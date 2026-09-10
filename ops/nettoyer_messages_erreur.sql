-- Assainissement des messages d'erreur déjà stockés en base.
--
-- CONTEXTE
--   Les messages d'erreur du pipeline sont exposés par l'API à tout compte
--   authentifié — pas seulement aux administrateurs :
--     - magazines.error_message et magazines.toc_error_message via MagazineOut
--       (GET /api/magazines, protégé par get_current_user)
--     - pages.error_message via PageOut
--   Jusqu'au durcissement récent, ces colonnes recevaient la trace Python
--   complète, chemins absolus du serveur compris.
--
--   Le code assainit désormais à l'écriture, mais UNIQUEMENT pour les
--   nouvelles erreurs. Les lignes déjà présentes conservent l'ancien contenu.
--   À exécuter avant d'ouvrir des comptes utilisateurs.
--
-- CE QUE FAIT LE NETTOYAGE
--   Pour chaque message concerné :
--     1. ne conserve que la première ligne (retire la trace) ;
--     2. supprime les préfixes de chemins absolus, ne gardant que le nom de
--        fichier — même règle que message_erreur_affichable() côté Python ;
--     3. tronque à 300 caractères.
--   Aucune ligne n'est supprimée, aucun statut n'est modifié : seul le texte
--   affiché est raccourci. Un numéro en échec le reste.
--
-- USAGE
--   Étape 1 — inspecter (lecture seule) :
--     docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
--       -f - < ops/nettoyer_messages_erreur.sql
--   La partie 2 est encadrée par BEGIN/ROLLBACK : par défaut, RIEN n'est
--   écrit. Remplacer ROLLBACK par COMMIT une fois le résultat vérifié.
--
--   Faire une sauvegarde fraîche avant d'appliquer (voir ops/pg_backup.sh).


-- =====================================================================
-- PARTIE 1 — Inspection : combien de lignes sont concernées ?
-- =====================================================================

\echo '--- Lignes contenant une trace ou un chemin absolu ---'

SELECT 'magazines.error_message' AS colonne,
       count(*) AS lignes_concernees
FROM magazines
WHERE error_message ~ '(Traceback|/[^ ]+/)'

UNION ALL

SELECT 'magazines.toc_error_message',
       count(*)
FROM magazines
WHERE toc_error_message ~ '(Traceback|/[^ ]+/)'

UNION ALL

SELECT 'pages.error_message',
       count(*)
FROM pages
WHERE error_message ~ '(Traceback|/[^ ]+/)';


\echo '--- Aperçu : avant / après, sur 5 exemples ---'

SELECT id,
       left(error_message, 120) AS avant,
       left(
         regexp_replace(split_part(error_message, E'\n', 1),
                        '/(?:[^/[:space:]]+/)+', '', 'g'),
         120
       ) AS apres
FROM magazines
WHERE error_message ~ '(Traceback|/[^ ]+/)'
LIMIT 5;


-- =====================================================================
-- PARTIE 2 — Nettoyage
-- Encadré par BEGIN/ROLLBACK : remplacer ROLLBACK par COMMIT pour appliquer.
-- =====================================================================

BEGIN;

UPDATE magazines
SET error_message = left(
      regexp_replace(split_part(error_message, E'\n', 1),
                     '/(?:[^/[:space:]]+/)+', '', 'g'),
      300)
WHERE error_message ~ '(Traceback|/[^ ]+/)';

UPDATE magazines
SET toc_error_message = left(
      regexp_replace(split_part(toc_error_message, E'\n', 1),
                     '/(?:[^/[:space:]]+/)+', '', 'g'),
      300)
WHERE toc_error_message ~ '(Traceback|/[^ ]+/)';

UPDATE pages
SET error_message = left(
      regexp_replace(split_part(error_message, E'\n', 1),
                     '/(?:[^/[:space:]]+/)+', '', 'g'),
      300)
WHERE error_message ~ '(Traceback|/[^ ]+/)';

\echo '--- Vérification post-nettoyage (doit renvoyer 0 partout) ---'

SELECT 'magazines.error_message' AS colonne, count(*) AS restantes
FROM magazines WHERE error_message ~ '(Traceback|/[^ ]+/)'
UNION ALL
SELECT 'magazines.toc_error_message', count(*)
FROM magazines WHERE toc_error_message ~ '(Traceback|/[^ ]+/)'
UNION ALL
SELECT 'pages.error_message', count(*)
FROM pages WHERE error_message ~ '(Traceback|/[^ ]+/)';

-- Remplacer par COMMIT une fois le résultat ci-dessus vérifié.
ROLLBACK;
