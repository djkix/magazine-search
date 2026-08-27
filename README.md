# Magazine Search

Application web auto-hébergée de gestion, OCR et recherche plein texte d'une collection de magazines PDF stockés sur un NAS (NFS). Voir [`cahier-des-charges-v2.md`](./cahier-des-charges-v2.md) pour la spécification complète.

## Fonctionnalités

- Scan manuel du NAS (déduplication par hash, détection de fichiers stables).
- Pipeline d'ingestion asynchrone : détection de texte natif, OCR conditionnel (`fra+eng`) via `ocrmypdf`/Tesseract, extraction des bounding boxes mot par mot, miniature de couverture.
- Recherche plein texte (Meilisearch) avec surlignage et filtres (titre, année, numéro).
- Viewer PDF intégré (`pdf.js`) avec saut direct à la page et overlay de surlignage des termes trouvés.
- Extraction automatique du sommaire de chaque magazine via l'API Gemini (titre + page de chaque article), avec sommaire par magazine, vue globale de tous les articles de la collection, et correction manuelle depuis le viewer (admin).
- Authentification multi-utilisateurs (admin + comptes standards), backoffice admin pour la gestion des comptes et du scan.

## Architecture

```
├── app-backend         FastAPI : API, auth, scan, admin
├── app-frontend         Next.js
├── worker               RQ : OCR + indexation
├── redis
├── postgres             Users, Magazines, Pages
├── meilisearch
```

Le reverse proxy et la terminaison TLS (Let's Encrypt) ne sont **pas** gérés par ce `docker-compose.yml` : ils sont délégués à **Nginx Proxy Manager (NPM)**, déployé séparément sur l'hôte. Le navigateur ne parle qu'au frontend : `app-frontend` relaie en interne (via `next.config.js` → `rewrites()`) les appels `/api/*` vers `app-backend` sur le réseau Docker interne — NPM n'a donc besoin de forwarder qu'**un seul port** (`FRONTEND_PORT`), sans routage par chemin.

## Prérequis

- Docker + Docker Compose v2.
- Un partage NAS monté en NFS sur l'hôte (lecture seule), contenant les PDF.
- Nginx Proxy Manager (ou équivalent) déjà installé sur l'hôte, avec un nom de domaine pointant dessus si exposition hors LAN.

## Déploiement

1. Copier `.env.example` vers `.env` et renseigner toutes les valeurs (secrets, chemin NAS, ports, etc.). `.env` ne doit jamais être commité.
2. Vérifier que `NAS_MOUNT_PATH` pointe vers un répertoire déjà monté en NFS sur l'hôte.
3. Démarrer la stack :

   ```bash
   docker compose up -d --build
   ```

4. Dans NPM, créer un **Proxy Host** pour votre domaine :
   - Onglet *Details* : `Forward Hostname/IP` = IP de l'hôte Docker, `Forward Port` = `${FRONTEND_PORT}` (ex. `3001`). C'est tout — pas de *Custom Locations* à ajouter, `/api` est relayé en interne par le frontend.
   - Onglet *SSL* : activer Let's Encrypt + *Force SSL* (le cookie de session est `Secure`, donc l'app doit être servie en HTTPS).
5. Un compte admin est créé automatiquement au premier démarrage du backend à partir de `ADMIN_BOOTSTRAP_EMAIL` / `ADMIN_BOOTSTRAP_PASSWORD` (changez le mot de passe ensuite depuis le backoffice).
6. Se connecter, puis déclencher un premier scan depuis `/admin`.

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

- GitHub Actions construit et publie les images multi-stage sur GHCR (`ghcr.io/<user>/<repo>`) à chaque tag de version.
- Les releases (changelog + tag semver) sont gérées par `release-please` à partir des commits [Conventional Commits](https://www.conventionalcommits.org/).
- `gitleaks` tourne en pre-commit et en CI pour éviter toute fuite de secret.

## Versioning

- La version courante du projet est suivie dans [`.release-please-manifest.json`](./.release-please-manifest.json) et incrémentée automatiquement par `release-please` à chaque release (semver, déduit des [Conventional Commits](https://www.conventionalcommits.org/)).
- Le workflow `Build and publish images` calcule le numéro de version à partir du tag Git de la release et le publie :
  - comme tag d'image Docker sur GHCR (`ghcr.io/<user>/<repo>-backend:<version>`, `...-frontend:<version>`, en plus de `:latest`) ;
  - comme variable d'environnement de build `NEXT_PUBLIC_APP_VERSION` du frontend, affichée dans l'interface (sidebar, sous le logo) — pratique pour vérifier en un coup d'œil quelle version tourne sur un déploiement donné.
- L'historique complet des changements par version est dans [`CHANGELOG.md`](./CHANGELOG.md), généré et mis à jour automatiquement par `release-please` à chaque release.

## Hors scope V1

Segmentation en articles, auto-inscription/mot de passe oublié par email, watcher automatique du NAS, rôles avancés, écriture sur le NAS. Voir la section 6 du cahier des charges.

## Licence

MIT — voir [`LICENSE`](./LICENSE).
