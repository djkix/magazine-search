# Magazine Search

Application web auto-hébergée de gestion, OCR et recherche plein texte d'une collection de magazines PDF stockés sur un NAS (NFS).

Voir [`cahier-des-charges-v2.md`](./cahier-des-charges-v2.md) pour la spécification complète.

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Architecture](#architecture)
- [Stack technique](#stack-technique)
- [Prérequis](#prérequis)
- [Déploiement](#déploiement)
- [Configuration](#configuration)
- [Utilisation](#utilisation)
- [Développement local](#développement-local)
- [CI/CD](#cicd)
- [Versioning et changelog](#versioning-et-changelog)
- [Hors scope V1](#hors-scope-v1)
- [Licence](#licence)

## Fonctionnalités

- **Scan du NAS** : détection des nouveaux PDF, déduplication par hash de contenu, attente de stabilité du fichier avant traitement (évite de traiter un fichier encore en cours de copie).
- **Pipeline d'ingestion asynchrone** (file RQ) : détection de texte natif, OCR conditionnel (`fra+eng`) via `ocrmypdf`/Tesseract, extraction des bounding boxes mot par mot pour le surlignage, génération d'une miniature de couverture. Le texte extrait est nettoyé des caractères NUL parfois produits par un mapping de police corrompu, qui feraient sinon échouer tout l'enregistrement du numéro en base. Un mapping de police corrompu peut aussi produire du texte non-nul mais illisible (ex. "lll Why | | | Il Ill") au lieu d'échouer franchement - indétectable par la seule présence de texte, donc détecté séparément par la densité de mots courants français/anglais (« le », « la », « the », « and »...) sur chaque page : si assez de pages en manquent, l'OCR réel est forcé sur tout le document (`--force-ocr`, qui réécrit le texte même là où il existe déjà) plutôt que sauté (`--skip-text`, qui aurait laissé les pages déjà "non vides" telles quelles). Ce contrôle ne coûte qu'un balayage de texte déjà extrait, et le forçage de l'OCR ne se déclenche (et ne coûte du temps) qu'une fois, au premier traitement du numéro concerné.
- **Collections et tags** :
  - une **collection** (ex. « Que Choisir ») regroupe automatiquement tous les numéros d'un même titre, déduite du répertoire de premier niveau sous la racine du NAS lors du scan (y compris si un numéro est déplacé vers un autre répertoire par la suite, ou rangé dans un sous-dossier par année/Hors-Séries) ;
  - un **tag** (ex. « Bricolage », « Guide achat ») est créé et géré à la main dans l'admin, et peut regrouper plusieurs collections — une collection peut elle-même porter plusieurs tags.
- **Bibliothèque et sommaires en deux niveaux** : parcours par collection (couverture représentative + nombre de numéros), puis détail des numéros — numéro, mois (ou plage de mois pour un bimestriel, ex. « Septembre-Octobre »), année (cliquable pour filtrer) et indicateur Hors-Série/Spécial, tous déduits automatiquement du nom de fichier — ou du sommaire de la collection sélectionnée, triable par date ou par type. Une colonne latérale liste les années présentes dans la collection ainsi que les Hors-Séries/Numéros Spéciaux, chacun cliquable pour filtrer la grille — même colonne, même comportement, sur la vue « Sommaires » d'une collection. Pour un Hors-Série/Spécial dont le nom de fichier ne porte ni date ni numéro (courant pour une édition nommée par son thème), l'année et le numéro sont recherchés en repli dans le texte déjà extrait par l'OCR de la couverture.
- **Thématiques automatiques** (optionnel, Gemini) : une fois les sommaires extraits, Gemini regroupe plusieurs numéros par requête (par lots de 8) et leur attribue 1 à 3 thématiques (ex. « Automobile », « Santé ») en réutilisant le vocabulaire déjà en place dans le reste de la bibliothèque pour éviter les quasi-doublons — c'est le seul appel Gemini de tout le pipeline d'ingestion. Sur `/articles`, l'onglet « Par thématique » d'une collection les liste (regroupées, avec un compteur de numéros) — cliquer une thématique affiche les numéros concernés. Un bouton « Régénérer les thématiques » dans les réglages admin permet de forcer une nouvelle génération, y compris pour les numéros qui en ont déjà.
- **Recherche plein texte** (Meilisearch) avec surlignage des termes, filtres (titre, année, numéro, un ou plusieurs tags — la recherche se limite alors aux collections associées à ces tags), un résultat par magazine (avec son nombre d'occurrences du terme recherché, colorée du gris au vert selon son poids relatif) plutôt qu'un par page, classés par pertinence puis par fraîcheur.
- **Extraction automatique du sommaire** (titre + page de chaque article), entièrement locale : le texte répétitif (en-tête/pied de page reproduit sur presque chaque page, quel que soit son contenu) est ensuite détecté et écarté, la page sommaire est repérée (mot « SOMMAIRE »/« CONTENTS »/« SUMMARY »/« INDEX », y compris en typographie espacée ou en plusieurs mots, cherché jusqu'à la page 30 pour les magazines au sommaire tardif, ou à défaut la page la plus dense en entrées parmi les 8 premières), et les entrées sont enfin extraites par reconnaissance de motif — points de suite (y compris quand chaque point est séparé par une espace fine, un artefact d'OCR courant sur ce type de mise en page), alignement tabulaire, numéro de page en tête ou dans son propre encart après le titre — directement sur le texte déjà OCRisé, sans aucun appel Gemini — donc instantanée, gratuite et jamais bloquée par un quota. Comme un sommaire en vraie mise en page à colonnes peut donner avec le texte linéaire non pas zéro résultat mais une unique entrée mal fusionnée (dont la page de fin s'étend jusqu'à la fin du magazine — un faux « succès » si on ne teste que l'absence de résultat), deux reconstructions alternatives de l'ordre de lecture (par colonnes, puis par bandes horizontales) sont systématiquement tentées en plus de la lecture linéaire sur la page identifiée comme le sommaire, et c'est la variante ayant trouvé le plus d'entrées qui est retenue. L'extraction verrouille la ligne du magazine pendant le remplacement de ses articles, pour qu'une relance déclenchée deux fois pour le même numéro (ex. « Relancer » et un retry TOC qui se chevauchent) ne finisse pas par insérer les deux jeux d'articles côte à côte en double - et un bouton « Supprimer les articles en double » dans le tableau de bord nettoie ceux déjà en base. Vue globale de tous les articles, et correction manuelle depuis le viewer (admin). Un échec d'extraction (bug de traitement) est distingué d'un sommaire réellement vide et affiché comme tel (avec possibilité de relancer), aussi bien dans le viewer que dans la vue « Sommaires » par collection. Seule l'attribution des thématiques passe encore par Gemini (voir ci-dessus) ; un quota Gemini journalier auto-géré (configurable dans les réglages, 20 requêtes/jour par défaut pour coller au tier gratuit) évite de dépasser la limite du compte, avec une limite de requêtes/minute (5 par défaut) qui fait patienter l'app plutôt que d'insister quand elle est atteinte, pour ne jamais risquer de se faire limiter plus sévèrement par Google pour abus. Les réglages affichent la consommation du jour pour vérifier en un coup d'œil si le quota est encore disponible. Modèle Gemini configurable depuis l'admin.
- **Viewer PDF intégré** (`pdf.js`) en défilement continu, saut direct à une page ou à un article du sommaire, overlay de surlignage des termes recherchés. En arrivant depuis un résultat de recherche, la colonne de gauche liste les autres magazines correspondant à la même recherche (avec leur nombre d'occurrences) pour naviguer entre eux sans revenir à la page de recherche. Le PDF est chargé par requêtes HTTP Range (le serveur les honore nativement) : `pdf.js` ne télécharge que les octets nécessaires à la page affichée plutôt que tout le fichier (30-75 Mo) d'un coup, ce qui accélère surtout l'ouverture sur mobile.
- **Authentification multi-utilisateurs** (admin + comptes standards), sessions JWT invalidées automatiquement à la réinitialisation d'un mot de passe.
- **Backoffice admin** : tableau de bord auto-rafraîchi (compteurs et vue filtrée toutes les 5 secondes, pour ne jamais afficher un statut périmé pendant qu'un scan avance en arrière-plan), avec un pourcentage de progression (page en cours / nombre total de pages) pour le magazine en cours de traitement plutôt qu'un simple badge « en cours » sans indication d'avancement, barre de progression du scan en cours (reprise automatique à l'écran si un scan était déjà en cours), « Activité récente » triée et horodatée (date + heure) par dernière activité réelle du magazine plutôt que par date d'ajout initiale — un numéro remis en file par une relance apparaît donc en tête, pas coincé au milieu de numéros ajoutés le même jour, compteurs cliquables (terminés/en file d'attente/en cours/échecs/sans sommaire) qui filtrent la liste des magazines sur ce statut, sans limite d'ancienneté, pour identifier et relancer directement les numéros concernés (individuellement, ou tous d'un coup pour les « sans sommaire », utile après une amélioration de l'extraction pour rattraper toute la bibliothèque déjà scannée), avec pagination (« Charger plus ») au-delà des 100 premiers résultats pour rester utilisable avec une grosse bibliothèque ; le recalcul des collections/sommaires tourne en arrière-plan plutôt que dans la requête admin, pour ne pas expirer sur une bibliothèque de plusieurs centaines de numéros. Le scan ne relit et ne rehash que les fichiers réellement nouveaux ou modifiés (taille/date inchangées = ignoré), pour que son coût suive la taille du NAS ajoutée plutôt que la taille totale de la bibliothèque ; gestion des comptes, relance d'un scan/OCR par magazine, page de logs applicatifs filtrable (niveau, composant) avec rotation (le fichier de sauvegarde après rotation reste consultable, pas seulement le courant ; les traces d'exception y sont conservées), réglages (modèle Gemini, tags et rattachement des collections, réindexation manuelle du moteur de recherche). Un job d'OCR interrompu par dépassement de délai (fichier trop volumineux ou corrompu) est automatiquement marqué en échec au lieu de rester bloqué indéfiniment en « en cours » ; un numéro resté « en cours » parce que le worker a été arrêté en plein traitement (ex. redéploiement) est de la même façon récupéré et marqué en échec au redémarrage du worker, ce qui débloque aussi la barre de progression du scan qui l'attendait indéfiniment.

## Architecture

```
├── app-backend         FastAPI : API, auth, scan, admin
├── app-frontend        Next.js
├── worker               RQ : OCR + indexation + extraction du sommaire
├── redis                 file de tâches RQ
├── postgres              utilisateurs, magazines, pages, tags, collections
├── meilisearch            index de recherche plein texte
```

Le reverse proxy et la terminaison TLS (Let's Encrypt) ne sont **pas** gérés par ce `docker-compose.yml` : ils sont délégués à **Nginx Proxy Manager (NPM)**, déployé séparément sur l'hôte. Le navigateur ne parle qu'au frontend : `app-frontend` relaie en interne (via `next.config.js` → `rewrites()`) les appels `/api/*` vers `app-backend` sur le réseau Docker interne — NPM n'a donc besoin de forwarder qu'**un seul port** (`FRONTEND_PORT`), sans routage par chemin.

## Stack technique

| Composant | Techno |
| --- | --- |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2 |
| Frontend | Next.js 14 (App Router), React 18, Tailwind CSS |
| Files d'attente | RQ (Redis Queue) |
| Recherche | Meilisearch |
| OCR | `ocrmypdf` / Tesseract (`fra+eng`) |
| Extraction de sommaire | API Google Gemini (`google-genai`) |
| Viewer PDF | `pdf.js` |
| Base de données | PostgreSQL 16 |
| Déploiement | Docker Compose, images publiées sur GHCR |

## Prérequis

- Docker + Docker Compose v2.
- Un partage NAS monté en NFS sur l'hôte (lecture seule), contenant les PDF, organisé en un répertoire de premier niveau par titre de magazine (ce nom devient automatiquement le nom de la collection) — les PDF peuvent être rangés directement dedans ou dans des sous-dossiers (par année, Hors-Séries, etc.), ces sous-dossiers n'affectent pas le nom de la collection mais un sous-dossier "Hors Séries"/"Numéros Spéciaux" est détecté pour marquer le numéro comme tel.
- Nginx Proxy Manager (ou équivalent) déjà installé sur l'hôte, avec un nom de domaine pointant dessus si exposition hors LAN.
- Une clé API Google Gemini si vous souhaitez l'extraction automatique des sommaires (fonctionnalité optionnelle).

## Déploiement

1. Copier `.env.example` vers `.env` et renseigner toutes les valeurs (secrets, chemin NAS, ports, etc.). `.env` ne doit jamais être commité.
2. Vérifier que `NAS_MOUNT_PATH` pointe vers un répertoire déjà monté en NFS sur l'hôte.
3. Démarrer la stack :

   ```bash
   docker compose up -d
   ```

4. Dans NPM, créer un **Proxy Host** pour votre domaine :
   - Onglet *Details* : `Forward Hostname/IP` = IP de l'hôte Docker, `Forward Port` = `${FRONTEND_PORT}` (ex. `3001`). C'est tout — pas de *Custom Locations* à ajouter, `/api` est relayé en interne par le frontend.
   - Onglet *SSL* : activer Let's Encrypt + *Force SSL* (le cookie de session est `Secure`, donc l'app doit être servie en HTTPS).
5. Un compte admin est créé automatiquement au premier démarrage du backend à partir de `ADMIN_BOOTSTRAP_EMAIL` / `ADMIN_BOOTSTRAP_PASSWORD` (changez le mot de passe ensuite depuis le backoffice).
6. Se connecter, puis déclencher un premier scan depuis `/admin`.

## Configuration

Toutes les variables sont documentées dans [`.env.example`](./.env.example). Les principales :

| Variable | Description |
| --- | --- |
| `NAS_MOUNT_PATH` | Chemin hôte du partage NAS monté en NFS (lecture seule). |
| `FRONTEND_PORT` | Seul port à forwarder depuis le reverse proxy. |
| `BACKEND_CORS_ORIGINS` | Domaine public exact (schéma inclus) sur lequel l'app est exposée. |
| `JWT_SECRET_KEY` | Secret de signature des sessions — à générer aléatoirement. |
| `MEILI_MASTER_KEY` | Clé maître Meilisearch — à générer aléatoirement. |
| `ADMIN_BOOTSTRAP_EMAIL` / `ADMIN_BOOTSTRAP_PASSWORD` | Compte admin créé au premier démarrage. |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Optionnel — active l'extraction automatique des sommaires. Le modèle est aussi modifiable depuis l'admin sans redéploiement. |

## Utilisation

- **Scanner le NAS** : depuis `/admin`, bouton « Scan ». Les nouveaux PDF stables sont détectés, dédupliqués par hash, puis OCRisés et indexés en tâche de fond ; un PDF déplacé vers un autre répertoire est retrouvé par son contenu et son chemin/sa collection corrigés automatiquement. La progression s'affiche en temps réel sur le tableau de bord.
- **Organiser en tags** : depuis `/admin/settings`, créez vos tags (ex. « Bricolage ») et rattachez-y une ou plusieurs collections détectées automatiquement (ex. « Que Choisir », « 60 Millions de consommateurs ») en cliquant dessus.
- **Rechercher** : `/search` — recherche plein texte avec filtres par titre, année, numéro et tags (cliquez un ou plusieurs tags pour limiter la recherche aux collections qui leur sont associées) ; un résultat par magazine, classé par nombre d'occurrences puis par fraîcheur.
- **Parcourir** : `/library` et `/articles` (sommaires) présentent d'abord les collections, puis le détail des numéros (paginé, taille de page réglable) ou des thématiques de la collection choisie.

## Développement local

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

Un `docker-compose.yml` complet est le moyen recommandé de lancer l'ensemble des services (Postgres, Redis, Meilisearch inclus) même en développement.

## CI/CD

- Chaque push sur `main` construit et publie les images `backend`/`frontend` sur GHCR (`ghcr.io/<user>/<repo>-backend:latest`, `...-frontend:latest`) — pas de workflow de pull request bloquant, publication directe.
- `release-please` propose périodiquement une pull request de release regroupant les commits [Conventional Commits](https://www.conventionalcommits.org/) depuis la dernière version ; la fusionner crée un tag semver, met à jour `CHANGELOG.md`, et republie les images taguées avec ce numéro de version (en plus de `:latest`).
- `gitleaks` tourne en pre-commit et en CI pour éviter toute fuite de secret.

## Versioning et changelog

- La version courante est suivie dans [`.release-please-manifest.json`](./.release-please-manifest.json).
- **L'historique complet des changements par version est dans [`CHANGELOG.md`](./CHANGELOG.md)**, généré et mis à jour automatiquement par `release-please` à chaque release fusionnée.
- La version affichée dans l'interface (sidebar, sous le logo) correspond à la dernière release réellement publiée, pas au dernier commit poussé sur `main` — les changements les plus récents peuvent donc être en avance sur ce numéro tant que la PR de release correspondante n'a pas été fusionnée.

## Hors scope V1

Segmentation en articles par OCR structurel (remplacée par l'extraction Gemini du sommaire), auto-inscription/mot de passe oublié par email, watcher automatique du NAS (le scan reste déclenché manuellement), rôles avancés, écriture sur le NAS. Voir la section 6 du cahier des charges.

## Licence

MIT — voir [`LICENSE`](./LICENSE).
