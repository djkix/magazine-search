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
collection, le numéro et la date sont lus dans le nom de fichier, et le
sommaire est reconstruit depuis la page de sommaire du magazine. Vous n'avez
rien à saisir.

Une navigation par sujet vient compléter cette organisation : une fois une
taxonomie mise en place (une seule fois, voir *Gérer les thématiques*), chaque
nouvel article y est rattaché de lui-même, sans aucune action de votre part.

L'application est **auto-hébergée** : vos fichiers restent chez vous, sur votre
matériel. Seule la construction initiale de la taxonomie fait appel à un
service externe, et elle est facultative.

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

Les magazines portent dans leur marge le nom du fichier de maquette qui a servi
à les composer (« 607-sommaire.indd »). L'OCR le lit comme du texte ordinaire :
le parseur l'écarte, et le retire lorsqu'il s'est collé à la fin d'un titre
valide. Le filtre ne vise que ce motif précis — un critère de brièveté aurait
supprimé des rubriques bien réelles comme « MIX » ou « Q&A », et un critère
d'absence de voyelle aurait emporté les « GT3 RS » des magazines automobiles.

**Thématiques**

Navigation par sujet à deux niveaux (thématique puis sous-thématique),
rattachée aux **articles**. La taxonomie se construit hors ligne — un modèle
de langage sans contrainte de quota nomme les regroupements, le rattachement
lui-même est calculé localement par correspondance de mots-clés, donc gratuit
et rejouable à volonté. Fonctionnalité entièrement facultative.

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

### Explorer par thématique

La page « Thématiques » descend en trois écrans :

1. **La thématique** — « Alimentation », « Audio », « Fiscalité » — avec le
   nombre d'articles rattachés, les plus fournies en tête.
2. **Ses sous-thématiques** — « Légumes », « Budget alimentaire ». Une
   sous-thématique affichée à zéro article n'est pas un oubli : elle signale
   des mots-clés qui n'accrochent rien, ce qui aide à corriger la taxonomie.
3. **Les articles**, regroupés par collection, du numéro le plus récent au plus
   ancien. Chaque ligne ouvre le lecteur directement à la page de l'article.

Le rattachement se fait au niveau de l'**article**, pas du numéro : « Les
légumes, bientôt une denrée de luxe » relève de « Alimentation > légumes » sans
y entraîner les vingt autres titres du même sommaire.

Cette navigation reste vide tant qu'aucune taxonomie n'a été importée — voir
*Gérer les thématiques* plus bas.

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

**Deux absences de sommaire, qui ne se valent pas.** Un numéro peut n'en
comporter aucun : c'est légitime, il reste marqué *terminé*. Mais lorsque la
page de sommaire a bien été localisée et qu'aucune entrée n'a pu en être lue,
c'est un échec de lecture, et le numéro est marqué *en échec*. Auparavant les
deux passaient pour des succès, ce qui rendait le second invisible : la
bibliothèque affichait 675 numéros « terminés » dont une partie n'avait
simplement jamais pu être exploitée.

Certaines maquettes resteront hors de portée. Les mensuels qui composent leurs
numéros de page en gros caractères décoratifs — la presse musicale anglophone
notamment — ne laissent aucun chiffre dans le texte reconnu, et aucun parseur
ne peut rattacher un titre à une page qui n'y figure pas.

### Gérer les thématiques

Les thématiques sont attribuées automatiquement après l'extraction d'un
sommaire. Un numéro sans sommaire n'est pas concerné : le modèle a besoin de la
liste des articles pour travailler.

**Deux sources, complémentaires.** Un tag posé sur une collection est une donnée
que vous avez choisie : « Système D » porte « Bricolage », et cela vaut pour ses
199 numéros, sans exception et sans consommer de quota. Gemini, lui, infère
numéro par numéro — plus fin, mais plus incertain.

Les deux se cumulent. Mais le vocabulaire des tags mélangeait des **sujets**
(« Bricolage », « Santé ») et des **formats éditoriaux** (« Test », « Tutoriel »,
« Guide achat »), et propager les seconds aurait donné une navigation par sujet
où « Test » écraserait tout. D'où la distinction *sujet* / *format* portée par
chaque tag — devenue sans objet depuis le retrait de la propagation, voir
ci-dessous.

> **Le thémage par numéro n'est plus actif.** Il reposait sur des appels à
> Gemini, dont le quota gratuit (20 requêtes par jour) rendait l'opération
> irréaliste à l'échelle de la bibliothèque. La navigation par sujet passe
> désormais par la **taxonomie par article** décrite plus bas, construite hors
> ligne puis importée.
>
> Concrètement : plus aucun enfilement automatique à l'ingestion ni à la
> ré-extraction des sommaires, et deux commandes retirées de l'interface —
> *Régénérer les thématiques* et *Propager les tags de sujet*. Leurs endpoints
> (`POST /admin/themes/regenerate-all`, `POST /admin/tags/propagate`) existent
> toujours : rien n'a été supprimé en base, et les écrans sont restaurables.
>
> La bascule *sujet* / *format* de chaque tag n'a plus de consommateur et a
> été retirée de l'interface des réglages ; le champ subsiste en base et dans
> l'API. Les tags servent aujourd'hui à **filtrer la recherche**, tous types
> confondus.

Le tableau de bord mesure désormais la couverture de la taxonomie au niveau de
l'**article** et non du numéro : *Articles rattachés* et *Sans sous-thématique*.
Les articles sont comptés distincts — un article relevant de plusieurs
sous-thématiques ne pèse qu'une fois. Les anciens compteurs s'appuyaient sur
`themed_at`, posé sur tout numéro parcouru par un lot même quand le modèle ne
lui attribuait rien : ils surestimaient la couverture.

La vue *Par thématique* d'une collection s'appuie elle aussi sur la taxonomie :
elle liste les sous-thématiques présentes dans les articles de la collection,
puis les articles correspondants groupés par numéro. Elle tient en une requête,
là où la version précédente en faisait une par numéro affiché.

**Sous-thématiques.** Chaque thématique peut être découpée en regroupements
plus fins (« Légumes » sous « Alimentation »), rattachés aux **articles** et
non aux numéros entiers — un numéro touche souvent plusieurs sujets, et
rattacher tout son sommaire à chacun contaminerait les corpus. Le quota Gemini
ne permet pas de calculer cette taxonomie dans l'application : elle est donc
produite hors ligne, par un modèle sans contrainte de quota.

Tout se fait depuis le tableau de bord, section *Sous-thématiques* :

1. **Télécharger** le corpus complet (tous les titres d'articles, groupés par
   collection pour donner du contexte au modèle, avec la consigne intégrée).
2. **Soumettre** ce fichier à un modèle de langage de votre choix.
3. **Déposer** sa réponse dans le champ prévu, sur la même page.

Le dépôt déclenche une **simulation** : la page affiche, par sous-thématique,
le nombre d'articles rattachés et les mots-clés sans correspondance, ainsi que
la proportion du corpus couverte. **Rien n'est écrit** tant que vous n'avez pas
cliqué sur *Appliquer*.

L'import est **cumulatif** : la réponse d'un modèle sur un corpus de cette
taille dépasse souvent sa limite de sortie et arrive en plusieurs morceaux —
chaque dépôt s'ajoute aux sous-thématiques déjà en base plutôt que de les
remplacer. Un avertissement apparaît si moins de la moitié du corpus est
couverte : les mots-clés sont probablement trop étroits.

Les mêmes opérations restent disponibles en ligne de commande, avec la même
logique et le même résultat :

```bash
docker exec magazine-search-app-backend-1 \
  python tools/importer_sous_thematiques.py -f /data/exports/reponse.json
```

Le modèle ne fait que nommer les regroupements et fournir leurs mots-clés. Le
rattachement des articles est calculé localement, en confrontant ces mots-clés
aux titres : le résultat reste vérifiable, et un article ajouté plus tard
rejoint automatiquement les sous-thématiques existantes, dès l'extraction de
son sommaire — sans nouvel appel à un modèle, et sans action de votre part.

```bash
docker exec magazine-search-app-backend-1 \
  python tools/importer_sous_thematiques.py --recalculer-tout --appliquer
```

Le tableau de bord affiche aussi, à la demande, les **articles non
rattachés** et les mots les plus fréquents parmi eux : un terme qui revient
souvent et qu'aucun mot-clé ne couvre encore se repère à l'œil, sans appel à
un modèle — de quoi compléter la taxonomie au fil de l'eau.

Un bouton dédié permet aussi de **télécharger ces orphelins** pour un modèle,
distinct de l'export complet : il ne contient que ce qui reste à classer,
accompagné de la taxonomie déjà en place pour que le modèle l'étende plutôt
que de la reconstruire. Soumettre les 13 500 titres déjà classés pour
n'obtenir que des ajouts noierait le signal. La consigne est intégrée au
fichier, comme pour l'export complet.

La consigne embarquée énonce trois contraintes, qui ne sont pas des
précautions de style mais le reflet exact du code de rattachement :

| Contrainte | Pourquoi |
| --- | --- |
| Lister **chaque forme** d'un mot-clé | La correspondance ne tolère qu'un `s` ou un `x` final. `mix` n'attrape pas `mixing`, `master` n'attrape pas `mastering`. |
| Renvoyer la liste **complète** des mots-clés d'une sous-thématique reprise | L'import **remplace** la liste, il ne la fusionne pas : omettre un ancien mot-clé détacherait les articles qu'il retenait. |
| Éviter les mots trop larges | `test` ou `guide` attraperaient des centaines d'articles sans rapport et rendraient la navigation inutilisable. |

La deuxième est la plus coûteuse à découvrir soi-même : elle ne provoque
aucune erreur, seulement des articles qui disparaissent silencieusement d'une
sous-thématique.

**Déposer la réponse.** Le champ attend un **fichier** `.json` (2 Mo maximum),
pas un copier-coller. Enregistrez la réponse du modèle telle quelle, en
retirant l'habillage <code>```json</code> s'il en a mis — ce cas précis est
détecté et signalé plutôt que de produire une erreur incompréhensible. Les
scripts ou explications que certains modèles ajoutent spontanément n'ont
aucune utilité ici : seul le JSON compte.

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

**Avant une migration de schéma**

Aucune sauvegarde n'est prise automatiquement au démarrage. Cette protection a
existé du 11 au 13 septembre 2026, et coûtait plus qu'elle ne rapportait : neuf
minutes d'indisponibilité à chaque déploiement touchant le schéma, et un dump
que le redémarrage de PostgreSQL — inhérent au redéploiement — interrompait,
ce qui annulait la migration et laissait le backend boucler sans démarrer.

Ce qui protège réellement : le job CI `migrations`, qui rejoue toute la chaîne
Alembic sur une base vierge avant tout déploiement, et le service `db-backup`
ci-dessus. Pour une migration que vous jugez risquée, prenez un dump
manuellement avant de déployer.

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
| 0.30.2 | 2026-09-15 | Interface : coller le contenu à gauche quand la barre est repliée |
| 0.30.1 | 2026-09-15 | OCR : normaliser via Ghostscript quand qpdf ne suffit pas |
| 0.30.0 | 2026-09-15 | Navigation : barre latérale repliable, mise en cache des couvertures et PDF |
| 0.29.0 | 2026-09-15 | Sous-thématiques : rattachement au fil de l'eau et écran des orphelins |
| 0.28.1 | 2026-09-14 | Thématiques : passer les titres OCR à la ligne au lieu de les tronquer |
| 0.28.0 | 2026-09-14 | Thématiques : navigation à trois écrans sur la taxonomie |
| 0.27.1 | 2026-09-13 | Déploiement : supprimer la sauvegarde avant migration |
| 0.27.0 | 2026-09-13 | Thématiques : propager les tags de sujet et tirer la file au hasard |
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
