#!/bin/sh
# Essai du script de sauvegarde, dans l'image : faux pg_dump et psql, cible, données et pile factices dans /tmp.
# Usage : docker run --rm --entrypoint sh magazine-search-sauvegarde:essai /app/essai.sh
set -u
APP="${APP:-/app}"
R=/tmp/essai-sauvegarde
rm -rf "$R"
mkdir -p "$R/bin" "$R/nas" "$R/donnees/processed" "$R/donnees/covers" "$R/donnees/logs" "$R/pile"

cat > "$R/bin/pg_dump" <<'FIN'
#!/bin/sh
[ "${FAUX_PG_ECHEC:-0}" = 1 ] && exit 1
echo "$*" > "${0%/bin/pg_dump}/pg_dump.args"
while [ $# -gt 0 ]; do
  if [ "$1" = -f ]; then echo dump > "$2"; exit 0; fi
  shift
done
exit 1
FIN
cat > "$R/bin/psql" <<FIN
#!/bin/sh
[ "\${FAUX_PSQL_ECHEC:-0}" = 1 ] && exit 2
case "\$*" in *backup_requests*) [ "\${FAUX_DEMANDE:-0}" = 1 ] && echo 1; exit 0 ;; esac
echo "\$*" >> "$R/sql.log"
FIN
chmod +x "$R/bin/pg_dump" "$R/bin/psql"
echo compose > "$R/pile/compose.yaml"
echo env > "$R/pile/.env"
echo a > "$R/donnees/processed/1.pdf"
echo c > "$R/donnees/covers/1.jpg"
echo l > "$R/donnees/logs/backend.log"

echec() { echo "ÉCHEC : $1" >&2; cat "$R/out.log" >&2; exit 1; }
nuit() {
  AUJOURDHUI="$1" CIBLE="$R/nas" DONNEES="${DONNEES_ESSAI:-$R/donnees}" PILE="${PILE_ESSAI:-$R/pile}" \
    DATABASE_URL=postgresql://faux PATH="$R/bin:$PATH" "$APP/sauvegarder.sh" > "$R/out.log" 2>&1
}
inode() { stat -c %i "$1"; }
dates() { ls -d "$R/nas"/????-??-?? 2>/dev/null | sed 's|.*/||' | tr '\n' ' '; }

# première nuit
nuit 2026-10-01 || echec "première nuit : code $?"
for f in base/magazines.dump donnees/processed/1.pdf donnees/covers/1.jpg config/compose.yaml config/.env sauvegarde.txt; do
  [ -f "$R/nas/2026-10-01/$f" ] || echec "première nuit : $f absent"
done
[ ! -e "$R/nas/2026-10-01/donnees/logs" ] || echec "première nuit : journaux copiés"
[ "$(readlink "$R/nas/derniere")" = 2026-10-01 ] || echec "première nuit : lien derniere"
grep -q true "$R/sql.log" || echec "première nuit : tentative non inscrite"
grep -q backup_runs "$R/sql.log" || echec "première nuit : table backup_runs"
grep -q -- '--lock-wait-timeout=10min' "$R/pg_dump.args" || echec "pg_dump sans délai d'attente des verrous"

# fichier inchangé : lien physique
echo b > "$R/donnees/processed/2.pdf"
nuit 2026-10-02 || echec "deuxième nuit : code $?"
[ "$(inode "$R/nas/2026-10-01/donnees/processed/1.pdf")" = "$(inode "$R/nas/2026-10-02/donnees/processed/1.pdf")" ] \
  || echec "fichier inchangé : pas de lien physique"
[ -f "$R/nas/2026-10-02/donnees/processed/2.pdf" ] && [ ! -e "$R/nas/2026-10-01/donnees/processed/2.pdf" ] || echec "nouveau fichier"

# fichier disparu : absent du jour, présent la veille
rm "$R/donnees/processed/1.pdf"
nuit 2026-10-03 || echec "troisième nuit : code $?"
[ ! -e "$R/nas/2026-10-03/donnees/processed/1.pdf" ] && [ -f "$R/nas/2026-10-02/donnees/processed/1.pdf" ] || echec "fichier disparu"

# même jour : remplacé
nuit 2026-10-03 || echec "même jour : code $?"
[ "$(dates)" = "2026-10-01 2026-10-02 2026-10-03 " ] || echec "même jour : $(dates)"
[ ! -e "$R/nas/.remplace" ] || echec "même jour : .remplace laissé"

# compose d'un clone du dépôt : docker-compose.yml
mv "$R/pile/compose.yaml" "$R/pile/docker-compose.yml"
nuit 2026-10-04 || echec "docker-compose.yml : code $?"
[ -f "$R/nas/2026-10-04/config/docker-compose.yml" ] || echec "docker-compose.yml absent"

# sept jours
for j in 05 06 07 08 09 10; do nuit "2026-10-$j" || echec "nuit du $j : code $?"; done
[ "$(dates)" = "2026-10-04 2026-10-05 2026-10-06 2026-10-07 2026-10-08 2026-10-09 2026-10-10 " ] || echec "sept jours : $(dates)"

# échec des données : rien n'est supprimé
(DONNEES_ESSAI="$R/absent" nuit 2026-10-11) && echec "échec des données : code 0"
[ "$(dates)" = "2026-10-04 2026-10-05 2026-10-06 2026-10-07 2026-10-08 2026-10-09 2026-10-10 " ] || echec "échec des données : $(dates)"
[ "$(readlink "$R/nas/derniere")" = 2026-10-10 ] || echec "échec des données : lien derniere"
tail -1 "$R/sql.log" | grep -q false || echec "échec des données : non inscrit"
tail -1 "$R/sql.log" | grep -q 'étape donnees' || echec "échec des données : message"

# échec de la base
(FAUX_PG_ECHEC=1 nuit 2026-10-11) && echec "échec de la base : code 0"
tail -1 "$R/sql.log" | grep -q 'étape base' || echec "échec de la base : message"

# pile sans fichier compose : échec de la configuration
mkdir -p "$R/pile-vide" && echo env > "$R/pile-vide/.env"
(PILE_ESSAI="$R/pile-vide" nuit 2026-10-11) && echec "pile sans compose : code 0"
tail -1 "$R/sql.log" | grep -q 'étape config' || echec "pile sans compose : message"

# reste d'une tentative interrompue
mkdir -p "$R/nas/.en-cours/vieux"
nuit 2026-10-11 || echec "après interruption : code $?"
[ ! -e "$R/nas/.en-cours" ] || echec "reste d'une tentative interrompue"
[ "$(dates)" = "2026-10-05 2026-10-06 2026-10-07 2026-10-08 2026-10-09 2026-10-10 2026-10-11 " ] || echec "après interruption : $(dates)"

# inscription impossible : code de sortie de la sauvegarde conservé
(FAUX_PSQL_ECHEC=1 nuit 2026-10-12) || echec "inscription impossible : code $?"
[ -d "$R/nas/2026-10-12" ] || echec "inscription impossible : dossier absent"

# déjà en cours : une deuxième tentative s'arrête sans toucher à rien
lignes="$(wc -l < "$R/sql.log")"
mkdir -p "$R/nas/.en-cours/temoin"
(
  exec 9> "$R/verrou"
  flock -n 9 || exit 3
  VERROU="$R/verrou" nuit 2026-10-13 && exit 1
  exit 0
) || echec "déjà en cours : la deuxième tentative a tourné"
grep -q 'déjà en cours' "$R/out.log" || echec "déjà en cours : message"
[ -d "$R/nas/.en-cours/temoin" ] || echec "déjà en cours : .en-cours supprimé"
[ ! -e "$R/nas/2026-10-13" ] || echec "déjà en cours : dossier créé"
[ "$(wc -l < "$R/sql.log")" = "$lignes" ] || echec "déjà en cours : tentative inscrite"

# planifier : une demande de l'administration lance une sauvegarde à toute heure ; sans demande, rien avant HEURE
printf '#!/bin/sh\necho fait >> "%s/fait"\n' "$R" > "$R/bin/faux-sauvegarder"
chmod +x "$R/bin/faux-sauvegarder"
planifier() {
  HEURE=24 CIBLE="$R/nas" DATABASE_URL=postgresql://faux PATH="$R/bin:$PATH" SAUVEGARDER="$R/bin/faux-sauvegarder" \
    timeout 2 "$APP/planifier.sh" > "$R/out.log" 2>&1
}
(FAUX_DEMANDE=1 planifier)
[ "$(cat "$R/fait" 2>/dev/null)" = fait ] || echec "planifier : demande non prise"
rm -f "$R/fait"
planifier
[ ! -e "$R/fait" ] || echec "planifier : sauvegarde sans demande avant l'heure"

rm -rf "$R"
echo "Essai de la sauvegarde réussi."
