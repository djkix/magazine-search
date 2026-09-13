#!/bin/sh
set -e

# Temporisation avant de sortir en erreur quand la migration échoue. Docker
# relance aussitôt le conteneur : sans cette pause, alembic repart toutes les
# deux secondes, empile des demandes de verrou sur les mêmes tables, et bloque
# toute intervention manuelle.
#
# Cas réel, 11/09/2026 : la migration 0012 échouait sur un index déjà existant.
# Le DROP INDEX correctif est resté en attente derrière la file de verrous
# créée par la boucle, et n'est passé qu'après arrêt complet du conteneur.
DELAI_AVANT_SORTIE="${MIGRATION_FAILURE_DELAY_SECONDS:-30}"

# Pas de sauvegarde prise ici avant la migration. Cette protection a existé,
# du 11 au 13/09/2026, et causait plus de dégâts qu'elle n'en évitait :
#
#   - neuf minutes de dump bloquant à chaque déploiement touchant le schéma,
#     donc autant d'indisponibilité ;
#   - un redéploiement redémarre PostgreSQL, ce qui tuait le dump en cours —
#     et l'échec annulait la migration, laissant le conteneur boucler
#     indéfiniment sans jamais démarrer.
#
# Ce qui protège réellement, aujourd'hui :
#   - le job CI « migrations », qui rejoue toute la chaîne Alembic (montée,
#     descente, remontée) sur une base vierge avant tout déploiement ;
#   - le service db-backup, qui produit un dump quotidien avec rotation.

# Only the API service runs migrations, so a concurrent restart of
# app-backend and worker (same image/entrypoint) can't race on Alembic.
case "$1" in
  uvicorn)
    if ! alembic upgrade head; then
      echo "" >&2
      echo "=== ECHEC DE LA MIGRATION ALEMBIC ===" >&2
      echo "" >&2
      echo "L'application ne demarrera pas. La base n'a PAS ete modifiee :" >&2
      echo "chaque revision s'applique dans une transaction, et PostgreSQL" >&2
      echo "sait annuler du DDL." >&2
      echo "" >&2
      echo "Pour diagnostiquer, depuis l'hote :" >&2
      echo "  docker exec <conteneur> alembic current   # version appliquee" >&2
      echo "  docker exec <conteneur> alembic heads     # version attendue" >&2
      echo "" >&2
      echo "Arretez le conteneur avant toute correction en base : tant qu'il" >&2
      echo "tourne, ses tentatives repetees monopolisent les verrous." >&2
      echo "" >&2
      echo "La derniere sauvegarde quotidienne se trouve dans le volume du" >&2
      echo "service db-backup." >&2
      echo "" >&2
      echo "Nouvelle tentative dans ${DELAI_AVANT_SORTIE}s." >&2
      echo "" >&2
      sleep "$DELAI_AVANT_SORTIE"
      exit 1
    fi
    ;;
esac

exec "$@"
