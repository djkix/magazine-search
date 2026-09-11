# Magazine Search

## Le principe

Vous avez une collection de magazines en PDF sur un NAS. Des centaines, voire
des milliers de numéros, accumulés au fil des années, dans lesquels il est
impossible de retrouver quoi que ce soit : ni par le nom de fichier, ni en
ouvrant les documents un par un.

Magazine Search transforme ce dossier en bibliothèque consultable.

L'application surveille le partage réseau, détecte les nouveaux PDF, en extrait
le texte — par OCR quand il s'agit de scans — puis indexe l'ensemble. À partir
de là, une recherche sur « ponceuse excentrique » remonte les numéros qui en
parlent, avec les occurrences surlignées directement dans les pages.

Le reste est déduit automatiquement : le titre du magazine devient une
collection, le numéro et la date sont lus dans le nom de fichier, le sommaire
est reconstruit depuis la page de sommaire du magazine, et des thématiques sont
attribuées à chaque numéro. Vous n'avez rien à saisir.

L'application est **auto-hébergée** : vos fichiers restent chez vous, sur votre
matériel. Seule l'attribution des thématiques fait appel à un service externe,
et elle est facultative.

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Utilisation](#utilisation)
- [Configuration](#configuration)
- [Sauvegarde et restauration](#sauvegarde-et-restauration)
- [Stack technique](#stack-technique)
- [Derniers changements](#derniers-changements)
- [Licence](#licence)

## Fonctionnalités

**Recherche plein texte**

Sur l'intégralité du texte extrait, avec filtres par titre, année, numéro et
thématique. Un résultat par magazine, classé par nombre d'occurrences. Les
résultats affichent « magazine - numéro - Mois année » plutôt que le nom de
fichier brut.

**Lecture avec surlignage**

Visionneuse PDF intégrée, occurrences du terme recherché surlignées à leur
position exacte dans la page, et recherche dans le document ouvert.

**Ingestion automatique**

Détection des nouveaux fichiers, déduplication par empreinte de contenu, et
attente de stabilité avant traitement — un PDF encore en cours de copie n'est
pas ingéré. L'OCR n'est déclenché que si nécessaire.

Les PDF dont le texte natif est présent mais illisible — police au mapping
corrompu, qui produit « lll Why | | | Il Ill » au lieu de mots — sont repérés
par la densité de mots courants et repassent par un OCR complet.

**Organisation déduite**

Le répertoire de premier niveau du NAS devient le nom de la collection. Numéro,
mois — ou plage de mois pour un bimestriel — année et statut Hors-Série sont lus
dans le nom de fichier, avec repli sur le texte de couverture quand le nom ne
porte ni date ni numéro.

**Sommaires reconstruits**

Extraction locale, par analyse du texte de la page de sommaire : aucun service
externe, aucun coût. Plusieurs mises en page sont reconnues — points de
conduite, colonnes, numéro avant ou après le titre, séparateur typographique.
Quand rien n'est extrait, la raison est consignée et visible dans le
backoffice : page introuvable, ou page trouvée mais illisible.

**Thématiques**

Regroupement des numéros par sujet (« Automobile », « Bricolage »…) via l'API
Google Gemini, par lots de 20 numéros et un seul appel par lot. Le vocabulaire
déjà utilisé est transmis au modèle pour éviter les doublons proches. Deux
plafonds — journalier et par minute — protègent votre quota. Fonctionnalité
entièrement facultative.

**Administration**

Tableau de bord auto-rafraîchi, compteurs cliquables par statut, progression
page par page du numéro en cours, relances ciblées, journaux applicatifs
filtrables et gestion des comptes.

## Utilisation

### Rechercher

Saisissez vos termes dans la barre de recherche. La recherche porte sur tout le
texte extrait de tous les numéros.

Affinez avec les filtres : collection, année, thématique. Un clic sur un
résultat ouvre le numéro à la page concernée, occurrences surlignées.

Dans la visionneuse, la recherche dans le document permet de circuler entre les
occurrences du numéro ouvert : la liste des résultats reste affichée après un
clic, le résultat consulté restant repérable dedans. La flèche de retour ramène
à la collection du numéro plutôt qu'au sommet de la bibliothèque.

### Parcourir la bibliothèque

La bibliothèque s'explore en deux niveaux : d'abord les collections, avec leur
couverture et leur nombre de numéros, puis le détail d'une collection.

Les numéros ordinaires et les Hors-Séries sont toujours présentés en blocs
distincts, même triés par date. Une colonne latérale liste les années présentes
et les Hors-Séries, chacune cliquable pour filtrer.

La vue « Sommaires » d'une collection affiche les articles extraits de chaque
numéro, avec le même système de filtres.

La page « Thématiques » les liste toutes triées par nombre de numéros
distincts qui les portent, toutes collections confondues ; cliquer sur l'une
d'elles affiche les numéros concernés.

### Organiser avec des tags

Une **collection** est créée automatiquement, vous n'avez rien à faire.

Un **tag** se crée à la main dans les réglages et peut regrouper plusieurs
collections — « Bricolage » rassemblant Système D et Maison & Travaux, par
exemple. Une collection peut porter plusieurs tags.

### Ajouter des numéros

Déposez les PDF dans le bon répertoire du NAS, puis déclenchez un scan depuis
`/admin`.

Le scan ne relit que les fichiers réellement nouveaux ou modifiés : son coût
suit ce que vous ajoutez, pas la taille totale de la bibliothèque. Les numéros
détectés sont mis en file, et le tableau de bord affiche la progression page par
page.

Un scan interrompu — redémarrage, coupure — est récupéré automatiquement : les
numéros restés « en cours » sont marqués en échec au redémarrage du worker, ce
qui débloque la barre de progression.

### Relancer un traitement

Depuis `/admin`, les compteurs par statut sont cliquables : ils filtrent la
liste sur les numéros concernés, sans limite d'ancienneté. Vous pouvez relancer
un numéro isolé, ou tous ceux d'un statut.

Pour les numéros sans sommaire, **deux actions distinctes** sont proposées, car
leur coût n'a rien de comparable :

| Action | Ce qu'elle fait | Durée |
| --- | --- | --- |
| **Réextraire les sommaires** | Rejoue le parsing à partir du texte déjà extrait. Ni OCR, ni appel externe. | Quelques minutes pour toute la bibliothèque |
| **Relancer l'OCR complet** | Refait le traitement de zéro. | Environ une minute par numéro |

Dans la quasi-totalité des cas, c'est la première qu'il faut : le texte OCR ne
change pas, seul le parseur du sommaire évolue. La seconde n'est utile que si la
logique de décision OCR elle-même a changé, et demande une confirmation
explicite.

### Gérer les thématiques

Les thématiques sont attribuées automatiquement après l'extraction d'un
sommaire. Un numéro sans sommaire n'est pas concerné : le modèle a besoin de la
liste des articles pour travailler.

La régénération complète, depuis les réglages, est **non destructive et
reprenable** : chaque numéro conserve ses thématiques actuelles jusqu'à ce
qu'un lot les remplace. Si le quota s'épuise en cours de route, l'opération
s'arrête proprement et un nouveau clic reprend là où elle s'était interrompue.

Les réglages affichent le modèle utilisé, les plafonds, et la consommation du
jour. Le tableau de bord affiche deux compteurs : numéros déjà thématisés, et
« reste à faire » — ce dernier n'inclut que les numéros réellement éligibles
(sommaire extrait, pas encore passés par Gemini).

### Consulter les journaux

La page de logs filtre par niveau et par composant. Le fichier de sauvegarde
après rotation reste consultable, et les traces d'exception y sont conservées —
c'est là qu'il faut chercher le détail d'un échec, les messages affichés dans
l'interface étant volontairement courts.

## Configuration

Toutes les variables sont définies dans `.env`. Voir
[`.env.example`](./.env.example) pour le fichier commenté complet.

**Obligatoires** — l'application refuse de démarrer si elles manquent, sont trop
courtes, ou sont restées à une valeur d'exemple.

| Variable | Contrainte |
| --- | --- |
| `JWT_SECRET_KEY` | 32 caractères minimum. Le modifier déconnecte tout le monde. |
| `MEILI_MASTER_KEY` | 16 caractères minimum. |
| `POSTGRES_PASSWORD` | À générer aléatoirement. |

Générer une valeur : `openssl rand -hex 32`.

**Principales options**

| Variable | Rôle |
| --- | --- |
| `NAS_MOUNT_PATH` | Chemin hôte du partage, monté en lecture seule. |
| `FRONTEND_PORT` | Seul port publié ; c'est lui que le reverse proxy atteint. |
| `IMAGE_TAG` | Version déployée. Préférer un tag précis à `latest` en production. |
| `GEMINI_API_KEY` | Sans clé, les thématiques sont ignorées ; recherche et OCR fonctionnent normalement. |
| `OCR_TIMEOUT_SECONDS` | Délai maximum d'`ocrmypdf` (défaut : 1500). |
| `PRE_MIGRATION_DUMP_DIR` | Où atterrit la sauvegarde prise avant une migration (défaut : `/data/pre-migration`). |
| `PRE_MIGRATION_DUMP_KEEP` | Nombre de sauvegardes pré-migration conservées (défaut : 3). |
| `SKIP_PRE_MIGRATION_DUMP` | À `1`, migre sans sauvegarde préalable. À n'utiliser qu'en connaissance de cause. |
| `MIGRATION_FAILURE_DELAY_SECONDS` | Pause avant de sortir en erreur quand une migration échoue (défaut : 30), pour éviter une boucle de redémarrage trop serrée. |
| `ADMIN_BOOTSTRAP_EMAIL` / `ADMIN_BOOTSTRAP_PASSWORD` | Compte créé au premier démarrage si aucun admin n'existe. À vider ensuite. |

## Sauvegarde et restauration

La base PostgreSQL est la **seule donnée non reconstructible** : elle contient
le texte OCR intégral, les sommaires, les thématiques et les comptes. Les PDF du
NAS, eux, peuvent être re-scannés.

Le service `db-backup` produit un dump compressé quotidien avec rotation, sous
`${BACKUP_DIR}`.

```bash
ls -lh ./backups                    # sauvegardes disponibles
docker compose restart db-backup    # sauvegarde immédiate
docker compose logs -f db-backup    # journal du service
```

**Restauration**

```bash
docker compose stop app-backend worker

gunzip -c ./backups/magazines_<horodatage>.sql.gz \
  | docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres

docker compose start app-backend worker
```

> Placez `BACKUP_DIR` sur un autre support que le volume PostgreSQL, et
> **testez une restauration périodiquement** — une sauvegarde jamais restaurée
> n'est pas une sauvegarde.

**Sauvegarde automatique avant migration**

Quand le backend démarre alors qu'une migration de schéma est en attente, il
prend d'abord un dump, puis migre. Si ce dump échoue, la migration est annulée
plutôt que tentée sans filet.

Un redémarrage ordinaire ne déclenche rien : la version appliquée en base est
comparée à celle attendue par le code, et le dump n'a lieu qu'en cas d'écart.

Ces fichiers sont au format `custom` et se restaurent avec `pg_restore`, non
avec `psql` :

```bash
docker compose stop app-backend worker

docker compose exec -T postgres pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  --clean --if-exists < /data/pre-migration/avant-migration-<horodatage>.dump

docker compose start app-backend worker
```

> Ils atterrissent sur le volume `app_data`, pas sur `BACKUP_DIR`. C'est un
> filet tendu le temps d'une migration, pas un substitut aux sauvegardes
> quotidiennes.

## Stack technique

| Composant | Techno |
| --- | --- |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2 |
| Frontend | Next.js 14 (App Router), React 18, Tailwind CSS |
| Base de données | PostgreSQL 16 |
| File d'attente | RQ (Redis Queue) |
| Recherche | Meilisearch |
| OCR | `ocrmypdf` / Tesseract (`fra+eng`) |
| Thématiques | API Google Gemini (`google-genai`) |
| Visionneuse | `pdf.js` |
| Déploiement | Docker Compose, images publiées sur GHCR |

## Derniers changements

| Version | Date | Changement |
| --- | --- | --- |
| 0.22.5 | 2026-09-10 | Sommaire : reconnaître un intitulé de rubrique tout en minuscules |
| 0.22.4 | 2026-09-10 | Ne plus dupliquer numéro et date quand le nom de collection est absent |
| 0.22.3 | 2026-09-10 | Sommaire : consigner pourquoi aucune entrée n'a été extraite |
| 0.22.1 – 0.22.2 | 2026-09-10 | Thématiques : lots ramenés à 20 numéros d'après la mesure réelle |
| 0.22.0 | 2026-09-10 | Thématiques : ne plus détruire les thèmes avant régénération |
| 0.22.0 | 2026-09-10 | Étendre « magazine - numéro - Mois année » aux résultats de recherche |
| 0.21.0 | 2026-09-10 | Afficher « magazine - numéro - Mois année » au lieu du nom de fichier |
| 0.20.5 | 2026-09-10 | Résoudre le conflit de dépendances `httpx` et la panne CI associée |
| 0.20.4 | 2026-09-09 | Ne plus masquer l'erreur d'origine ni fuir de connexion au nettoyage |
| 0.20.3 | 2026-09-09 | Bornes sur les listes admin, déduplication en simulation, timeout OCR |

**L'historique complet est dans [`CHANGELOG.md`](./CHANGELOG.md)**, généré
automatiquement à chaque release.

La version affichée dans l'interface, sous le logo, correspond à la dernière
release publiée — pas au dernier commit poussé.

## Licence

[MIT](./LICENSE).
