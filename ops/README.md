# ops/

Operational files for running ViralShorts in production. Nothing here runs
automatically: each file is installed and scheduled on the host that needs it.

1. [Deploying ViralShorts on one VPS](#deploying-viralshorts-on-one-vps) (the current setup)
2. [Backups of the SQLite database](#backups-of-the-sqlite-database-backup_studiosh)

A step-by-step walkthrough in Vietnamese (domain, VPS, DNS, `.env`, payment webhooks, checks)
is in [`docs/deploy-vi.md`](../docs/deploy-vi.md); this file is the reference.

---

## Deploying ViralShorts on one VPS

Files: `docker-compose.prod.yml`, `Caddyfile` (repo root), `dashboard/Dockerfile`
(stage `prod`), `dashboard/nginx.conf`.

```
internet -> Caddy :80/:443 (automatic HTTPS)
              |-- /api /videos /thumbnails /gallery /video /mcp /health -> backend:8000 (FastAPI)
              `-- everything else                                         -> frontend:80  (nginx, static React build)
backend -> renderer:3100 (Remotion), internal only
```

Only Caddy publishes ports. The backend, frontend and renderer are reachable
solely on the compose network. The renderer is never exposed.

### Hard limits of this setup (read before promising anything to anyone)

- **One server, one backend container.** No horizontal scaling, no failover: if
  the VPS is down, the site is down. Jobs run inside that single container and
  their state lives in its memory and on its disk.
- **SQLite** (`data/studio.db`, WAL mode) is the database. It is fine for a
  thesis project and a few hundred accounts, but it allows one writer at a time,
  cannot be shared by two backend instances, and lives on the same disk as the
  application. The nightly off-site backup below is the only copy that survives
  losing the VPS: set it up before inviting real users.
- Transcription (faster-whisper) runs **on the CPU** by default; reframing and
  rendering are CPU-bound too. Concurrent jobs share the same cores
  (`MAX_CONCURRENT_JOBS`, `STUDIO_MAX_ACTIVE_JOBS`). Throughput must be measured
  on your VPS with your own videos.
- A deploy (`docker compose up -d --build`) restarts the backend. Running jobs
  are drained for up to `DRAIN_TIMEOUT_SECONDS` (840 s) and unfinished ones are
  resumed after a crash, but expect a short interruption.
- No staging environment, no metrics/alerting stack. Point an external uptime
  monitor (UptimeRobot, Better Stack...) at `GET /health`.

### Suggested VPS

Reference only; **measure** with a representative video before committing to a
size (a 1-hour source can take much longer than real time with CPU Whisper).

| Resource | Minimum to try | Comfortable |
|---|---|---|
| vCPU | 4 | 8 |
| RAM | 8 GB | 16 GB (torch, mediapipe, ffmpeg and Chromium for Remotion run together) |
| Disk | 80 GB SSD | 160+ GB (source uploads + clips; `output/` is swept after `JOB_RETENTION_SECONDS`, default 7 days) |
| OS | Ubuntu 22.04/24.04 LTS or Debian 12 | |
| Network | public IPv4, ports 80/443 | |

Add 2-4 GB of swap as a safety net for memory spikes. A GPU is **not** required;
`WHISPER_MODEL=small` (default) or `base` keeps CPU time manageable.

### DNS and firewall

- Create an `A` record (and `AAAA` if you have IPv6) for your domain pointing at
  the VPS public IP **before** the first start. Caddy requests the certificate
  from Let's Encrypt on first boot; a wrong DNS makes it fail and get
  rate-limited.
- For `www.<domain>` too: add its DNS record and uncomment the `www` block at
  the bottom of the `Caddyfile` (it redirects to the apex).
- Open **inbound** `22/tcp` (SSH, restrict to your IP if you can), `80/tcp`,
  `443/tcp` and `443/udp` (HTTP/3). Nothing else; in particular not 8000 or
  3100. Example with ufw:

```bash
sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw allow 443/udp && sudo ufw enable
```

Docker publishes ports by editing iptables directly and bypasses ufw, so the
real guarantee is the compose file itself: only `caddy` has `ports:`.

### First deployment

```bash
# Docker Engine + compose plugin: https://docs.docker.com/engine/install/
git clone <your repo> /opt/viralshorts && cd /opt/viralshorts
cp .env.example .env && chmod 600 .env     # then edit .env, see the table below
docker compose -f docker-compose.prod.yml config >/dev/null   # validates the file and the required variables
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps                   # backend should become "healthy"
curl -fsS https://YOUR-DOMAIN/health/ready
```

Update later with `git pull && docker compose -f docker-compose.prod.yml up -d --build`.
Logs: `docker compose -f docker-compose.prod.yml logs -f backend caddy`.

> The compose file and Caddyfile were written and syntax-checked on a machine
> without Docker; they have **not** been run end to end. Expect to fix small
> things on the first real deploy, and read the `docker compose ... config`
> output before `up`.

### Environment variables (`.env` next to the compose file)

The backend reads the whole `.env` (`env_file`), so every variable documented in
`.env.example` works. Compose refuses to start when a **required** one is
missing.

| Variable | Required | What / how to get it |
|---|---|---|
| `DOMAIN` | yes | Public host name, no scheme, e.g. `viralshorts.example.com`. Drives `PUBLIC_API_URL`, `FRONTEND_URL`, `GOOGLE_REDIRECT_URI` and the Caddy site address. |
| `ACME_EMAIL` | yes | Contact email for Let's Encrypt expiry notices. |
| `STUDIO_SECRET` | yes | Signs session tokens and media links. `openssl rand -hex 32`. Keep it stable: changing it logs everyone out and invalidates signed media URLs. |
| `GEMINI_API_KEY` | yes in practice | Clip detection, titles, thumbnails. Without it, processing returns 503. |
| `FAL_KEY`, `ELEVENLABS_API_KEY` | optional | AI Shorts (actors/B-roll), voices and dubbing. |
| `STUDIO_PAID`, `STRIPE_*`, `PAYOS_*`, `DAILY_AI_BUDGET_CREDITS` | for payments | See `docs/payments.md`. Webhook URLs to register: `https://DOMAIN/api/payos/webhook` and `https://DOMAIN/api/stripe/webhook`. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | optional | "Sign in with Google". Authorized redirect URI to register: `https://DOMAIN/api/auth/google/callback`. |
| `STUDIO_MONTHLY_MINUTES`, `STUDIO_MAX_ACTIVE_JOBS`, `MAX_CONCURRENT_JOBS` | optional | Capacity limits; tune to the VPS. |
| `STATE_DIR` | optional | Host folder for state (default `./state`: `data/`, `output/`, `uploads/`). |
| `MAX_UPLOAD` | optional | Max upload body accepted by Caddy (default `2GB`). |
| `WHISPER_MODEL` | optional | `base` is faster, `small` (default) more accurate. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | recommended | Verification, password-reset and receipt emails (`studio/mailer.py`). Without `SMTP_HOST` nothing is sent and no verified email is required. |
| `ADMIN_EMAILS` | recommended | Comma-separated emails allowed into `#/admin` (they must also have verified the email). |
| `ARCHIVE_BUCKET`, `ARCHIVE_ACCESS_KEY_ID`, `ARCHIVE_SECRET_ACCESS_KEY`, `ARCHIVE_ENDPOINT_URL` | for paid retention | S3/R2 bucket where finished clips are kept for the 14 / 60 days of the paid plans (`studio/archive.py`). Unset = off, and paid retention is not honoured. |
| `COMPANY_NAME`, `COMPANY_TAX_CODE`, `COMPANY_ADDRESS`, `SUPPORT_EMAIL` | for payments | Seller block on receipts. Use the same values as the legal pages (`dashboard/seo/site.js`). |
| `VITE_OPENPANEL_API_URL`, `VITE_OPENPANEL_CLIENT_ID` | optional | Analytics, baked in at build time. Leave empty for none. |
| `SITE_URL` | recommended | Public origin (`https://DOMAIN`), a **build** argument of the frontend image: canonical links, `sitemap.xml` and `llms.txt`. Not yet passed by `docker-compose.prod.yml` (add `SITE_URL: https://${DOMAIN}` under `frontend.build.args`); without it the legal pages and `robots.txt` are still built, the sitemap is not. |

Set by `docker-compose.prod.yml` itself (do not repeat them in `.env`):
`ACCOUNTS_ENABLED=1`, `BILLING_ENABLED=0` (forced off; `cloud/` is not used),
`STUDIO_DB_PATH=/app/data/studio.db`, `PUBLIC_API_URL`, `FRONTEND_URL`,
`GOOGLE_REDIRECT_URI`, `RENDER_SERVICE_URL`.

Notes:

- `.env` holds secrets: `chmod 600`, never commit it (it is git-ignored and
  excluded from the Docker build context).
- The image starts uvicorn with `--forwarded-allow-ips "*"` (Dockerfile). That
  is acceptable here only because the backend is not published: Caddy is the
  sole client that can reach it. Do not add a `ports:` entry to `backend`, or
  clients could forge `X-Forwarded-For` and bypass the per-IP rate limits.
- State lives in `${STATE_DIR}/data` (accounts DB + logos), `${STATE_DIR}/output`
  (clips) and `${STATE_DIR}/uploads`, plus the named volumes `caddy_data`
  (certificates) and `hf_cache` (downloaded ASR models). A one-shot
  `volume-init` service fixes folder ownership for the container's non-root user
  on every `up`.

---

## Backups of the SQLite database (`backup_studio.sh`)

Accounts, projects, the credit ledger and payment records are all in
`${STATE_DIR}/data/studio.db`. Run `backup_studio.sh` **on the VPS host** (not in
a container) every night.

What it does:

1. Takes a **consistent snapshot** with `VACUUM INTO` (or Python's SQLite online
   backup API when the `sqlite3` CLI is missing) - never a plain `cp` of a
   database that is being written - and runs `PRAGMA integrity_check` on it.
2. Adds `data/brand/` (logos) and `.studio_secret` if present. Optionally
   `output/` (`BACKUP_INCLUDE_OUTPUT=1`; large, off by default).
3. Compresses and **encrypts** with `age` (or `gpg`) in one pipeline. The
   database holds emails and password hashes, so the script refuses to run
   without a recipient key.
4. Uploads to S3 / Cloudflare R2 and deletes archives older than
   `RETENTION_DAYS` (default 30), judged by the UTC timestamp in the file name.

### Install

```bash
sudo apt-get install -y sqlite3 age awscli
sudo install -d -m 0750 /opt/viralshorts/ops
sudo install -m 0750 ops/backup_studio.sh /opt/viralshorts/ops/backup_studio.sh
```

Generate the key pair **on your laptop**, not on the server (the server only
needs the public half):

```bash
age-keygen -o viralshorts-backup.key      # keep in a password manager
grep 'public key' viralshorts-backup.key  # -> age1... goes on the server
```

Create `/etc/viralshorts-backup.env` (mode `0600`):

```sh
STATE_DIR="/opt/viralshorts/state"
BACKUP_AGE_RECIPIENT="age1................................................"
BACKUP_DEST="s3://viralshorts-backups/studio"
BACKUP_S3_ENDPOINT="https://<accountid>.r2.cloudflarestorage.com"   # empty for AWS S3
AWS_ACCESS_KEY_ID="..."          # token scoped to THIS bucket only
AWS_SECRET_ACCESS_KEY="..."
RETENTION_DAYS=30
# BACKUP_INCLUDE_OUTPUT=1
```

The files in `state/data` are owned by the container user, so run the script as
root.

Dry run first (builds and encrypts, uploads nothing; the archive is written to
the current directory):

```bash
set -a; . /etc/viralshorts-backup.env; set +a
cd /tmp && DRY_RUN=1 /opt/viralshorts/ops/backup_studio.sh
```

Schedule it (`sudo crontab -e`):

```cron
15 3 * * * set -a; . /etc/viralshorts-backup.env; set +a; /opt/viralshorts/ops/backup_studio.sh >> /var/log/viralshorts-backup.log 2>&1
```

### Restore

Do this once on a scratch machine before you need it. A backup nobody has
restored is a hypothesis.

```bash
# 1. Fetch and decrypt
aws s3 ls --endpoint-url "$BACKUP_S3_ENDPOINT" s3://viralshorts-backups/studio/
aws s3 cp --endpoint-url "$BACKUP_S3_ENDPOINT" \
  s3://viralshorts-backups/studio/viralshorts-data-20261112T031500Z.tar.gz.age .
mkdir restore && age -d -i viralshorts-backup.key viralshorts-data-*.tar.gz.age | tar xz -C restore

# 2. Check it
sqlite3 restore/studio.db 'PRAGMA integrity_check; SELECT count(*) FROM users;'

# 3. Put it back on the VPS (stop the backend first so nothing writes to the DB)
cd /opt/viralshorts
docker compose -f docker-compose.prod.yml stop backend
mv state/data state/data.broken.$(date +%s) 2>/dev/null
mkdir -p state/data
cp -a restore/studio.db state/data/
[ -d restore/brand ] && cp -a restore/brand state/data/
[ -f restore/.studio_secret ] && cp -a restore/.studio_secret state/data/
# (if you also backed up output/: cp -a restore/output state/)
docker compose -f docker-compose.prod.yml up -d      # volume-init re-applies ownership
curl -fsS https://YOUR-DOMAIN/health/ready
```

The snapshot has no `studio.db-wal` / `-shm` companions, which is intended: it is
already a complete database. After a restore, log in with a known account and
open the project library to confirm.

### Things to keep true

- **The bucket is private and separate from anything public.** Give the backup
  token write access to its own bucket and nothing else.
- **The private key is not on the server.** Otherwise whoever owns the server
  has both ciphertext and key.
- **`RETENTION_DAYS` and the privacy policy move together.** If the policy says
  a deletion disappears from backups within 30 days, raising the retention makes
  it false (see `docs/compliance/data-retention.md`). Bucket versioning / object-lock
  would defeat the retention too; use the same window if you enable it.
- **Keep `.env` (including `STUDIO_SECRET`) in a password manager.** It is not in
  the archive, and without it a rebuilt VPS cannot start.
