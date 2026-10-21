# Classification automatique des nouveaux articles par Gemini

## Intention

Quand de nouveaux numéros sont scannés, leurs sommaires sont déjà extraits
localement et rattachés aux sous-thématiques par correspondance de mots-clés
(`rattacher_magazine`, appelé à la fin de l'extraction du sommaire). Les articles
que les mots-clés n'attrapent pas restent « orphelins » et obligent aujourd'hui à
repasser par le flux manuel (export du corpus, appli Gemini, dépôt de la
réponse).

Objectif : après un scan, un modèle Gemini classe ces orphelins tout seul, sans
intervention, sans jamais dépasser les quotas du compte gratuit, et en
expliquant clairement dans l'application quand il est en pause et quand il
reprend.

Réintroduit volontairement un appel à l'API Gemini, retiré lors de l'audit
ponytail (`gemini_quota.py`, `theme_batch.py`, `GEMINI_API_KEY`, `google-genai`).
Ce n'est pas un retour au thémage par numéro : la cible reste l'**article** et la
taxonomie à deux niveaux existante (thématique > sous-thématique).

## Décisions de l'utilisateur

- Déclencheur : le scan de nouveaux magazines.
- Modèle par défaut : **Gemini Flash 3.8**, mêmes limites que celles affichées
  pour Gemini 3.6 Flash dans AI Studio : **5 requêtes/minute, 250 000
  tokens/minute, 20 requêtes/jour**.
- Quand un article ne rentre dans aucune sous-thématique existante, Gemini
  **propose une nouvelle sous-thématique**, **créée immédiatement**, sans
  validation préalable.
- Quota atteint : afficher dans l'application le message correct, avec l'heure à
  laquelle le modèle sera de nouveau disponible.

## Objectifs

- Les articles orphelins d'un nouveau numéro sont classés automatiquement.
- Aucun dépassement de quota en fonctionnement normal.
- Un échec ou un quota épuisé ne bloque jamais l'ingestion ni l'extraction des
  sommaires : les articles restent en attente et sont repris plus tard.
- Le tableau de bord indique : nombre d'articles en attente, requêtes
  consommées aujourd'hui sur la limite, et, si en pause, la raison et l'heure de
  reprise en heure locale.

## Hors périmètre

- Pas de thémage par numéro, pas de retour de l'ancien pipeline.
- Pas de reclassement des articles déjà rattachés par mots-clés.
- Pas de fusion ou de nettoyage automatique des sous-thématiques créées par le
  modèle.
- Pas de sélection de modèle dans l'interface : un réglage d'environnement
  suffit.

## À éviter absolument

- Bloquer ou faire échouer l'extraction d'un sommaire parce que Gemini est
  indisponible ou hors quota.
- Dépasser les limites et se faire couper par Google en pleine opération.
- Créer des doublons évidents de sous-thématiques existantes.
- Ré-envoyer à chaque scan des articles déjà soumis au modèle.

## Contraintes

- Limites par défaut codées en configuration : `GEMINI_RPM=5`,
  `GEMINI_TPM=250000`, `GEMINI_RPD=20`, modifiables par variable
  d'environnement (un autre hébergeur aura d'autres quotas).
- Sans `GEMINI_API_KEY`, la fonctionnalité est inactive et silencieuse : le
  comportement actuel (rattachement par mots-clés, flux manuel) est inchangé.
- Travail fait par le worker RQ existant (file `ingestion`), pas dans le
  processus web.
- Stack existante : FastAPI, SQLAlchemy/Alembic, Redis (déjà utilisé par RQ),
  Next.js. Tests en pytest, schéma de test SQLite en mémoire.
- Conventions du dépôt : commentaires en français, messages d'erreur affichables
  à l'utilisateur en français.

## Comportement attendu (décisions de conception)

*Les points marqués « choix du concepteur » sont des appels non validés par
l'utilisateur, à relire.*

**Déclenchement.** À la fin de l'extraction d'un sommaire, après
`rattacher_magazine`, une tâche `classer_orphelins` est mise en file. Elle traite
**tous** les articles encore non soumis au modèle, pas seulement ceux du dernier
numéro, ce qui rattrape aussi les lots restés en attente. Une seule tâche de ce
type à la fois (verrou Redis).

**Quels articles.** Un article est candidat s'il n'est rattaché à aucune
sous-thématique **et** n'a jamais été soumis à Gemini. Une colonne
`articles.classe_par_gemini_le` (horodatage, nullable) est posée une fois
l'article traité, qu'il ait été rattaché ou non (choix du concepteur : évite de
renvoyer indéfiniment un article que le modèle n'a pas su classer).

**Lots.** Plusieurs centaines de titres par requête (choix du concepteur :
environ 300, à ajuster d'après le plafond de tokens), pour que 20 requêtes par
jour suffisent largement. La requête contient la taxonomie actuelle (thématiques
et sous-thématiques avec leurs mots-clés) et la liste des articles `(id, titre,
collection)`.

**Réponse attendue.** Sortie structurée JSON. Pour chaque article, soit
l'identifiant d'une sous-thématique existante, soit une proposition de nouvelle
sous-thématique : nom, thématique parente, mots-clés. Une réponse mal formée est
rejetée en bloc et l'article reste candidat (choix du concepteur).

**Nouvelles sous-thématiques.** Créées immédiatement, sous une thématique
**existante** uniquement (choix du concepteur : Gemini ne crée pas de
thématique de premier niveau). Déduplication par nom normalisé dans la
thématique, avec réutilisation de l'existante si le nom correspond. Les
mots-clés sont stockés pour que les prochains articles rejoignent la
sous-thématique gratuitement, par le rattachement local habituel.

**Suivi de quota.** Compteurs dans Redis : requêtes par minute, requêtes par
jour, tokens par minute. Marge de sécurité : la tâche s'arrête avant la limite
(choix du concepteur : réserver 2 requêtes sur 20 par jour). Le jour de quota
est le jour **heure du Pacifique** (réinitialisation à minuit
America/Los_Angeles, selon la compréhension actuelle du fonctionnement de
Google, à vérifier). En cas de réponse 429 de Google malgré les compteurs, la
pause est posée d'après l'indication de reprise de l'erreur si elle existe,
sinon jusqu'à la prochaine réinitialisation.

**Pause et reprise.** Une clé Redis « pause jusqu'à » porte l'heure de reprise
et la raison (quota minute, quota jour, modèle introuvable, clé invalide). La
reprise est automatique : la file est relancée à l'heure indiquée. Le mécanisme
exact de relance (job différé RQ, tâche périodique) est laissé au constructeur,
sous réserve qu'il survive à un redémarrage du worker.

**Affichage.** Un endpoint d'administration renvoie l'état de la classification :
`en_attente`, `requetes_aujourdhui`, `limite_jour`, `pause` (raison, heure de
reprise ISO) ou rien. Le tableau de bord admin affiche un bandeau quand
l'état n'est pas normal, avec des messages en français distincts :
quota journalier atteint (reprise à l'heure locale, par exemple « demain à
08:00 »), quota par minute (reprise dans quelques secondes), clé invalide,
modèle introuvable (avec le nom configuré). Quand tout va bien et que des
articles attendent, une ligne discrète indique le nombre en attente.

**Modèle.** `GEMINI_MODEL`, défaut `gemini-3.8-flash` (choix du concepteur : cet
identifiant n'a pas été confirmé ; en cas d'erreur « modèle introuvable » le
message affiché nomme la valeur configurée pour corriger la variable).

## Précisions (choix du concepteur, après relecture)

- **Les rattachements posés par Gemini doivent survivre au recalcul par
  mots-clés.** Une colonne `source` sur `subtheme_articles` (`mots_cles` par
  défaut, `gemini` pour ceux-ci) ; `rattacher_magazine`, `rattacher` et
  `recalculer_tout` ne purgent que les liens `mots_cles`. Sans cela, un
  retraitement de sommaire ou un recalcul rendrait l'article orphelin sans qu'il
  soit jamais renvoyé (`classe_par_gemini_le` déjà posé).
- **Mots-clés proposés pour une nouvelle sous-thématique** : au plus 8, de 4
  caractères minimum, en minuscules ; un mot-clé qui correspond à plus de 2 %
  des articles du corpus est écarté, pour qu'un terme trop générique n'aspire
  pas des articles sans rapport lors d'un recalcul. Ils servent aux scans
  suivants et aux recalculs.
- **Tokens par minute** : on compte l'entrée et la sortie. La taille d'un lot
  est adaptative, estimée à environ 4 caractères par token et plafonnée à
  100 000 tokens par requête. Pour la taxonomie embarquée dans chaque requête :
  noms de thématiques et de sous-thématiques avec au plus 5 mots-clés chacune.
- **Doublons de sous-thématiques** : déduplication par nom normalisé dans la
  thématique, plus une consigne explicite dans la requête (« réutilise une
  sous-thématique existante si le sujet est le même »). Pas de correspondance
  floue en première version.
- **Réponse mal formée** : elle compte comme une requête consommée. Après 3
  échecs consécutifs, la classification se met en pause 1 heure avec la raison
  affichée, pour qu'un format défaillant ne vide pas le quota du jour.
- **« Collection » dans la requête** : le nom de la collection du magazine de
  l'article, ou « sans collection » s'il n'en a pas.

## À la charge du constructeur

- Choix du client (SDK `google-genai` réintroduit, ou appel HTTP direct) et de
  la façon d'obtenir une sortie JSON structurée.
- Taille exacte des lots d'après le plafond de tokens, et gestion d'une
  taxonomie qui grossit (la requête embarque toute la taxonomie).
- Mécanisme de relance automatique à l'heure de reprise.
- Migration Alembic (colonne `classe_par_gemini_le`), tests, mise à jour du
  README et de `.env.example`.
