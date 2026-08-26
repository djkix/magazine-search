# Cahier des charges — Application de gestion, OCR et recherche de magazines PDF

**Version :** 2.0
**Destinataire :** Claude Code
**Statut :** Prêt pour développement

---

## 1. Contexte & objectif

Développer une application web conteneurisée (Docker), auto-hébergée sur réseau local avec exposition possible hors LAN via reverse proxy, dédiée à la gestion, l'indexation OCR et la recherche plein texte d'une collection de magazines PDF hébergés sur un NAS (NFS, même réseau local).

L'application permet de scanner manuellement le répertoire NFS pour détecter de nouveaux PDF, d'en extraire/OCRiser le contenu texte page par page, et de fournir une recherche plein texte renvoyant directement à la page exacte du PDF, avec surlignage visuel des termes trouvés.

Usage : personnel + familial (comptes créés manuellement par l'admin, pas d'auto-inscription).

---

## 2. Spécifications fonctionnelles

### 2.1. Ingestion (scan manuel, pas de watcher automatique)

- **Pas d'upload utilisateur.** Les PDF résident sur un NAS, monté en NFS **en lecture seule** (`:ro`) dans les containers.
- **Déclenchement du scan : manuel uniquement**, via un bouton "Scanner le NAS" dans l'UI admin. Aucun scan automatique au démarrage ni de polling périodique.
- **Flux du scan :**
  1. `POST /api/admin/scan` (réservé admin) → lance le scan, retourne un `job_id`.
  2. Backend liste récursivement le répertoire NFS monté.
  3. Pour chaque `.pdf` : calcul du hash (SHA-256) et comparaison avec les `Magazines.file_hash` déjà en base → doublons ignorés.
  4. Nouveaux fichiers : vérification de stabilité (taille + mtime identiques à ~5-10s d'intervalle) pour éviter de traiter un fichier en cours de copie sur le NAS.
  5. Fichiers stables et nouveaux → statut `detected`, puis enqueue dans Redis/RQ pour traitement asynchrone.
  6. Réponse immédiate : nombre de nouveaux fichiers détectés + `job_id` pour suivre la progression.
- **Suivi de progression :** `GET /api/admin/scan/{job_id}/status` → nombre détectés / en cours d'OCR / terminés / échoués.

### 2.2. Traitement OCR et extraction

- **Détection texte natif** (PyMuPDF/`fitz`) avant tout appel OCR — ne pas OCRiser une page qui a déjà une couche texte exploitable.
- **OCR pour pages scannées** : `ocrmypdf` avec Tesseract, packs de langue **`fra+eng`** chargés simultanément (français dominant, anglais ~10% du contenu — pas de détection préalable stricte, laisser Tesseract arbitrer par page).
- **Extraction enrichie par page :**
  - Texte brut (`raw_text`).
  - **Bounding boxes mot par mot** (via `PyMuPDF get_text("words")` ou équivalent), stockées pour permettre le surlignage visuel dans le viewer — capture obligatoire dès la V1, pas un ajout ultérieur.
  - Langue détectée par page (`fr` / `en` / `mixed`), à titre informatif (filtrage, debug).
- **Segmentation en "articles" : hors scope V1.** L'indexation reste au niveau page — approche la plus robuste, pas de Layout Analysis (LayoutLM ou équivalent) en V1.
- **Traitement asynchrone obligatoire** (queue RQ + worker dédié) pour ne jamais bloquer l'UI ou saturer le serveur sur un batch de plusieurs magazines.
- **Génération d'une miniature de couverture** (rendu de la première page en image) pour l'affichage en grille.
- **Gestion des échecs :** statut détaillé par magazine (`detected` → `stable` → `queued` → `processing` → `done` / `failed`), avec message d'erreur stocké si échec (fichier corrompu, timeout, etc.).

### 2.3. Recherche plein texte

- **Moteur : Meilisearch** (choix tranché — highlighting natif, tolérance aux fautes de frappe, gestion accents/pluriels français sans configuration lourde, plus léger qu'Elasticsearch pour ce volume).
- Recherche par mots-clés, expressions exactes, filtres (titre du magazine, année, numéro).
- Résultats classés par pertinence, avec extrait (snippet) et surlignage des termes trouvés (fourni nativement par Meilisearch).
- Chaque résultat renvoie : magazine source, numéro de page, extrait, et les bounding boxes du/des mot(s) trouvé(s) sur cette page.

### 2.4. Consultation

- **Viewer intégré** via `pdf.js` (ou `react-pdf-viewer`), ouverture directe à la page cible (`magazine.pdf#page=X`).
- **Surlignage visuel** : overlay (SVG/canvas) positionné sur les bounding boxes du mot recherché, superposé au rendu PDF.
- **Téléchargement** du PDF d'origine (ou version OCRisée) possible pour les utilisateurs authentifiés.
- Accès aux fichiers PDF **jamais servi en statique direct** — toujours via le backend, avec vérification de session/droits.

### 2.5. Authentification & gestion des comptes

- **Multi-utilisateurs** : vous (admin) + membres de la famille (comptes standards).
- **Pas d'auto-inscription** — création de comptes exclusivement via backoffice admin.
- **Backoffice admin** (`/admin`, accès réservé `is_admin = true`) :
  - Créer un compte (email, nom affiché, mot de passe défini par l'admin).
  - Lister les comptes (email, dernière connexion, statut actif/inactif).
  - Désactiver/réactiver un compte.
  - Réinitialiser le mot de passe d'un compte (**reset manuel par l'admin, transmission directe du mot de passe — pas de flux email/SMTP en V1**).
  - Déclencher et suivre le scan NAS (fonctionnalité admin-only).
- **Comptes standards (famille)** : recherche, consultation, téléchargement uniquement. Pas d'accès au scan ni au backoffice.
- **Sécurité session :**
  - Mots de passe hashés (bcrypt ou argon2).
  - Session via JWT ou cookie `httpOnly`, `Secure`, `SameSite=Strict`.
  - Rate limiting sur `/api/login` (ex: 5 tentatives / 15 min / IP) — via middleware Traefik ou `slowapi` côté FastAPI.

---

## 3. Architecture technique

### 3.1. Backend
- **Framework :** Python / FastAPI.
- **Traitement PDF/OCR :** `ocrmypdf`, `pypdf`, `pdf2image`, `pytesseract`, `PyMuPDF` (`fitz`).
- **Auth :** JWT ou session cookie, bcrypt/argon2.
- **Queue :** Redis + RQ (worker séparé pour l'OCR).

### 3.2. Frontend
- **Framework :** Next.js + Tailwind CSS.
- **Composant PDF :** `pdfjs-dist` ou `react-pdf-viewer` + overlay de surlignage custom.

### 3.3. Recherche
- **Meilisearch** — index texte + payload bbox par résultat.

### 3.4. Infrastructure
- **Reverse proxy / TLS :** Traefik, certificats Let's Encrypt automatiques (auto-discovery via labels Docker). Remplace Nginx.
- **Conteneurisation :** Dockerfile multi-stage par service.
- **Montage NFS :** lecture seule (`:ro`), point de montage NAS non commité (dans `.env` local uniquement).

```
├── traefik            (reverse proxy + TLS auto)
├── app-backend        (FastAPI : API, auth, scan, admin)
├── app-frontend        (Next.js)
├── worker              (RQ : OCR + indexation)
├── redis
├── postgres            (Users, Magazines, Pages)
├── meilisearch
```

### 3.5. Hébergement & CI/CD (repo GitHub public)

- **Secrets :** aucun secret dans le repo. `.env` dans `.gitignore` dès le premier commit, `.env.example` fourni sans valeurs (inclut credentials DB, `MEILI_MASTER_KEY`, chemin NFS, email Let's Encrypt, domaine).
- **Pre-commit :** `gitleaks` ou `git-secrets` pour éviter tout leak accidentel.
- **CI/CD :** GitHub Actions — build multi-stage à chaque push sur `main`/tag, publication de l'image sur **GHCR** (`ghcr.io/<user>/<repo>`), tags `latest` + versions.
- **`docker-compose.yml`** : uniquement des références `${VAR_NAME}`, jamais de valeur en dur (y compris chemin NAS, IP, domaine).
- **README** : description, prérequis, instructions de déploiement (`.env.example` → `.env`, `docker compose up`). Tenu à jour à chaque évolution significative (pas seulement à l'init du repo).
- **LICENSE** : à trancher selon intention (MIT si réutilisation souhaitée, sinon mention "usage personnel").
- **Release notes automatiques** : génération d'un changelog à chaque release (tag de version), pas à chaque commit individuel — un commit isolé n'est pas une unité de communication pertinente pour un changelog.
  - Convention **Conventional Commits** (`feat:`, `fix:`, `chore:`, `docs:`, etc.) à adopter sur les messages de commit — c'est ce qui permet la génération automatique.
  - Outil recommandé : **release-please** (GitHub Action officielle Google) — ouvre automatiquement une PR de release avec changelog généré à partir des commits, incrémente la version selon semver, crée le tag + la GitHub Release au merge.
  - Alternative plus simple si vous préférez éviter la PR automatique : `git-cliff` ou `github-changelog-generator` déclenché manuellement à la création d'un tag.
  - Le build/publication d'image sur GHCR (déjà prévu) se déclenche sur ce même tag de version, pas sur chaque push — évite de publier une image à chaque commit.

---

## 4. Modèle de données

```
Users:
  id, email, password_hash, display_name, is_admin (bool),
  is_active (bool), created_at, last_login

Magazines:
  id, title, issue_number, publication_date, filename,
  file_path (chemin NFS), file_hash (SHA-256), file_size, file_mtime,
  cover_thumbnail_path,
  scan_status (detected/stable/queued/processing/done/failed),
  error_message (nullable),
  created_at

Pages:
  id, magazine_id, page_number, raw_text, language (fr/en/mixed),
  ocr_status (pending/processing/done/failed), error_message (nullable)

Words:
  id, page_id, text, bbox_x, bbox_y, bbox_w, bbox_h
  -- alternative : stocké en JSON dans Pages si le volume par page reste raisonnable,
  -- plutôt qu'une table dédiée (à évaluer selon perf réelle)
```

---

## 5. Livrables attendus

- `docker-compose.yml` clé en main (Traefik, backend, frontend, worker, redis, postgres, meilisearch), volumes persistants pour Postgres, Meilisearch, et point de montage NFS en lecture seule.
- Structure de projet complète : `backend/` (FastAPI), `frontend/` (Next.js), `.github/workflows/docker-build.yml`.
- Worker asynchrone d'ingestion (RQ) : détection texte natif → OCR conditionnel `fra+eng` → extraction texte + bbox → indexation Meilisearch.
- Backend :
  - Endpoints scan (`POST /api/admin/scan`, `GET /api/admin/scan/{job_id}/status`).
  - Endpoints admin utilisateurs (`POST/GET/PATCH/DELETE /api/admin/users`).
  - Endpoints auth (`POST /api/login`, gestion session).
  - Endpoints recherche (`GET /api/search`) et consultation (`GET /api/magazines/{id}/pages/{n}`, téléchargement).
- Frontend :
  - Page de login.
  - Barre de recherche + filtres + résultats avec snippets surlignés.
  - Viewer PDF intégré avec saut de page + overlay de surlignage.
  - Backoffice admin (gestion comptes + déclenchement/suivi scan).
- `.env.example`, `.gitignore`, `README.md`, `LICENSE`.

---

## 6. Hors scope V1 (explicitement écarté)

- Segmentation automatique en articles (Layout Analysis).
- Auto-inscription / self-service mot de passe oublié par email.
- Watcher automatique / polling périodique du NAS.
- Multi-rôles avancés (uniquement admin / standard).
- Écriture sur le NAS (montage strictement lecture seule).

---

## 7. Roadmap V2 (post-V1, non développé initialement)

Fonctionnalités candidates pour une itération future, classées par priorité indicative :

**Priorité haute (meilleur ratio valeur/effort, V1.5)**
1. **Favoris / marque-pages** — épingler des pages ou articles pour y revenir facilement.
2. **Mode "feuilletage" (flipbook)** — navigation page suivante/précédente fluide, hors contexte recherche.
3. **Notifications après scan** — email ou push à l'admin une fois le batch OCR terminé.
4. **Ré-OCR ciblé** — relancer l'OCR sur un magazine spécifique sans repasser tout le pipeline (utile si mauvaise qualité initiale).

**Priorité moyenne**
5. **Historique de recherche personnel** — retrouver ses dernières recherches par utilisateur.
6. **Recherche par plage de dates / décennie** — filtre timeline plutôt qu'un simple champ année.
7. **Tags/catégories manuels** — étiquetage libre des magazines (thématique, auteur récurrent, etc.).
8. **Statistiques de collection** — dashboard admin (nb magazines, pages indexées, mots les plus recherchés, stockage total).

**Priorité basse / exploratoire**
9. **Export des résultats de recherche** — liste de résultats en PDF/CSV pour un thème donné.
10. **Recherche par similarité visuelle de couverture** — retrouver un numéro par sa couverture (nécessite un modèle d'embedding image, effort significatif).
