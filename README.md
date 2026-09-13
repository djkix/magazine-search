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

**Deux sources, complémentaires.** Un tag posé sur une collection est une donnée
que vous avez choisie : « Système D » porte « Bricolage », et cela vaut pour ses
199 numéros, sans exception et sans consommer de quota. Gemini, lui, infère
numéro par numéro — plus fin, mais plus incertain.

Les deux se cumulent. Mais le vocabulaire des tags mélange des **sujets**
(« Bricolage », « Santé ») et des **formats éditoriaux** (« Test », « Tutoriel »,
« Guide achat »), et propager les seconds donnerait une navigation par sujet où
« Test » écraserait tout. Dans les réglages, chaque tag porte donc une bascule
*sujet* / *format* : seuls les sujets sont propagés. Tout est en *format* par
défaut — rien ne se propage tant que vous n'avez pas choisi.

Le bouton *Simuler* affiche ce qui serait rattaché avant d'écrire quoi que ce
soit. La propagation ne marque pas les numéros comme traités : ils restent dans
la file de thématisation, et Gemini viendra compléter sans jamais effacer le
thème hérité du tag.

L'ordre de passage de la file est **aléatoire**, et non par ordre de scan : une
collection indexée tardivement se retrouvait sinon derrière toute la
bibliothèque — 1 043 numéros d'attente ont été mesurés pour « Système D », soit
près de trois jours de quota.

La régénération complète, depuis les réglages, est **non destructive et
reprenable** : chaque numéro conserve ses thématiques actuelles jusqu'à ce
qu'un lot les remplace. Si le quota s'épuise en cours de route, l'opération
s'arrête proprement et un nouveau clic reprend là où elle s'était interrompue.

Les réglages affichent le modèle utilisé, les plafonds, et la consommation du
jour. Le tableau de bord affiche deux compteurs : numéros déjà thématisés, et
« reste à faire » — ce dernier n'inclut que les numéros réellement éligibles
(sommaire extrait, pas encore passés par Gemini).

**Sous-thématiques.** Une thématique peut être découpée en regroupements plus
fins (« Crème solaire » sous « Santé »). Le quota Gemini ne permet pas de les
calculer dans l'application : une requête par thématique consommerait les trois
quarts d'une journée. Ils sont donc produits hors ligne.

Tout se fait depuis le tableau de bord, section *Sous-thématiques* :

1. **Télécharger** le corpus d'une thématique — ou tous en une archive. Le
   fichier contient les titres d'articles et la consigne à donner au modèle.
2. **Soumettre** ce fichier au modèle de votre choix, sans contrainte de quota.
3. **Déposer** sa réponse dans le champ prévu, sur la même page.

Le dépôt déclenche une **simulation** : la page affiche les numéros qui seraient
rattachés à chaque sous-thématique, les mots-clés ne correspondant à aucun
article, et le nombre de numéros qu'aucun regroupement ne couvre. **Rien n'est
écrit** tant que vous n'avez pas cliqué sur *Appliquer*.

Un avertissement apparaît si plus d'un tiers des numéros reste non rattaché :
le découpage est alors trop étroit, mieux vaut relancer le modèle que de
publier une navigation trouée.

Les mêmes opérations restent disponibles en ligne de commande, avec la même
logique et le même résultat :

```bash
docker exec magazine-search-app-backend-1 \
  python tools/importer_sous_thematiques.py -f /data/exports/sante.json
```

Le modèle ne fait que nommer les regroupements et fournir leurs mots-clés. Le
rattachement des numéros est calculé localement, en confrontant ces mots-clés
aux titres : le décompte reste vérifiable, et un numéro ajouté plus tard
rejoint les sous-thématiques existantes sans nouvel appel à un modèle.

```bash
docker exec magazine-search-app-backend-1 \
  python tools/importer_sous_thematiques.py --recalculer-tout --appliquer
```

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
| `GEMINI_TIMEOUT_SECONDS` | Délai maximum d'un appel à l'API Gemini (défaut : 120). Sans borne, une connexion suspendue immobilise le worker. |
| `LOG_TIMEZONE` | Fuseau des horodatages des journaux (défaut : `Europe/Paris`). Sans lui, un conteneur Docker journalise en UTC. |
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
| 0.26.0 | 2026-09-13 | Admin : déposer la réponse du modèle depuis le tableau de bord |
| 0.25.1 | 2026-09-11 | Outils : rendre le paquet `app` importable depuis `tools/` |
| 0.25.0 | 2026-09-11 | Sous-thématiques : socle de données et chaîne export/import |
| 0.24.2 | 2026-09-11 | Gemini : borner les appels à l'API et le nombre total de tentatives |
| 0.24.1 | 2026-09-11 | Journaux : horodatages dans le fuseau local, décalage inclus |
| 0.24.0 | 2026-09-11 | Déploiement : sauvegarde avant migration, fin de la boucle d'échec |
| 0.23.3 | 2026-09-11 | OCR : réparer la structure du PDF via qpdf en dernier recours |
| 0.23.2 | 2026-09-11 | Base : ne plus recréer un index déjà posé par une révision antérieure |
| 0.23.1 | 2026-09-10 | Lecteur : conserver les résultats au clic, retour vers la collection |
| 0.23.0 | 2026-09-10 | Thématiques : page dédiée triée par occurrences, avancement en admin |

**L'historique complet est dans [`CHANGELOG.md`](./CHANGELOG.md)**, généré
automatiquement à chaque release.

La version affichée dans l'interface, sous le logo, correspond à la dernière
release publiée — pas au dernier commit poussé.

## Licence

[MIT](./LICENSE).
