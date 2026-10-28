#!/usr/bin/env bash
# Sauvegarde PostgreSQL (Neon) -> fichier .sql.gz, avec envoi optionnel vers Cloudflare R2 (gratuit, 10 Go).
#
# Usage :
#   DATABASE_URL_DIRECT="postgresql://user:pass@ep-xxx.region.aws.neon.tech/db?sslmode=require" \
#     ./scripts/backup_db.sh [dossier_de_sortie]
#
# Variables optionnelles pour l'envoi vers R2 (AWS CLI requis) :
#   R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET
#   BACKUP_KEEP (nombre de sauvegardes locales conservées, défaut 7)
#
# IMPORTANT : utilisez l'URL DIRECTE de Neon (sans "-pooler") : pg_dump ne fonctionne pas via PgBouncer.
# Les identifiants ne sont jamais écrits sur disque ni affichés.
set -euo pipefail

: "${DATABASE_URL_DIRECT:?Définissez DATABASE_URL_DIRECT (URL Neon directe, sans -pooler)}"
case "$DATABASE_URL_DIRECT" in
  *-pooler*) echo "Erreur : l'URL contient '-pooler'. Utilisez l'URL directe de Neon." >&2; exit 1 ;;
esac
command -v pg_dump >/dev/null || { echo "pg_dump introuvable (installez postgresql-client)." >&2; exit 1; }

OUT_DIR="${1:-./backups}"
KEEP="${BACKUP_KEEP:-7}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FILE="${OUT_DIR}/eduia_${STAMP}.sql.gz"
mkdir -p "$OUT_DIR"
umask 077

echo "Sauvegarde en cours -> ${FILE}"
pg_dump --no-owner --no-privileges --format=plain "$DATABASE_URL_DIRECT" | gzip -9 > "$FILE"
[ -s "$FILE" ] || { echo "Erreur : sauvegarde vide." >&2; rm -f "$FILE"; exit 1; }
echo "OK ($(du -h "$FILE" | cut -f1))"

if [ -n "${R2_BUCKET:-}" ]; then
  command -v aws >/dev/null || { echo "aws CLI introuvable : envoi R2 ignoré." >&2; exit 1; }
  : "${R2_ACCOUNT_ID:?}" "${R2_ACCESS_KEY_ID:?}" "${R2_SECRET_ACCESS_KEY:?}"
  AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY" AWS_DEFAULT_REGION=auto \
    aws s3 cp "$FILE" "s3://${R2_BUCKET}/backups/$(basename "$FILE")" \
      --endpoint-url "https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com" --only-show-errors
  echo "Envoyé vers R2 : s3://${R2_BUCKET}/backups/$(basename "$FILE")"
fi

# Rotation locale : ne garder que les $KEEP plus récentes.
ls -1t "${OUT_DIR}"/eduia_*.sql.gz 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -r rm -f --
