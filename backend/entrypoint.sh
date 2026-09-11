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

# Sauvegarde prise juste avant une migration. Elle atterrit sur le volume
# app_data, déjà monté : aucune modification du docker-compose n'est requise.
# Ce n'est PAS la sauvegarde principale — celle-ci reste le service db-backup,
# qui écrit sur un volume distinct — mais un filet tendu au seul moment où le
# schéma change.
REP_DUMP="${PRE_MIGRATION_DUMP_DIR:-/data/pre-migration}"
DUMPS_CONSERVES="${PRE_MIGRATION_DUMP_KEEP:-3}"

# Rend vrai quand la version appliquée en base diffère de celle attendue par
# le code. Sans ce test, un simple redémarrage déclencherait un dump de neuf
# minutes alors que rien ne change.
migration_en_attente() {
    appliquee="$(alembic current 2>/dev/null | awk 'NF {print $1; exit}')"
    attendue="$(alembic heads 2>/dev/null | awk 'NF {print $1; exit}')"
    [ "$appliquee" != "$attendue" ]
}

sauvegarder_avant_migration() {
    # DATABASE_URL est une URL SQLAlchemy : pg_dump ignore le suffixe de
    # pilote « +psycopg » et refuserait de l'analyser.
    url_pg="$(printf '%s' "${DATABASE_URL:-}" | sed 's|+psycopg||')"
    if [ -z "$url_pg" ]; then
        echo "DATABASE_URL absente : sauvegarde impossible." >&2
        return 1
    fi

    mkdir -p "$REP_DUMP"
    fichier="${REP_DUMP}/avant-migration-$(date -u +%Y%m%dT%H%M%SZ).dump"

    echo "Migration en attente (${appliquee:-base vide} -> ${attendue})." >&2
    echo "Sauvegarde vers ${fichier} — cela peut prendre plusieurs minutes." >&2

    # --format=custom : compresse, et restaurable sélectivement via pg_restore.
    if ! pg_dump "$url_pg" --format=custom --file="$fichier"; then
        # Un fichier tronqué serait pire qu'aucun fichier : il donnerait
        # l'illusion d'une sauvegarde exploitable.
        rm -f "$fichier"
        return 1
    fi

    echo "Sauvegarde terminée ($(du -h "$fichier" | cut -f1))." >&2

    # Les migrations sont rares : trois sauvegardes suffisent à couvrir un
    # retour en arrière, et le volume ne se remplit pas indéfiniment.
    ls -1t "${REP_DUMP}"/avant-migration-*.dump 2>/dev/null \
        | tail -n +$((DUMPS_CONSERVES + 1)) \
        | while read -r ancien; do
            echo "Purge de la sauvegarde ${ancien}" >&2
            rm -f "$ancien"
        done

    return 0
}

# Only the API service runs migrations, so a concurrent restart of
# app-backend and worker (same image/entrypoint) can't race on Alembic.
case "$1" in
  uvicorn)
    if migration_en_attente; then
      if [ "${SKIP_PRE_MIGRATION_DUMP:-0}" = "1" ]; then
        echo "SKIP_PRE_MIGRATION_DUMP=1 : migration sans sauvegarde prealable." >&2
      elif ! sauvegarder_avant_migration; then
        echo "" >&2
        echo "=== SAUVEGARDE PRE-MIGRATION IMPOSSIBLE ===" >&2
        echo "" >&2
        echo "La migration est ANNULEE : appliquer un changement de schema" >&2
        echo "sans filet est precisement ce que ce garde-fou evite." >&2
        echo "" >&2
        echo "Causes frequentes : volume /data plein, base injoignable," >&2
        echo "version de pg_dump inferieure a celle du serveur." >&2
        echo "" >&2
        echo "Pour passer outre en connaissance de cause :" >&2
        echo "  SKIP_PRE_MIGRATION_DUMP=1" >&2
        echo "" >&2
        sleep "$DELAI_AVANT_SORTIE"
        exit 1
      fi
    fi

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
      echo "Une sauvegarde a ete prise avant la tentative, dans ${REP_DUMP}." >&2
      echo "" >&2
      echo "Nouvelle tentative dans ${DELAI_AVANT_SORTIE}s." >&2
      echo "" >&2
      sleep "$DELAI_AVANT_SORTIE"
      exit 1
    fi
    ;;
esac

exec "$@"
