#!/usr/bin/env bash
# ViralShorts - encrypted backup of the SQLite accounts database + data folder
# to S3 / Cloudflare R2, with N-day retention. Run from cron on the VPS host.
# Counterpart of the (Postgres) pg_backup.sh described in ops/README.md.
#
# What goes into one archive (viralshorts-data-<UTC timestamp>.tar.gz.age):
#   studio.db       a CONSISTENT snapshot taken with SQLite's own VACUUM INTO
#                   (never a cp of the live file: the DB runs in WAL mode and a
#                   plain copy can be torn or miss the -wal contents)
#   brand/          uploaded brand-kit logos (same folder as the DB)
#   .studio_secret  only if it exists (auto-generated signing key; absent when
#                   STUDIO_SECRET is set in .env)
#   output/         ONLY when BACKUP_INCLUDE_OUTPUT=1 (finished clips; large,
#                   and swept after JOB_RETENTION_SECONDS anyway)
#
# Environment (put in /etc/viralshorts-backup.env, mode 0600):
#   STATE_DIR              host folder holding data/ and output/ (same value as
#                          in .env / docker-compose.prod.yml). Required.
#   BACKUP_AGE_RECIPIENT   age public key (age1...). Required unless
#                          BACKUP_GPG_RECIPIENT is set. The archive holds
#                          emails and password hashes: it is never uploaded
#                          in clear.
#   BACKUP_GPG_RECIPIENT   alternative to age: a gpg key id/email.
#   BACKUP_DEST            s3://bucket/prefix   Required unless DRY_RUN=1.
#   BACKUP_S3_ENDPOINT     e.g. https://<account>.r2.cloudflarestorage.com
#                          (leave empty for AWS S3)
#   AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY   credentials scoped to the bucket
#   AWS_DEFAULT_REGION     R2: auto (default here); AWS: your region
#   RETENTION_DAYS         default 30
#   BACKUP_INCLUDE_OUTPUT  1 to also archive output/ (default 0)
#   DRY_RUN                1 = build and encrypt locally, upload/prune nothing
#   BACKUP_WORKDIR         scratch folder (default: mktemp -d). Needs space for
#                          one archive.
#
# Requirements on the host: sqlite3 (CLI, >= 3.27 for VACUUM INTO) or python3,
# tar, gzip, age (or gpg), awscli, GNU date.

set -euo pipefail

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

: "${STATE_DIR:?STATE_DIR must be set (host folder that contains data/)}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
BACKUP_INCLUDE_OUTPUT="${BACKUP_INCLUDE_OUTPUT:-0}"
DRY_RUN="${DRY_RUN:-0}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-auto}"

DATA="$STATE_DIR/data"
DB="$DATA/studio.db"
[ -f "$DB" ] || die "database not found: $DB"
case "$RETENTION_DAYS" in ''|*[!0-9]*) die "RETENTION_DAYS must be a number" ;; esac

# Refuse to write a readable copy of the users table anywhere.
if [ -z "${BACKUP_AGE_RECIPIENT:-}" ] && [ -z "${BACKUP_GPG_RECIPIENT:-}" ]; then
  die "set BACKUP_AGE_RECIPIENT (or BACKUP_GPG_RECIPIENT): refusing to produce an unencrypted backup"
fi
if [ "$DRY_RUN" != "1" ]; then
  : "${BACKUP_DEST:?BACKUP_DEST must be set (s3://bucket/prefix)}"
  command -v aws >/dev/null || die "aws CLI not found"
  case "$BACKUP_DEST" in s3://*) ;; *) die "BACKUP_DEST must start with s3://" ;; esac
fi

WORK="${BACKUP_WORKDIR:-$(mktemp -d)}"
mkdir -p "$WORK"
OUT=""
cleanup() {
  rm -rf "$WORK/stage"
  [ -n "$OUT" ] && rm -f "$OUT"
  if [ -z "${BACKUP_WORKDIR:-}" ]; then rm -rf "$WORK"; fi
  return 0
}
trap cleanup EXIT

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
STAGE="$WORK/stage"
rm -rf "$STAGE"; mkdir -p "$STAGE"

# 1. Consistent snapshot of the live database.
log "snapshotting $DB"
SNAP="$STAGE/studio.db"
if command -v sqlite3 >/dev/null; then
  # Waits for locks up to 30 s instead of failing while the app is writing.
  sqlite3 "$DB" ".timeout 30000" "VACUUM INTO '$SNAP'"
  CHECK="$(sqlite3 "$SNAP" 'PRAGMA integrity_check;')"
elif command -v python3 >/dev/null; then
  python3 - "$DB" "$SNAP" <<'PY'
import sqlite3, sys
src = sqlite3.connect(sys.argv[1], timeout=30)
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)           # online backup API: safe on a live WAL database
dst.close(); src.close()
PY
  CHECK="$(python3 -c "import sqlite3,sys; print(sqlite3.connect(sys.argv[1]).execute('PRAGMA integrity_check').fetchone()[0])" "$SNAP")"
else
  die "need sqlite3 or python3 on the host"
fi
[ "$CHECK" = "ok" ] || die "integrity_check on the snapshot failed: $CHECK"

# 2. Companion files from the data folder.
[ -d "$DATA/brand" ] && cp -a "$DATA/brand" "$STAGE/brand"
[ -f "$DATA/.studio_secret" ] && cp -a "$DATA/.studio_secret" "$STAGE/.studio_secret"

TAR_ARGS=(-C "$STAGE" .)
if [ "$BACKUP_INCLUDE_OUTPUT" = "1" ] && [ -d "$STATE_DIR/output" ]; then
  # Finished clips, the thing the project library points at.
  TAR_ARGS+=(-C "$STATE_DIR" output)
fi

# 3. Archive + encrypt in one pipeline: plaintext never touches the disk
#    (the staged snapshot does, so keep BACKUP_WORKDIR on the host's private disk).
OUT="$WORK/viralshorts-data-$STAMP.tar.gz.${BACKUP_AGE_RECIPIENT:+age}"
if [ -n "${BACKUP_AGE_RECIPIENT:-}" ]; then
  command -v age >/dev/null || die "age not found (apt install age)"
  tar -cz "${TAR_ARGS[@]}" | age -r "$BACKUP_AGE_RECIPIENT" -o "$OUT"
else
  command -v gpg >/dev/null || die "gpg not found"
  OUT="$WORK/viralshorts-data-$STAMP.tar.gz.gpg"
  tar -cz "${TAR_ARGS[@]}" | gpg --batch --yes --trust-model always -e -r "$BACKUP_GPG_RECIPIENT" -o "$OUT"
fi
SIZE="$(du -h "$OUT" | cut -f1)"
log "built $(basename "$OUT") ($SIZE)"

if [ "$DRY_RUN" = "1" ]; then
  cp "$OUT" "./$(basename "$OUT")"
  log "DRY_RUN: not uploaded, not pruned. Local copy: $PWD/$(basename "$OUT")"
  exit 0
fi

# 4. Upload.
AWS=(aws)
[ -n "${BACKUP_S3_ENDPOINT:-}" ] && AWS+=(--endpoint-url "$BACKUP_S3_ENDPOINT")
DEST="${BACKUP_DEST%/}"
"${AWS[@]}" s3 cp --only-show-errors "$OUT" "$DEST/$(basename "$OUT")"
log "uploaded to $DEST/$(basename "$OUT")"

# 5. Retention: delete archives older than RETENTION_DAYS. The timestamp in the
#    file name (UTC, sortable) is the clock, not the object's mtime.
CUTOFF="$(date -u -d "-$RETENTION_DAYS days" +%Y%m%dT%H%M%SZ)"
"${AWS[@]}" s3 ls "$DEST/" | awk '{print $4}' | grep -E '^viralshorts-data-[0-9]{8}T[0-9]{6}Z\.tar\.gz\.(age|gpg)$' | while read -r name; do
  ts="${name#viralshorts-data-}"; ts="${ts%%.tar.gz*}"
  if [[ "$ts" < "$CUTOFF" ]]; then
    "${AWS[@]}" s3 rm --only-show-errors "$DEST/$name"
    log "pruned $name"
  fi
done
log "done"
