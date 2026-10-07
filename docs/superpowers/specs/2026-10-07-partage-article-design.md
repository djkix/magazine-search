# Partage d'un article par lien

## Intention

Permettre de partager un article précis d'un numéro avec quelqu'un qui n'a
pas de compte, via un lien envoyé par un canal privé (WhatsApp en usage
prévu). La personne qui reçoit le lien doit arriver directement sur
l'article — pas sur l'écran de connexion, pas sur la bibliothèque — et
pouvoir le lire sans rien saisir.

**Contraintes posées par l'utilisateur, à ne pas réinterpréter :**
- L'unité partagée est l'**article**, pas le numéro entier.
- Diffusion exclusivement via un canal privé (WhatsApp) : le risque qu'un
  lien atteigne quelqu'un de non souhaité est jugé négligeable. Ça ne
  dispense pas de rendre le lien impossible à deviner, mais ça écarte le
  besoin d'expiration ou de révocation.
- Lecture **sans aucune authentification** : pas de cookie de session, pas
  de redirection vers `/login`.
- **Pas d'expiration, pas de révocation.** Le lien reste valide tant que
  l'article existe en base.
- Bouton "Partager" dans les listes d'articles existantes (panneau du
  lecteur, page "Sommaires" d'une collection) — pas dans la visionneuse
  elle-même.

## Vue d'ensemble

```
[Utilisateur connecté]                         [Destinataire du lien, sans compte]
       |                                                    |
       | clic "Partager" sur un article                     | ouvre le lien WhatsApp
       v                                                    v
POST /api/articles/{id}/share                    GET /partage/{token}  (page publique)
  -> crée/retrouve share_token                       -> GET /api/partage/{token}       (métadonnées)
  -> renvoie l'URL complète                           -> GET /api/partage/{token}/file  (PDF, par plages)
  -> copiée dans le presse-papiers                        -> affichage ouvert à start_page de l'article
```

## 1. Modèle de données

Colonne ajoutée à `Article` (`backend/app/models.py`) :

```python
share_token: Mapped[str | None] = mapped_column(String(43), unique=True, index=True, nullable=True)
```

- Nullable : la quasi-totalité des articles ne sont jamais partagés.
- Générée à la demande (`secrets.token_urlsafe(32)`, 43 caractères en
  base64 URL-safe) au premier clic sur "Partager" — pas à l'extraction du
  sommaire. Pas de table séparée : sans expiration ni révocation, il n'y a
  rien de plus à tracer qu'un champ sur la ligne existante.
- Migration `backend/alembic/versions/0017_article_share_token.py`
  (`down_revision` = la dernière migration en date au moment de l'implémentation —
  à vérifier contre `backend/alembic/versions/` à ce moment-là, pas figé ici).

**Pas de PDF découpé par article.** Une version envisagée un instant
proposait d'extraire les pages de l'article dans un petit fichier séparé,
généré au moment du partage. Écartée : l'objectif réel n'est pas de réduire
la taille du fichier servi, mais d'éviter que le destinataire **télécharge
tout le magazine d'un coup** pour lire un seul article — ce que le
streaming par plages HTTP (section 2/3) résout déjà, sans extraction ni
fichier supplémentaire à gérer.

## 2. Endpoints backend

### Authentifié (réutilise l'auth existante, n'importe quel utilisateur actif)

```
POST /api/articles/{id}/share
```
- Idempotent : si `article.share_token` existe déjà, le renvoie tel quel ;
  sinon le génère, le persiste, le renvoie.
- Réponse : `{"token": "...", "url": "<origine publique>/partage/<token>"}`.
  L'origine publique est construite à partir de la requête entrante
  (`request.base_url` ou équivalent FastAPI), pas d'une variable d'env
  séparée — cohérent avec le fait que l'app ne connaît déjà son propre
  domaine public nulle part ailleurs dans le code.
- 404 si l'article n'existe pas (même comportement que les autres routes
  `/articles/{id}`).

### Publics, nouveau routeur SANS dépendance d'authentification

```
GET /api/partage/{token}        -> métadonnées (titre article, titre magazine,
                                    nom de collection, start_page, end_page)
GET /api/partage/{token}/file   -> PDF du magazine, par plages HTTP
```
- Nouveau fichier `backend/app/routers/partage.py`, `APIRouter()` sans
  `Depends(get_current_user)` — contrairement à `magazines.py` et
  `articles.py` dont le routeur entier exige une session.
- Résolution : `db.query(Article).filter(Article.share_token == token).first()`.
  Token inconnu → 404 générique (`"Lien introuvable."`), indiscernable d'un
  token qui n'a jamais existé.
- `/file` réutilise **telle quelle** `_servir_pdf()` déjà écrite dans
  `backend/app/routers/magazines.py` (gestion des plages HTTP, 206/416,
  `Accept-Ranges`) — pas de dépendance au cookie de session dans cette
  fonction, elle prend déjà le chemin du fichier et les en-têtes en
  paramètres. Pas de réécriture, juste un nouvel appelant, avec les mêmes
  `disposition="inline"` et `cache=CACHE_PDF` que l'endpoint `/file`
  authentifié existant. **Sert le PDF du magazine entier**, pas un extrait :
  c'est le streaming par plages ci-dessous, pas la taille du fichier, qui
  évite au destinataire de tout télécharger.
- Monté dans `backend/app/main.py` avec le même préfixe `/api` que les
  autres routeurs, tag `["partage"]`.

## 3. Frontend

### Bouton "Partager"

Ajouté sur chaque ligne d'article dans :
- `frontend/components/viewer/ViewerMetaPanel.tsx` (liste des articles du
  numéro ouvert dans le lecteur)
- `frontend/app/(app)/articles/collection/[collectionId]/page.tsx` (page
  "Sommaires" d'une collection)

Comportement : clic → `api.post<{token: string; url: string}>("/articles/{id}/share")`
→ `navigator.clipboard.writeText(url)` → confirmation visuelle brève (tooltip
ou changement d'icône temporaire, à l'image des autres confirmations déjà
présentes dans l'admin). Pas de modale, pas d'écran dédié.

### Page publique

Nouvelle route `frontend/app/partage/[token]/page.tsx`, **en dehors du
groupe `(app)`** : pas d'`AppShell`, pas de `UserContext`, aucune des
redirections vers `/login` qui s'appliquent au reste de l'application.

Contenu :
- Appelle `GET /api/partage/{token}` pour les métadonnées ; 404 → message
  "Ce lien n'est plus disponible." sans détail technique.
- Réutilise le composant `frontend/components/viewer/PdfViewer.tsx` tel
  quel (il prend déjà `fileUrl`, `pageNumber`, `zoom`, `highlightWords` en
  props, découplé de toute logique d'authentification), pointé sur
  `/api/partage/{token}/file`, ouvert à `start_page` de l'article.
- Navigation minimale : page précédente/suivante, zoom. **Pas** de
  `ViewerMetaPanel`, pas de `ViewerSearchPanel`, pas de sommaire, pas de
  lien vers le reste de la bibliothèque — la personne qui ouvre ce lien
  n'a accès à rien d'autre que ce PDF.
- **Nouveau prop sur `PdfViewer`** : `disableAutoFetch?: boolean` (défaut
  `false`, comportement actuel du lecteur authentifié inchangé). pdf.js
  utilise déjà les plages HTTP pour ne charger que les pages affichées
  (`getDocument({ url, withCredentials: true })`, aucune option qui
  désactive le streaming), mais son réglage par défaut continue de charger
  le **reste** du document en tâche de fond une fois les pages visibles
  rendues — pas "d'un coup", mais ça finit par tout récupérer si la page
  reste ouverte. Sur la page de partage, `disableAutoFetch={true}` : seules
  les pages que la personne consulte réellement sont jamais demandées au
  serveur, jamais le magazine entier.

## 4. Cas limites et limites connues

- **Token inconnu** : 404 générique, même traitement qu'une route qui
  n'existerait pas.
- **Numéro ré-traité** : `extract_and_store_articles()` recrée les lignes
  `Article` à chaque nouvelle extraction de sommaire
  ([tasks.py](../../../backend/app/worker/tasks.py)) — un `share_token`
  disparaît donc avec l'ancienne ligne. Un lien partagé avant un nouveau
  traitement du numéro cessera de fonctionner silencieusement (404). Limite
  acceptée telle quelle, cohérente avec la demande ("pas de risque,
  diffusion ponctuelle") — pas de mécanisme de migration de token prévu.
- **Force brute** : le token fait 256 bits d'entropie ; le deviner est hors
  de portée. Pas de limite de débit dédiée sur les routes publiques.
- **Suppression du magazine/article** : cascade déjà existante au niveau
  base (`ON DELETE CASCADE` sur les FK d'`Article`) — un lien pointant vers
  un article supprimé renvoie naturellement 404 sans code spécial.

## 5. Tests

`backend/tests/test_partage.py` (base SQLite en mémoire, pas de serveur
HTTP réel nécessaire pour la plupart des cas) :
- `POST /articles/{id}/share` appelé deux fois sur le même article renvoie
  le même token (idempotence).
- `GET /partage/{token}` avec un token inconnu → 404.
- `GET /partage/{token}` avec un token valide → métadonnées correctes
  (titre, magazine, collection, pages).
- Le service de fichier par plages (`_servir_pdf`) est déjà couvert par son
  usage existant dans `magazines.py` ; seule la résolution token → article
  est un comportement réellement nouveau à tester ici.

Côté frontend : `npx tsc --noEmit -p .` suffit (pas de runner de tests dans
ce projet, confirmé lors d'un travail précédent sur l'auth Google).

## Hors périmètre (explicitement écarté)

- Expiration automatique des liens.
- Révocation manuelle depuis l'admin.
- Partage d'un numéro entier plutôt que d'un seul article (c'était la
  première formulation de la demande, remplacée par celle-ci).
- Restriction par email/domaine du destinataire.
- Tout compteur de consultation ou analytics sur les liens partagés.
