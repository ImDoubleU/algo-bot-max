#!/usr/bin/env bash
set -euo pipefail

backup_dir="${BACKUP_DIR:-/var/backups/algo-max}"
retention_days="${BACKUP_RETENTION_DAYS:-14}"
database_url="${DATABASE_SYNC_URL:?DATABASE_SYNC_URL is required}"
database_url="${database_url/postgresql+psycopg:/postgresql:}"
product_media_root="${PRODUCT_MEDIA_ROOT:-}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$backup_dir"
umask 077
pg_dump --format=custom --no-owner --file "$backup_dir/algo_bot_max_${timestamp}.dump" "$database_url"
if [[ -n "$product_media_root" && -d "$product_media_root" ]]; then
    tar --create --gzip \
        --file "$backup_dir/product_media_${timestamp}.tar.gz" \
        --directory "$product_media_root" \
        .
fi
find "$backup_dir" -maxdepth 1 -type f -name 'algo_bot_max_*.dump' -mtime "+$retention_days" -delete
find "$backup_dir" -maxdepth 1 -type f -name 'product_media_*.tar.gz' -mtime "+$retention_days" -delete
