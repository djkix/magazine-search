# Magazine Search

Application web auto-hébergée de gestion, OCR et recherche plein texte d'une
collection de magazines PDF stockés sur un NAS (NFS).

Spécification complète : [`cahier-des-charges-v2.md`](./cahier-des-charges-v2.md).

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Architecture](#architecture)
- [Stack technique](#stack-technique)
- [Prérequis](#prérequis)
- [Déploiement](#déploiement)
- [Configuration](#configuration)
- [Sécurité](#sécurité)
- [Sauvegarde et restauration](#sauvegarde-et-restauration)
- [Utilisation](#utilisation)
- [Développement local](#développement-local)
- [Qualité et CI/CD](#qualité-et-cicd)
- [Versioning et changelog](#versioning-et-changelog)
- [Hors scope V1](#hors-scope-v1)
- [Licence](#licence)

## Fonctionnalités

**Ingestion**

- Scan du NAS avec déduplication par hash de contenu et attente de stabilité
  du fichier (un PDF encore en cours de copie n'est pas traité).
- Pipeline asynchrone (file RQ) : détection de texte natif, OCR conditionnel
  `fra+eng` via `ocrmypdf`/Tesseract, extraction des bounding boxes mot par mot
  pour le surlignage, miniature de couverture.
- Détection des PDF à mapping de police corrompu : un texte présent mais
  illisible (« lll Why | | | Il Ill ») est repéré par la densité de mots
  courants français/anglais, ce qui déclenche un `--force-ocr` au lieu d'un
  `--skip-text` qui aurait laissé les pages en l'état.
- Isolation par job : chaque traitement tourne dans un process forké, de sorte
  qu'un PDF corrompu ne fasse pas tomber le worker.
- Reprise après panne : un job expiré ou interrompu par un redéploiement est
  marqué en échec au redémarrage plutôt que de rester bloqué « en cours ».

**Organisation**

- **Collections** déduites automatiquement du répertoire de premier niveau du
  NAS (un titre de magazine = une collection), y compris si un numéro est
  déplacé ensuite.
- **Tags** créés à la main dans l'admin, rattachables à plusieurs collections.
- Numéro, mois (ou plage pour un bimestriel), année et indicateur
  Hors-Série/Spécial déduits du nom de fichier, avec repli sur le texte extrait
  quand le nom ne porte ni date ni numéro.
- Extraction automatique des sommaires via l'API Google Gemini (optionnelle).

**Consultation**

- Recherche plein texte (Meilisearch) avec filtres titre, année, numéro et
  tags ; un résultat par magazine, classé par nombre d'occurrences.
- Viewer PDF (`pdf.js`) avec surlignage des occurrences et recherche dans le
  document.
- Bibliothèque et sommaires en deux niveaux : collections, puis numéros —
  normaux et Hors-Séries toujours présentés en blocs distincts.

**Administration**

- Tableau de bord auto-rafraîchi : compteurs cliquables par statut, progression
  page par page du numéro en cours, activité récente triée par dernière
  activité réelle.
- Relance ciblée d'un scan ou d'un OCR, individuellement ou en lot.
- Logs applicatifs filtrables (niveau, composant) avec rotation.
- Réglages : modèle Gemini, tags, réindexation manuelle du moteur de recherche.

## Architecture

```
                    ┌───────────────────────────┐
   navigateur ──────►  Nginx Proxy Manager (TLS) │   hors de ce compose
                    └─────────────┬─────────────┘
                                  │ un seul port : FRONTEND_PORT
                    ┌─────────────▼─────────────┐
                    │  app-frontend (Next.js)   │  relaie /api/* en interne
                    └─────────────┬─────────────┘
                                  │ réseau Docker interne
                    ┌─────────────▼─────────────┐
                    │  app-backend (FastAPI)    │  non publié sur l'hôte
                    └──┬────────┬────────┬──────┘
                       │        │        │
              ┌────────▼──┐ ┌───▼────┐ ┌─▼─────────────┐
              │ PostgreSQL│ │ Redis  │ │ Meilisearch   │
              └────▲──────┘ └───┬────┘ └───────────────┘
                   │            │ file RQ
              ┌────┴──────┐ ┌───▼──────────────────────┐
              │ db-backup │ │ worker (OCR, Gemini)     │
              └───────────┘ └──────────┬───────────────┘
                                       │ lecture seule
                                 ┌─────▼─────┐
                                 │  NAS NFS  │
                                 └───────────┘
```

Le navigateur ne parle qu'au frontend. Le reverse proxy et la terminaison TLS
sont délégués à **Nginx Proxy Manager**, déployé séparément sur l'hôte : il n'a
besoin de forwarder qu'**un seul port**, sans routage par chemin.

Le backend n'est **pas** publié sur l'hôte — il n'est joignable que depuis le
réseau Docker interne.

## Stack technique

| Composant | Techno |
| --- | --- |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2 |
| Frontend | Next.js 14 (App Router), React 18, Tailwind CSS |
| Base de données | PostgreSQL 16 |
| File d'attente | RQ (Redis Queue) |
| Recherche | Meilisearch |
| OCR | `ocrmypdf` / Tesseract (`fra+eng`) |
| Extraction de sommaire | API Google Gemini (`google-genai`) |
| Viewer PDF | `pdf.js` |
| Déploiement | Docker Compose, images publiées sur GHCR |

## Prérequis

- Docker et Docker Compose v2.
- Un partage NAS monté en NFS sur l'hôte, **en lecture seule**, organisé en un
  répertoire de premier niveau par titre de magazine — ce nom devient le nom de
  la collection. Les PDF peuvent être rangés directement dedans ou dans des
  sous-dossiers (année, Hors-Séries…) : ces sous-dossiers n'affectent pas la
  collection, mais un dossier « Hors Séries » ou « Numéros Spéciaux » marque le
  numéro comme tel.
- Nginx Proxy Manager (ou équivalent) sur l'hôte, avec un nom de domaine si
  l'application est exposée hors LAN.
- Une clé API Google Gemini, uniquement si vous voulez l'extraction automatique
  des sommaires.

## Déploiement

**1. Préparer la configuration**

```bash
cp .env.example .env
```

Générer les deux secrets obligatoires :

```bash
openssl rand -hex 32   # -> JWT_SECRET_KEY   (32 caractères minimum)
openssl rand -hex 24   # -> MEILI_MASTER_KEY (16 caractères minimum)
openssl rand -hex 24   # -> POSTGRES_PASSWORD
```

> Le backend **refuse de démarrer** si ces secrets sont absents, trop courts,
> ou laissés à une valeur d'exemple. C'est volontaire : l'ancienne version
> démarrait silencieusement avec un secret public, connu de quiconque lit le
> dépôt.

`.env` ne doit jamais être commité.

**2. Vérifier le montage NAS**

`NAS_MOUNT_PATH` doit pointer vers un répertoire déjà monté en NFS sur l'hôte.

**3. Démarrer**

```bash
docker compose up -d
docker compose logs -f app-backend
```

En cas de secret invalide, le conteneur redémarre en boucle et le log indique
précisément la variable en cause.

**4. Configurer le reverse proxy**

Dans NPM, créer un *Proxy Host* :

- *Details* : `Forward Hostname/IP` = IP de l'hôte Docker, `Forward Port` =
  `${FRONTEND_PORT}` (ex. `3001`). Pas de *Custom Location* à ajouter, `/api`
  est relayé en interne par le frontend.
- *SSL* : activer Let's Encrypt et *Force SSL* — le cookie de session est
  `Secure`, l'application doit être servie en HTTPS.

**5. Créer le compte administrateur**

Renseigner `ADMIN_BOOTSTRAP_EMAIL` et `ADMIN_BOOTSTRAP_PASSWORD` (12 caractères
minimum) puis démarrer : le compte est créé **uniquement si aucun admin
n'existe encore**. Une fois le compte en place, videz les deux variables — la
valeur n'est plus lue, et un mot de passe en clair dans `.env` qui recréerait
un admin après une restauration ratée est une porte d'entrée inutile.

**6. Premier scan**

Se connecter, puis déclencher un scan depuis `/admin`.

## Configuration

Toutes les variables sont définies dans `.env`. Voir
[`.env.example`](./.env.example) pour le fichier commenté complet.

**Secrets — obligatoires, contrôlés au démarrage**

| Variable | Contrainte |
| --- | --- |
| `JWT_SECRET_KEY` | 32 caractères minimum. Valeurs d'exemple rejetées. Le modifier invalide toutes les sessions en cours. |
| `MEILI_MASTER_KEY` | 16 caractères minimum. Valeurs d'exemple rejetées. |
| `POSTGRES_PASSWORD` | À générer aléatoirement. |

**Compte d'amorçage — facultatif**

| Variable | Rôle |
| --- | --- |
| `ADMIN_BOOTSTRAP_EMAIL` | Laisser vide si un admin existe déjà. |
| `ADMIN_BOOTSTRAP_PASSWORD` | 12 caractères minimum si renseigné. Les deux variables fonctionnent en paire. |

**Réseau**

| Variable | Rôle |
| --- | --- |
| `FRONTEND_PORT` | Port publié sur l'hôte — le seul que le reverse proxy doit atteindre. |
| `BACKEND_CORS_ORIGINS` | Origines tierces autorisées, séparées par des virgules. Vide = aucune, ce qui est le cas normal puisque le frontend relaie `/api/*` sur sa propre origine. |

> `BACKEND_PORT` n'est plus utilisée : le backend n'est plus publié sur l'hôte.

**Déploiement**

| Variable | Rôle |
| --- | --- |
| `IMAGE_TAG` | Tag des images applicatives déployées. `latest` redéploie un contenu différent à chaque merge, sans retour arrière possible : préférer un tag de version (`v0.19.1`) en production. |

**Stockage et sauvegarde**

| Variable | Rôle |
| --- | --- |
| `NAS_MOUNT_PATH` | Chemin **hôte** du montage NFS, monté en lecture seule dans les conteneurs. |
| `BACKUP_DIR` | Répertoire hôte des dumps PostgreSQL. |
| `BACKUP_RETENTION_DAYS` | Rétention avant purge automatique (défaut : 14). |
| `BACKUP_INTERVAL_SECONDS` | Intervalle entre deux sauvegardes (défaut : 86400). |

**Extraction de sommaire — facultative**

| Variable | Rôle |
| --- | --- |
| `GEMINI_API_KEY` | Sans clé, l'extraction des sommaires est ignorée ; OCR et recherche fonctionnent normalement. |
| `GEMINI_MODEL` | Modèle utilisé, également réglable depuis l'admin. |

## Sécurité

Le modèle de menace est celui d'une application auto-hébergée, exposée derrière
un reverse proxy, avec un petit nombre de comptes de confiance.

- **Secrets** : aucune valeur de repli. L'application refuse de démarrer plutôt
  que de tourner avec un secret connu.
- **Mots de passe** : hachés en Argon2. 12 caractères minimum à la création et
  à la réinitialisation. La règle n'est volontairement **pas** appliquée à la
  connexion, pour ne pas divulguer la politique ni bloquer un compte ancien.
- **Sessions** : JWT en cookie `httpOnly`, `Secure`, `SameSite=Lax`. Le jeton
  porte une empreinte du hash du mot de passe, de sorte qu'un changement de mot
  de passe invalide les sessions existantes.
- **Surface réseau** : seul le frontend est publié. Le backend, PostgreSQL,
  Redis et Meilisearch restent sur le réseau Docker interne.
- **Cloisonnement** : le conteneur frontend ne reçoit que les quatre variables
  dont il a besoin, et non l'intégralité des secrets backend.
- **CORS** : aucune origine tierce autorisée par défaut. Pas de repli sur le
  joker, incompatible avec l'envoi du cookie de session.
- **Anti-force-brute** : limitation de débit sur `/login`, adossée à Redis pour
  survivre aux redémarrages et être partagée entre workers.
- **En-têtes HTTP** : `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy` et `Permissions-Policy` posés par le frontend.

**Limites connues**

- Le backend est lancé avec `--forwarded-allow-ips="*"` : un client déjà
  présent sur le réseau Docker interne peut forger un `X-Forwarded-For` et
  réinitialiser son compteur anti-force-brute. Restreindre cette valeur à
  l'adresse du conteneur frontend ferme complètement le point.
- Les conteneurs tournent en `root`.
- Pas de politique de sécurité du contenu (CSP) : elle doit être calibrée avec
  le viewer `pdf.js`, qui utilise des workers et des URL `blob:`.

## Sauvegarde et restauration

La base PostgreSQL est la **seule donnée non reconstructible** de la stack :
elle concentre le texte OCR intégral, les sommaires extraits via l'API Gemini,
les tags, collections et comptes. Les PDF du NAS, eux, peuvent être re-scannés.

Le service `db-backup` produit un dump compressé à intervalle régulier, avec
rotation. Les fichiers sont écrits sous `${BACKUP_DIR}` au format
`<base>_<horodatage>.sql.gz`.

```bash
# Sauvegardes disponibles
ls -lh ./backups

# Déclencher une sauvegarde immédiate
docker compose restart db-backup

# Journal du service
docker compose logs -f db-backup
```

**Restauration**

```bash
# 1. Arrêter les services qui écrivent
docker compose stop app-backend worker

# 2. Restaurer dans une base de test d'abord
gunzip -c ./backups/magazines_20260909T030000Z.sql.gz \
  | docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres

# 3. Redémarrer
docker compose start app-backend worker
```

> Placez `BACKUP_DIR` sur un autre support que le volume Docker de PostgreSQL :
> une sauvegarde sur le même disque ne protège pas d'une panne matérielle.
> **Testez une restauration périodiquement** — une sauvegarde jamais restaurée
> n'est pas une sauvegarde.

## Utilisation

1. **Scan** — depuis `/admin`, déclencher un scan du NAS. Les nouveaux PDF sont
   détectés, dédupliqués et mis en file. Le scan ne relit que les fichiers
   réellement nouveaux ou modifiés.
2. **Suivi** — le tableau de bord affiche l'avancement page par page. Les
   compteurs par statut sont cliquables et filtrent la liste.
3. **Recherche** — la recherche plein texte porte sur tout le texte extrait ;
   les occurrences sont surlignées dans le viewer.
4. **Organisation** — créer des tags dans les réglages et les rattacher aux
   collections.

## Développement local

Les services d'infrastructure via Docker, les applications en local :

```bash
# Infrastructure seule
docker compose up -d postgres redis meilisearch

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

Un `.env` valide reste nécessaire : les contrôles sur les secrets s'appliquent
aussi en développement.

**Migrations**

```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

Les migrations sont appliquées automatiquement au démarrage du conteneur
`app-backend`, par `entrypoint.sh`. Seul le service API les exécute, jamais le
worker, pour éviter toute course entre les deux.

**Note sur le worker** — RQ forke un process par job. Avant d'entrer dans la
boucle, `worker/run.py` appelle `engine.dispose(close=False)` : la connexion
utilisée au démarrage n'est pas fermée, mais détachée du pool, de sorte qu'un
process forké n'hérite pas d'une session PostgreSQL déjà en cours d'utilisation
(source d'erreurs `DuplicatePreparedStatement`). Les statements préparés côté
serveur sont par ailleurs désactivés (`prepare_threshold=None`).

## Qualité et CI/CD

**Hooks pre-commit**

```bash
pip install pre-commit && pre-commit install
```

- `gitleaks` — détection de secrets.
- `ruff` — erreurs réelles côté backend (syntaxe, noms non définis).
- Contrôles de format : YAML, JSON, TOML, fins de fichier, espaces en fin de
  ligne, conflits de merge non résolus, fichiers volumineux.

**Intégration continue** — sur chaque push et pull request :

| Job | Rôle |
| --- | --- |
| `gitleaks` | Scan de secrets sur tout l'historique. |
| `typecheck-frontend` | `tsc --noEmit`. |
| `lint-backend` | `ruff check` sur un jeu de règles restreint aux erreurs réelles. |
| `build-backend` / `build-frontend` | Build des images, sans publication. |

> Le jeu de règles `ruff` est volontairement restreint : le code n'ayant jamais
> été passé à un linter, activer tout `ruff` d'un coup rendrait la CI rouge sur
> du style. À élargir progressivement.

**Publication** — chaque push sur `main` construit et publie les images sur
GHCR (`ghcr.io/<user>/<repo>-backend`, `...-frontend`), taguées `:latest` et,
lors d'une release, avec le numéro de version.

**Il n'existe aucun test automatisé.** C'est la principale faiblesse du projet :
une régression sur la décision OCR ou le parsing de sommaire ne lève aucune
exception, elle dégrade silencieusement la bibliothèque indexée.

## Versioning et changelog

- Les messages de commit suivent la convention
  [Conventional Commits](https://www.conventionalcommits.org/).
- `release-please` propose périodiquement une pull request de release ; la
  fusionner crée un tag semver, met à jour
  [`CHANGELOG.md`](./CHANGELOG.md) et republie les images taguées.
- La version affichée dans l'interface correspond à la dernière release
  publiée, pas au dernier commit poussé sur `main`.

## Hors scope V1

Lecture hors-ligne, application mobile native, annotations et favoris,
partage public de numéros, OCR de langues autres que le français et l'anglais.

## Licence

[MIT](./LICENSE).
