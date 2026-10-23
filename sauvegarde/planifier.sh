#!/bin/sh
# Planification de la sauvegarde : chaque jour dès HEURE (heure de Paris, défaut 3 h).
# Une nuit manquée (serveur ou NAS éteint) est rattrapée dès que le service tourne ; après un échec, une heure d'attente.
# Une sauvegarde demandée depuis l'administration (table backup_requests) part au passage suivant, à toute heure.
set -u
HEURE="${HEURE:-3}"
CIBLE="${CIBLE:-/nas}"
SAUVEGARDER="${SAUVEGARDER:-/app/sauvegarder.sh}"
echo "Sauvegarde planifiée chaque jour à $HEURE h."
while :; do
  # La demande est effacée avant la sauvegarde : un échec est inscrit et alerte, sans boucle de reprise.
  if [ -n "$(psql "$DATABASE_URL" -tAq -c 'DELETE FROM backup_requests RETURNING 1' 2>/dev/null)" ]; then
    echo "Sauvegarde demandée depuis l'administration."
    "$SAUVEGARDER"
  fi
  heure="$(date +%H | sed 's/^0//')"
  if [ "${heure:-0}" -ge "$HEURE" ] && [ "$(readlink "$CIBLE/derniere" 2>/dev/null)" != "$(date +%F)" ]; then
    "$SAUVEGARDER" || sleep 3600
  fi
  sleep 300
done
