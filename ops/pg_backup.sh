#!/bin/sh
# Sauvegarde périodique de PostgreSQL avec rotation.
#
# La base est la seule donnée non reconstructible de l'application : elle
# concentre le texte OCR intégral, les sommaires extraits via l'API Gemini,
# les tags, collections et comptes. Les PDF sur le NAS peuvent être
# re-scannés ; ce contenu-là, non.
#
# Exécuté en boucle par le service « db-backup » de docker-compose.yml.
# Les variables PG* sont fournies par l'environnement du conteneur.

set -eu

REP_SAUVEGARDE="${BACKUP_DIR:-/backups}"
RETENTION_JOURS="${BACKUP_RETENTION_DAYS:-14}"
INTERVALLE="${BACKUP_INTERVAL_SECONDS:-86400}"

mkdir -p "$REP_SAUVEGARDE"

journal() {
    echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*"
}

sauvegarder() {
    horodatage="$(date -u '+%Y%m%dT%H%M%SZ')"
    cible="${REP_SAUVEGARDE}/${PGDATABASE}_${horodatage}.sql.gz"
    partiel="${cible}.partial"

    journal "Sauvegarde en cours vers $(basename "$cible")"

    # Écriture sous un nom temporaire puis renommage : une sauvegarde
    # interrompue ne laisse jamais un fichier .sql.gz d'apparence valide.
    if pg_dump --no-owner --no-privileges | gzip -9 > "$partiel"; then
        mv "$partiel" "$cible"
        journal "Terminée : $(du -h "$cible" | cut -f1)"
    else
        rm -f "$partiel"
        journal "ÉCHEC de la sauvegarde"
        return 1
    fi
}

purger() {
    # -mtime +N supprime les fichiers de plus de N jours.
    supprimes="$(find "$REP_SAUVEGARDE" -name "${PGDATABASE}_*.sql.gz" \
        -type f -mtime "+${RETENTION_JOURS}" -print -delete | wc -l)"
    if [ "$supprimes" -gt 0 ]; then
        journal "Purge : ${supprimes} sauvegarde(s) de plus de ${RETENTION_JOURS} jours"
    fi
}

journal "Service de sauvegarde démarré (intervalle ${INTERVALLE}s, rétention ${RETENTION_JOURS} jours)"

while true; do
    # Un échec ne doit pas tuer la boucle : on réessaiera au cycle suivant.
    sauvegarder || journal "Nouvelle tentative au prochain cycle"
    purger || true
    sleep "$INTERVALLE"
done
