# Magazine Search

Application web auto-hébergée de gestion, OCR et recherche plein texte d'une collection de magazines PDF stockés sur un NAS (NFS). Voir [`cahier-des-charges-v2.md`](./cahier-des-charges-v2.md) pour la spécification complète.

## Fonctionnalités

- Scan manuel du NAS (déduplication par hash, détection de fichiers stables).
- Pipeline d'ingestion asynchrone : détection de texte natif, OCR conditionnel (`fra+eng`) via `ocrmypdf`/Tesseract, extraction des bounding boxes mot par mot, miniature de couverture.
- Recherche plein texte (Meilisearch) avec surlignage et filtres (titre, année, numéro).
- Viewer PDF intégré (`pdf.js`) avec saut direct à la page et overlay de surlignage des termes trouvés.
- Authentification multi-utilisateurs (admin + comptes standards), backoffice admin pour la gestion des comptes et du scan.

## Architecture

```
├── traefik            reverse proxy + TLS automatique (Let's Encrypt)
├── app-backend         FastAPI : API, auth, scan, admin
├── app-frontend         Next.js
├── worker               RQ : OCR + indexation
├── redis
├── postgres             Users, Magazines, Pages
├── meilisearch
```

## Prérequis

- Docker + Docker Compose v2.
- Un partage NAS monté en NFS sur l'hôte (lecture seule), contenant les PDF.
- Un nom de domaine pointant vers l'hôte si exposition hors LAN (pour Let's Encrypt via Traefik).

## Déploiement

1. Copier `.env.example` vers `.env` et renseigner toutes les valeurs (secrets, domaine, chemin NAS, etc.). `.env` ne doit jamais être commité.
2. Vérifier que `NAS_MOUNT_PATH` pointe vers un répertoire déjà monté en NFS sur l'hôte.
3. Démarrer la stack :

   ```bash
   docker compose up -d --build
   ```

4. Un compte admin est créé automatiquement au premier démarrage du backend à partir de `ADMIN_BOOTSTRAP_EMAIL` / `ADMIN_BOOTSTRAP_PASSWORD` (changez le mot de passe ensuite depuis le backoffice).
5. Se connecter, puis déclencher un premier scan depuis `/admin`.

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

## Hors scope V1

Segmentation en articles, auto-inscription/mot de passe oublié par email, watcher automatique du NAS, rôles avancés, écriture sur le NAS. Voir la section 6 du cahier des charges.

## Licence

MIT — voir [`LICENSE`](./LICENSE).
