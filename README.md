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
- [Notes de mise à jour](#notes-de-mise-à-jour)
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
  normaux et Hors-Séries toujours présentés en blocs distincts. Chaque numéro
  est identifié par « Nom du magazine - numéro - Mois année » (ex. « 01net -
  998 - Juin 2023 »), plutôt que par le nom de fichier brut.

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
| `ENABLE_API_DOCS` | Expose `/api/docs`, `/api/redoc` et `/api/openapi.json`. `false` par défaut : ces pages cartographient toute la surface d'API. À n'activer qu'en développement local. |

> `JWT_ALGORITHM` n'est plus lue : l'algorithme est figé dans le code
> (`app/security.py`) pour qu'une variable mal renseignée ne puisse pas
> affaiblir la signature des jetons.

> `BACKEND_PORT` n'est plus utilisée : le backend n'est plus publié sur l'hôte.

**Déploiement**

| Variable | Rôle |
| --- | --- |
| `IMAGE_TAG` | Tag des images applicatives déployées. `latest` redéploie un contenu différent à chaque merge, sans retour arrière possible : préférer un tag de version (`v0.19.1`) en production. |

**Infrastructure interne**

| Variable | Rôle |
| --- | --- |
| `REDIS_HOST` / `REDIS_PORT` | Adresse de Redis (file RQ, compteurs de quota, limitation de débit). Valeurs par défaut adaptées au `docker-compose.yml`. |
| `MEILI_HOST` | URL interne de Meilisearch. |
| `JWT_EXPIRE_MINUTES` | Durée de validité d'une session, en minutes (défaut : 1440, soit 24 h). |
| `LOG_DIR` | Répertoire des logs applicatifs (défaut : `/data/logs`). À surcharger pour lancer le backend hors Docker, où ce chemin n'existe pas. |

**Délais d'attente**

| Variable | Rôle |
| --- | --- |
| `OCR_TIMEOUT_SECONDS` | Délai maximum du sous-processus `ocrmypdf` (défaut : 1500, soit 25 min). Doit rester sous le `job_timeout` RQ de 30 min, pour que l'échec soit reporté sur le numéro plutôt que par la mort du job. |
| `MEILI_TIMEOUT_SECONDS` | Délai maximum des appels HTTP vers Meilisearch (défaut : 15). |

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
- **Énumération des comptes** : la connexion vérifie un hash factice lorsque
  l'adresse est inconnue, pour que le temps de réponse soit le même qu'avec un
  compte existant. Le message d'erreur est identique dans les deux cas.
- **Sessions** : JWT en cookie `httpOnly`, `Secure`, `SameSite=Strict`. Le
  jeton n'est **pas** renvoyé dans le corps de la réponse : l'authentification
  repose uniquement sur le cookie, ce qui évite qu'il finisse stocké en
  `localStorage`. Il porte `iat`, `jti`, `exp`, et une empreinte du hash du mot
  de passe — un changement de mot de passe invalide donc les sessions
  existantes. L'algorithme de signature est figé dans le code (`HS256`) et non
  pilotable par l'environnement. Un cookie devenu invalide est effacé côté
  client dès le premier appel API en échec, pour ne jamais laisser un cookie
  périmé faire boucler l'application sur l'écran de connexion.
- **Surface d'API** : `/api/docs`, `/api/redoc` et `/api/openapi.json` sont
  fermés par défaut (`ENABLE_API_DOCS`).
- **Messages d'erreur** : les erreurs de traitement stockées en base sont
  courtes et débarrassées des chemins absolus. La trace Python complète n'est
  écrite que dans les logs applicatifs, jamais renvoyée par l'API. Attention,
  ces messages sont visibles par **tout compte authentifié**, pas seulement
  par les administrateurs.
  L'assainissement ne s'applique qu'à l'écriture : les lignes antérieures au
  correctif conservent leur contenu d'origine.
  [`ops/nettoyer_messages_erreur.sql`](./ops/nettoyer_messages_erreur.sql)
  nettoie l'historique — à exécuter **avant d'ouvrir des comptes
  utilisateurs**. Le script inspecte d'abord, et n'écrit qu'après avoir
  remplacé son `ROLLBACK` final par `COMMIT`.
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

> **Régénération des thèmes** — `POST /api/admin/themes/regenerate-all` est
> **non destructif et reprenable** : chaque numéro conserve ses thèmes actuels
> jusqu'à ce qu'un lot les remplace effectivement. Si le quota Gemini s'épuise
> en cours de série, l'opération s'arrête proprement et un nouveau clic
> reprend là où elle s'était interrompue, sans repartir de zéro. La série
> avance par lots de 20 numéros, un appel Gemini par lot.

> **Déduplication des articles** — `POST /api/admin/articles/deduplicate`
> fonctionne en simulation par défaut : il renvoie `would_delete` sans rien
> supprimer. Passer `?dry_run=false` pour appliquer. Le critère de doublon
> ignore `end_page`, donc vérifiez le compte simulé avant d'appliquer.

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
| `test-backend` | `pytest` sur la suite backend. |
| `build-backend` / `build-frontend` | Build des images, sans publication. |

> Le jeu de règles `ruff` est volontairement restreint : le code n'ayant jamais
> été passé à un linter, activer tout `ruff` d'un coup rendrait la CI rouge sur
> du style. À élargir progressivement.

**Publication** — chaque push sur `main` construit et publie les images sur
GHCR (`ghcr.io/<user>/<repo>-backend`, `...-frontend`), taguées `:latest` et,
lors d'une release, avec le numéro de version.

**Tests**

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

La suite actuelle est du **calcul pur** : ni PostgreSQL, ni Redis, ni
Meilisearch, ni fichier PDF ne sont nécessaires. Les secrets attendus par
`Settings` sont posés par `tests/conftest.py`.

Elle couvre pour l'instant trois zones :

| Fichier | Couvre |
| --- | --- |
| `test_issue_parser.py` | Extraction du numéro, de la date et du libellé de mois depuis le nom de fichier. |
| `test_schemas.py` | Politique de mot de passe, bornes des pages d'article, cardinalité des tags. |
| `test_security.py` | Aller-retour des jetons, claims obligatoires, algorithme figé, invalidation au changement de mot de passe. |
| `test_authorization.py` | Frontière admin / utilisateur standard : aucune route `/api/admin` accessible à un compte non administrateur, ni à un visiteur non authentifié. Le contrôle parcourt les routes réellement déclarées, donc toute nouvelle route d'administration est couverte automatiquement. |
| `test_ocr_decision.py` | Décision OCR : présence d'une couche de texte, et détection du texte natif illisible (police au mapping corrompu). Les PDF témoins sont fabriqués à l'exécution avec PyMuPDF, aucun binaire n'est commité. |

**Ce qui n'est pas couvert** : l'extraction de sommaire et les thèmes, qui
dépendent de l'API Gemini, ainsi que les routers au-delà de leur frontière
d'autorisation (aucun test n'exerce encore une requête avec une vraie base).
Une régression y passerait inaperçue tant qu'aucun utilisateur ne la
rencontre.

## Versioning et changelog

- Les messages de commit suivent la convention
  [Conventional Commits](https://www.conventionalcommits.org/).
- `release-please` propose périodiquement une pull request de release ; la
  fusionner crée un tag semver, met à jour
  [`CHANGELOG.md`](./CHANGELOG.md) et republie les images taguées.
- La version affichée dans l'interface correspond à la dernière release
  publiée, pas au dernier commit poussé sur `main`.
- Le CI (`pull_request`) ignore les changements portant uniquement sur
  `CHANGELOG.md`/`.release-please-manifest.json` : sans ça, GitHub bloquait
  chaque PR de release derrière une approbation manuelle (« Action
  required »), le bot `github-actions[bot]` n'étant jamais reconnu comme
  collaborateur habituel.

## Notes de mise à jour

- **Après le passage à la version qui introduit `issue_month`/nom de
  collection dans les résultats de recherche globale** : ces deux champs
  viennent de l'index Meilisearch, alimenté à l'indexation de chaque page.
  Les pages déjà indexées avant cette mise à jour n'ont ni l'un ni l'autre
  tant qu'un réindexage complet n'a pas été relancé — sans quoi les
  résultats de recherche antérieurs à cette date affichent un en-tête
  incomplet (juste le nom de fichier). Déclencher ce réindexage depuis
  `Admin` → `Réglages` → réindexation manuelle du moteur de recherche.

## Hors scope V1

Lecture hors-ligne, application mobile native, annotations et favoris,
partage public de numéros, OCR de langues autres que le français et l'anglais.

## Licence

[MIT](./LICENSE).
