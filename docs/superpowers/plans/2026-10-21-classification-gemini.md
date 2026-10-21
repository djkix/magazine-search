# Classification automatique par Gemini : plan d'implémentation

> **Pour l'exécutant :** utiliser superpowers:executing-plans, tâche par tâche, en TDD (test rouge, puis code, puis test vert). Cases à cocher pour le suivi.
>
> **Pas de commit dans ce plan.** La règle du dépôt (mémoire utilisateur) interdit tout commit sans consigne explicite : on termine sur l'arbre de travail modifié et vérifié.

**Objectif :** après un scan, un modèle Gemini classe les articles orphelins dans la taxonomie (en créant des sous-thématiques au besoin), sans dépasser les quotas, et le tableau de bord explique les pauses.

**Architecture :** une tâche RQ `classer_orphelins_task`, mise en file à la fin de l'extraction d'un sommaire, envoie des lots d'articles à Gemini. Un suivi de quota dans Redis (`SuiviQuota`) autorise ou refuse chaque requête et porte l'état de pause. La reprise est un job RQ différé (`enqueue_at`). Un endpoint admin expose l'état, un bandeau du tableau de bord l'affiche.

**Stack :** FastAPI, SQLAlchemy/Alembic, RQ/Redis, `google-genai==2.20.0` (version utilisée avant le retrait), Next.js.

**Spec :** `docs/superpowers/specs/2026-10-21-classification-gemini-design.md`

## Contraintes globales

- Modèle par défaut `gemini-3.8-flash` (`GEMINI_MODEL`). Limites par défaut `GEMINI_RPM=5`, `GEMINI_TPM=250000`, `GEMINI_RPD=20`, réserve de 2 requêtes/jour.
- Sans `GEMINI_API_KEY` : tout est inactif et silencieux, comportement actuel inchangé.
- Un échec Gemini ne fait jamais échouer l'extraction d'un sommaire.
- Lots : au plus 300 articles et 100 000 tokens estimés par requête (≈ 4 caractères par token).
- Mots-clés d'une nouvelle sous-thématique : 8 au plus, 4 caractères minimum, minuscules, écarté si présent dans plus de 2 % des titres du corpus.
- 3 réponses mal formées consécutives : pause d'1 heure (`format_invalide`). Une réponse mal formée compte comme requête consommée.
- Nouvelles sous-thématiques uniquement sous une thématique existante ; jamais de nouvelle thématique.
- Jour de quota = jour `America/Los_Angeles` ; reprise affichée en heure locale du navigateur.
- Commentaires et messages utilisateur en français. Tests pytest : voir « Commandes » en bas.

## Review Focus

- Clé API absente : le hook ne met rien en file et l'endpoint renvoie `actif: false` (tâche 5 et 6).
- Réponse avec des `article_id` hors du lot ou des `sous_thematique_id` inconnus : ignorés, sans crash (tâche 3).
- Même nom de sous-thématique à la casse ou aux accents près : réutilisée, pas dupliquée (tâche 3).
- Retraitement d'un sommaire et `recalculer_tout` : les liens `source='gemini'` survivent (tâche 1).
- Passage de minuit heure du Pacifique, y compris changement d'heure : compteur et heure de reprise corrects (tâche 2).
- Taxonomie volumineuse ou 1 000 articles : lots découpés sous 100 000 tokens (tâche 3).
- Réponse 429 : pause posée, aucune nouvelle tentative, articles toujours candidats (tâche 4).

---

### Task 1: Schéma et préservation des liens Gemini

**Files:**
- Create: `backend/alembic/versions/0019_classification_gemini.py`
- Modify: `backend/app/models.py` (table `subtheme_articles`, classe `Article`)
- Modify: `backend/app/services/import_sous_thematiques.py` (`rattacher`, `rattacher_magazine`)
- Test: `backend/tests/test_classification_gemini.py` (créé ici)

**Interfaces:**
- Produces: colonne `articles.classe_par_gemini_le` (`DateTime(timezone=True)`, nullable) ; colonne `subtheme_articles.source` (`String(16)`, `NOT NULL`, défaut `'mots_cles'`, valeurs `'mots_cles'` ou `'gemini'`).

- [ ] **Step 1: Test rouge** `test_rattacher_magazine_preserve_les_liens_gemini` : base SQLite en mémoire (fixture `db_session` comme `tests/test_admin_stats.py`), un magazine avec 2 articles, une sous-thématique ; un lien `source='gemini'` sur l'article A et un lien `source='mots_cles'` sur l'article B ; appeler `rattacher_magazine(db, magazine.id)` ; asserter que le lien Gemini de A existe toujours et que le lien de B (non retrouvé par les mots-clés) a disparu. Second test `test_rattacher_preserve_les_liens_gemini` : `rattacher(..., appliquer=True)` ne supprime que les liens `mots_cles` de la sous-thématique.
- [ ] **Step 2:** lancer les deux tests, attendre l'échec (colonne `source` inconnue).
- [ ] **Step 3:** ajouter les deux colonnes dans `models.py` (la `Table` `subtheme_articles` reçoit `Column("source", String(16), nullable=False, server_default="mots_cles")`) ; écrire la migration `0019` (`down_revision = "0018"`, `add_column` pour les deux colonnes, `drop_column` au downgrade, `server_default` sur `source`) ; dans `rattacher_magazine` et `rattacher`, ajouter `.where(subtheme_articles.c.source == "mots_cles")` aux deux `delete()` ; les `insert()` existants prennent la valeur par défaut.
- [ ] **Step 4:** tests verts ; vérifier la migration hors ligne : `alembic upgrade 0018:0019 --sql` et `alembic downgrade 0019:0018 --sql` (aucune Postgres disponible), sorties plausibles.

### Task 2: Configuration et suivi de quota

**Files:**
- Modify: `backend/app/config.py` (champs Gemini), `backend/requirements.txt` (`google-genai==2.20.0`, et `tzdata` s'il n'y est pas déjà), `.env.example`
- Create: `backend/app/services/gemini_quota.py`, `backend/tests/faux_redis.py`
- Test: `backend/tests/test_gemini_quota.py`

**Interfaces:**
- Produces, dans `config.py` (`Settings`) : `gemini_api_key: str = ""`, `gemini_model: str = "gemini-3.8-flash"`, `gemini_timeout_seconds: int = 120`, `gemini_rpm: int = 5`, `gemini_tpm: int = 250000`, `gemini_rpd: int = 20`.
- Produces, dans `gemini_quota.py` :
  - constantes de raison : `QUOTA_JOUR = "quota_jour"`, `QUOTA_MINUTE = "quota_minute"`, `CLE_INVALIDE = "cle_invalide"`, `MODELE_INTROUVABLE = "modele_introuvable"`, `FORMAT_INVALIDE = "format_invalide"`, `ERREUR_API = "erreur_api"`, `RESERVE_JOUR = 2`
  - `class Pause(NamedTuple): raison: str; jusqua: datetime` (`jusqua` aware, UTC)
  - `prochaine_reinitialisation(maintenant: datetime) -> datetime` : prochain minuit `America/Los_Angeles`, rendu en UTC
  - `class SuiviQuota` : `__init__(self, redis, rpm: int, rpd: int, tpm: int, maintenant: Callable[[], datetime] = lambda: datetime.now(timezone.utc))` ; `requetes_aujourdhui(self) -> int` ; `limite_jour_effective(self) -> int` (`rpd - RESERVE_JOUR`) ; `pause_active(self) -> Pause | None` ; `poser_pause(self, raison: str, jusqua: datetime) -> None` ; `autoriser(self, tokens_estimes: int) -> Pause | None` (rend `None` si la requête peut partir, sinon la `Pause` à appliquer) ; `enregistrer(self, tokens: int) -> None` (compte une requête et ses tokens, minute et jour)
- `FauxRedis` (tests) : dict en mémoire avec `get`, `set(nom, valeur, ex=None, nx=False)`, `incr`, `incrby`, `expire`, `delete`, `ttl` ; les clés expirent d'après une horloge injectable.

- [ ] **Step 1: Tests rouges** (`test_gemini_quota.py`, horloge injectée) : `test_autorise_sous_les_limites` ; `test_refuse_quand_le_budget_du_jour_est_atteint` (après 18 `enregistrer`, `autoriser` rend `Pause(QUOTA_JOUR, prochaine_reinitialisation(now))`) ; `test_refuse_a_la_sixieme_requete_de_la_minute` (`QUOTA_MINUTE`, `jusqua` = début de la minute suivante) ; `test_refuse_si_les_tokens_depassent_la_minute` ; `test_compteur_du_jour_repart_apres_minuit_pacifique` (23:59 puis 00:01 heure du Pacifique, en hiver et en été, `requetes_aujourdhui` repasse à 0) ; `test_prochaine_reinitialisation_gere_le_changement_d_heure` (veille et lendemain du passage à l'heure d'été, écart de 8 h au lieu de 7) ; `test_pause_posee_est_relue_puis_expire` ; `test_pause_active_ignore_une_pause_echue`.
- [ ] **Step 2:** vérifier l'échec (module absent).
- [ ] **Step 3:** implémenter. Clés Redis : `gemini:rpd:<AAAA-MM-JJ Pacifique>` (TTL 26 h), `gemini:rpm:<minute epoch>` et `gemini:tpm:<minute epoch>` (TTL 120 s), `gemini:pause` (JSON `{raison, jusqua}`, TTL jusqu'à `jusqua`). `autoriser` teste dans l'ordre pause active, jour, minute, tokens. Ajouter les champs à `Settings` et la section Gemini dans `.env.example` (clé vide, modèle, trois limites, commentaire expliquant que l'application est inactive sans clé).
- [ ] **Step 4:** tests verts.

### Task 3: Sélection, lots, requête et application de la réponse

**Files:**
- Create: `backend/app/services/classification_gemini.py`
- Test: `backend/tests/test_classification_gemini.py`

**Interfaces:**
- Consumes: `normaliser(texte: str) -> str` (`app/services/sous_thematiques.py`), `Article`, `Subtheme`, `Theme`, `subtheme_articles`.
- Produces :
  - `class ArticleACLasser(NamedTuple): id: int; titre: str; collection: str` (`collection` vaut « sans collection » si absente)
  - `articles_a_classer(db: Session) -> list[ArticleACLasser]` : articles sans aucun lien et avec `classe_par_gemini_le IS NULL`, par `id` croissant
  - `taxonomie_pour_requete(db: Session) -> list[dict]` : `[{"thematique": str, "sous_thematiques": [{"id": int, "nom": str, "mots_cles": [≤5 str]}]}]`
  - `estimer_tokens(texte: str) -> int` (`ceil(len/4)`)
  - `construire_requete(taxonomie: list[dict], lot: list[ArticleACLasser]) -> str`
  - `decouper_en_lots(articles: list[ArticleACLasser], taxonomie: list[dict]) -> list[list[ArticleACLasser]]` : respecte 300 articles et 100 000 tokens estimés (taxonomie incluse) par lot
  - `SCHEMA_REPONSE: dict` : liste d'objets `{article_id: int, sous_thematique_id: int | null, nouvelle: {thematique, nom, mots_cles} | null}`
  - `mots_cles_valides(mots: list[str], titres_corpus: list[str]) -> list[str]`
  - `appliquer_reponse(db: Session, lot: list[ArticleACLasser], reponse: list[dict]) -> dict` rend `{"rattaches": int, "crees": int}` ; écrit les liens avec `source='gemini'`, crée les sous-thématiques, pose `classe_par_gemini_le` sur **tous** les articles du lot, `flush` sans `commit`.

- [ ] **Step 1: Tests rouges** :
  - `test_articles_a_classer_exclut_les_rattaches_et_les_deja_soumis`
  - `test_decouper_en_lots_respecte_la_taille_maximale` (1 000 articles, plusieurs lots de ≤ 300) et `test_decouper_en_lots_respecte_le_plafond_de_tokens` (titres très longs, chaque lot sous 100 000 tokens)
  - `test_construire_requete_contient_taxonomie_articles_et_consigne_de_reutilisation` (la consigne « réutilise une sous-thématique existante si le sujet est le même » y figure)
  - `test_mots_cles_valides_borne_et_filtre` (9 mots donnent 8 ; « abc » écarté ; majuscules passées en minuscules ; un mot présent dans plus de 2 % des titres écarté)
  - `test_appliquer_reponse_rattache_a_une_sous_thematique_existante`
  - `test_appliquer_reponse_cree_une_sous_thematique_sous_une_thematique_existante`
  - `test_appliquer_reponse_reutilise_une_sous_thematique_au_nom_equivalent` (« Jardin Bio » puis « jardin bio » et « Jardin bio » avec accent ou casse différents : une seule ligne)
  - `test_appliquer_reponse_refuse_une_thematique_inconnue` (rien n'est créé, article tout de même horodaté)
  - `test_appliquer_reponse_ignore_les_ids_hors_lot_ou_inconnus`
  - `test_appliquer_reponse_horodate_tout_le_lot`
- [ ] **Step 2:** vérifier l'échec.
- [ ] **Step 3:** implémenter. La déduplication compare `normaliser(nom)` aux sous-thématiques de la thématique ; la thématique se retrouve par `func.lower(Theme.name)`. Ne pas utiliser `theme_pour_nom` (il crée). Constantes `TAILLE_LOT_MAX = 300`, `TOKENS_REQUETE_MAX = 100_000`, `MOTS_CLES_MAX = 8`, `MOT_CLE_LONGUEUR_MIN = 4`, `MOT_CLE_PART_CORPUS_MAX = 0.02`.
- [ ] **Step 4:** tests verts.

### Task 4: Client Gemini et boucle de classification

**Files:**
- Create: `backend/app/services/gemini_client.py`
- Modify: `backend/app/services/classification_gemini.py`
- Test: `backend/tests/test_classification_gemini.py`, `backend/tests/test_gemini_client.py`

**Interfaces:**
- Consumes: `SuiviQuota`, `Pause`, constantes de raison (tâche 2) ; fonctions de la tâche 3.
- Produces :
  - `class ErreurGemini(Exception)` avec attributs `raison: str`, `jusqua: datetime | None`, `message: str`
  - `appeler_gemini(prompt: str) -> tuple[str, int]` : texte JSON et tokens utilisés (`usage_metadata.total_token_count`) ; client `genai.Client` avec `HttpOptions(timeout=gemini_timeout_seconds * 1000)`, sortie JSON structurée avec `SCHEMA_REPONSE` ; traduit les erreurs du SDK en `ErreurGemini` : 429 devient `QUOTA_JOUR` si le message contient « PerDay » sinon `QUOTA_MINUTE`, avec `jusqua` tiré du délai de reprise de l'erreur s'il existe ; 404 `MODELE_INTROUVABLE` ; 401, 403 ou clé refusée `CLE_INVALIDE` ; toute autre `ERREUR_API`
  - `classer_orphelins(db: Session, suivi: SuiviQuota, appeler_modele: Callable[[str], tuple[str, int]] = appeler_gemini) -> dict` : rend `{"rattaches": int, "crees": int, "restants": int, "pause": Pause | None}`

- [ ] **Step 1: Tests rouges** (modèle simulé par une fonction Python) :
  - `test_classer_orphelins_traite_tous_les_lots_et_commite`
  - `test_pause_quota_jour_arrete_la_boucle_sans_appel` (budget épuisé : `appeler_modele` jamais appelé, `pause.raison == QUOTA_JOUR`, articles toujours candidats)
  - `test_erreur_429_pose_la_pause_et_ne_reessaie_pas` (un seul appel, pause enregistrée dans `SuiviQuota`)
  - `test_modele_introuvable_pose_une_pause_avec_la_raison`
  - `test_reponse_mal_formee_compte_une_requete_et_laisse_les_articles_candidats`
  - `test_trois_reponses_mal_formees_posent_une_pause_d_une_heure` (`FORMAT_INVALIDE`, `jusqua` = maintenant + 1 h)
  - `test_une_reponse_valide_remet_le_compteur_d_echecs_a_zero`
  - `test_un_echec_gemini_ne_touche_pas_aux_donnees_deja_commitees` (lot 1 appliqué, lot 2 en erreur : lot 1 reste)
  - Pour `gemini_client` : `test_traduction_429_par_jour_et_par_minute`, `test_traduction_404_et_cle_invalide` avec de fausses exceptions du SDK (aucun appel réseau).
- [ ] **Step 2:** vérifier l'échec.
- [ ] **Step 3:** implémenter `classer_orphelins` : tant qu'il reste des lots, `pause_active` puis `autoriser(estimer_tokens(prompt))` ; si pause, stop. Sinon `enregistrer` **avant** l'appel, appeler, `json.loads` (liste attendue), `appliquer_reponse`, `commit`. `ErreurGemini` : `poser_pause(raison, jusqua or prochaine_reinitialisation(now) pour QUOTA_JOUR, début de minute suivante pour QUOTA_MINUTE)` puis stop. Compteur d'échecs de format consécutifs en variable locale ; à 3, `poser_pause(FORMAT_INVALIDE, now + 1 h)`.
- [ ] **Step 4:** tests verts.

### Task 5: Tâche worker, déclenchement et reprise

**Files:**
- Modify: `backend/app/worker/tasks.py` (nouvelle tâche et hook après `rattacher_magazine`), `backend/app/worker/run.py` (`worker.work(with_scheduler=True)`)
- Test: `backend/tests/test_classification_tache.py`

**Interfaces:**
- Consumes: `classer_orphelins`, `SuiviQuota`, `redis_conn` et `ingestion_queue` (`app/queue.py`), `get_settings`.
- Produces :
  - `classer_orphelins_task() -> None` : sans clé API, retourne aussitôt ; verrou Redis `gemini:verrou` (`SET NX EX 3600`, libéré en `finally`) ; construit `SuiviQuota(redis_conn, settings.gemini_rpm, settings.gemini_rpd, settings.gemini_tpm)` ; ouvre sa session ; si `pause` et `restants > 0`, `ingestion_queue.enqueue_at(pause.jusqua + 5 s, classer_orphelins_task, job_id="classer_orphelins_reprise")` (en supprimant d'abord un job du même identifiant)
  - `declencher_classification() -> None` : sans clé API, ne fait rien ; sinon `ingestion_queue.enqueue(classer_orphelins_task, job_timeout="30m")`

- [ ] **Step 1: Tests rouges** (Redis et file simulés par monkeypatch) : `test_sans_cle_api_rien_n_est_mis_en_file` ; `test_declenche_une_tache_avec_une_cle` ; `test_la_tache_reprogramme_la_reprise_quand_une_pause_laisse_des_articles` (`enqueue_at` appelé avec l'heure de reprise) ; `test_la_tache_ne_reprogramme_rien_quand_tout_est_classe` ; `test_le_verrou_empeche_deux_executions_simultanees` ; `test_le_verrou_est_libere_apres_une_erreur`.
- [ ] **Step 2:** vérifier l'échec.
- [ ] **Step 3:** implémenter. Dans `tasks.py`, appeler `declencher_classification()` juste après le bloc `rattacher_magazine`, dans son propre `try/except` qui journalise sans remonter (l'extraction du sommaire ne doit jamais échouer à cause de cela). `run.py` : `worker.work(with_scheduler=True)`.
- [ ] **Step 4:** tests verts.

### Task 6: Endpoint d'état

**Files:**
- Modify: `backend/app/schemas.py`, `backend/app/routers/admin.py`
- Test: `backend/tests/test_classification_etat.py`

**Interfaces:**
- Consumes: `SuiviQuota`, `articles_a_classer`, `redis_conn`.
- Produces : `GET /api/admin/classification` (admin seulement) répond `ClassificationOut` : `actif: bool`, `modele: str`, `en_attente: int`, `requetes_aujourdhui: int`, `limite_jour: int`, `pause: {raison: str, jusqua: datetime} | None`. Sans clé API : `actif=False`, compteurs à 0, `pause=None`, sans toucher Redis.

- [ ] **Step 1: Tests rouges** (client de test comme `test_admin_stats.py`, `redis_conn` remplacé par `FauxRedis`) : `test_inactif_sans_cle_api` ; `test_actif_renvoie_attente_et_compteurs` ; `test_renvoie_la_pause_en_cours` ; `test_route_reservee_a_l_admin` (utilisateur non admin : 403, comme les tests d'autorisation existants).
- [ ] **Step 2:** vérifier l'échec.
- [ ] **Step 3:** implémenter schéma et route.
- [ ] **Step 4:** tests verts.

### Task 7: Bandeau du tableau de bord

**Files:**
- Modify: `frontend/lib/types.ts`, `frontend/app/(app)/admin/page.tsx`
- Create: `frontend/components/admin/ClassificationBanner.tsx`

**Interfaces:**
- Consumes: `GET /admin/classification` (tâche 6) via `api.get`.
- Produces : type `ClassificationStatus` (`actif`, `modele`, `en_attente`, `requetes_aujourdhui`, `limite_jour`, `pause: { raison: string; jusqua: string } | null`) ; composant `ClassificationBanner` sans props.

- [ ] **Step 1:** ajouter le type. Composant : ne rend rien si `!actif` ou en cas d'erreur. Sinon, avec `pause`, une bannière d'avertissement avec un message français par `raison` : `quota_jour` « Quota journalier Gemini atteint (X/Y). La classification reprend {quand}. » ; `quota_minute` « Limite par minute atteinte, reprise {quand}. » ; `cle_invalide` « Clé API Gemini refusée : vérifier GEMINI_API_KEY. » ; `modele_introuvable` « Modèle Gemini « {modele} » introuvable : vérifier GEMINI_MODEL. » ; `format_invalide` « Réponses Gemini illisibles, nouvelle tentative {quand}. » ; `erreur_api` « Gemini indisponible, nouvelle tentative {quand}. » `{quand}` = « à HH:MM » le jour même, « demain à HH:MM » sinon, en heure locale (`toLocaleTimeString("fr-FR", …)`). Sans pause mais avec `en_attente > 0`, une ligne discrète « N article(s) en attente de classification (X/Y requêtes aujourd'hui) ». Rafraîchissement toutes les 60 s.
- [ ] **Step 2:** insérer le composant en tête du contenu de `admin/page.tsx`.
- [ ] **Step 3:** `cd frontend && npx tsc --noEmit -p .` sans erreur ; vérification dans le navigateur impossible sans backend, à signaler.

### Task 8: Documentation et vérification finale

**Files:**
- Modify: `README.md` (section « Gérer les thématiques » et configuration), `docker-compose.yml` si une variable doit être transmise.

- [ ] **Step 1:** README : décrire la classification automatique (clé facultative, modèle par défaut, limites réglables, nouvelles sous-thématiques créées automatiquement, pause et reprise, bandeau), corriger l'encadré qui annonce la suppression de Gemini (le thémage par numéro reste supprimé, la classification d'articles est nouvelle), ajouter les lignes de configuration (`GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_RPM`, `GEMINI_TPM`, `GEMINI_RPD`, `GEMINI_TIMEOUT_SECONDS`).
- [ ] **Step 2:** vérifier que `app-backend` et `worker` reçoivent la clé (`env_file: .env` pour les deux, pas de changement attendu).
- [ ] **Step 3:** suite complète : `python3 -c "import app.main"` et `pytest -q` (tous verts, aucun test existant cassé), `npx tsc --noEmit -p .`, migration `0019` hors ligne dans les deux sens.

## Commandes

```bash
# Environnement de test (éphémère, à recréer s'il a disparu)
uv venv /tmp/test-venv-magsearch3 --python 3.12 --clear --force
uv pip install --python /tmp/test-venv-magsearch3/bin/python -r backend/requirements.txt -r backend/requirements-dev.txt
cd backend && /tmp/test-venv-magsearch3/bin/python -m pytest -q
```

## Limites assumées

- Les articles orphelins déjà présents avant le déploiement ne sont classés qu'au prochain scan (pas de bouton de lancement manuel, hors périmètre).
- Pas de fusion automatique des sous-thématiques proches (« Jardinage bio » et « Jardin bio ») : la déduplication ne couvre que les noms équivalents à la casse et aux accents près, la consigne de réutilisation du prompt fait le reste.
