# Deployment — paper-plus

Not part of the build roadmap (`STATE.md`) — this covers taking the app
from repo to a running production server. Nothing here changes
application behavior; see [business-rules.md](business-rules.md) for what
must never change.

## Recommended target

A small Linux VPS is the standard, best-documented path for a Django app
this size (single business, moderate traffic, Postgres on the same box):

- **OS:** Ubuntu 24.04 LTS (or 22.04).
- **Size:** 1–2 vCPU, 2 GB RAM, 20–40 GB SSD is comfortable headroom —
  this app has no heavy background jobs or media processing.
- **Stack:** nginx (reverse proxy, TLS termination, serves `static/`/`media/`)
  → gunicorn (WSGI, under systemd) → PostgreSQL 18 (matches dev, D-018's
  `paper_app` role).
- **TLS:** Let's Encrypt via `certbot`, since you already have a domain.

Any VPS provider works (Hetzner, DigitalOcean, Vultr, ArvanCloud, etc.) —
pick by price/region to your users, nothing here is provider-specific.

## 1. Server prerequisites

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.13 python3.13-venv postgresql postgresql-contrib \
    nginx certbot python3-certbot-nginx git
```

## 2. Database (mirrors D-018 locally: the app never connects as `postgres`)

```bash
sudo -u postgres psql <<'SQL'
CREATE ROLE paper_app WITH LOGIN PASSWORD 'CHANGE_ME';
CREATE DATABASE paper_plus OWNER paper_app;
SQL
```
Never paste the real password in chat — generate it on the server
(`openssl rand -base64 24`) and put it straight into `.env`.

## 3. Clone and install

```bash
sudo useradd -m -s /bin/bash paperplus
sudo -iu paperplus
git clone <your-repo-url> /home/paperplus/app
cd /home/paperplus/app
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: real SECRET_KEY, DEBUG=False, ALLOWED_HOSTS=your-domain.example,
# DATABASE_URL=postgres://paper_app:<password>@localhost:5432/paper_plus,
# CSRF_TRUSTED_ORIGINS=https://your-domain.example, BEHIND_TLS_PROXY=True
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

## 4. gunicorn as a systemd service

`/etc/systemd/system/paperplus.service`:
```ini
[Unit]
Description=paper-plus gunicorn
After=network.target postgresql.service

[Service]
User=paperplus
Group=www-data
WorkingDirectory=/home/paperplus/app
EnvironmentFile=/home/paperplus/app/.env
ExecStart=/home/paperplus/app/.venv/bin/gunicorn core.wsgi:application \
    --bind unix:/run/paperplus/paperplus.sock --workers 3
RuntimeDirectory=paperplus

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable --now paperplus
```

## 5. nginx

`/etc/nginx/sites-available/paperplus`:
```nginx
server {
    listen 80;
    server_name your-domain.example;

    location /static/ { alias /home/paperplus/app/staticfiles/; }
    location /media/  { alias /home/paperplus/app/media/; }

    location / {
        proxy_pass http://unix:/run/paperplus/paperplus.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```
```bash
sudo ln -s /etc/nginx/sites-available/paperplus /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d your-domain.example
```
`certbot` rewrites the server block for HTTPS and sets up auto-renewal.
`X-Forwarded-Proto` above is what `BEHIND_TLS_PROXY=True`
(`SECURE_PROXY_SSL_HEADER`, `core/settings.py`) trusts — never set that
flag without this header actually being set by your proxy.

## 6. Backups (Linux equivalent of `tools/backup.ps1`, which is PowerShell-only)

```bash
# /home/paperplus/backup.sh
#!/bin/bash
set -euo pipefail
ts=$(date +%F_%H%M%S)
pg_dump -U paper_app -h localhost paper_plus > /home/paperplus/backups/paper_plus_$ts.sql
```
Cron it (`crontab -e`): `0 2 * * * /home/paperplus/backup.sh`. Keep
`media/` (expense receipts) backed up the same way — it's real business
documents, not source (already gitignored, per `core/settings.py`'s own
comment on `MEDIA_ROOT`).

## 7. Deploying a new commit

```bash
sudo -iu paperplus
cd /home/paperplus/app && source .venv/bin/activate
git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
exit
sudo systemctl restart paperplus
```

## Checklist before going live
- [ ] `.env` has a real, unique `SECRET_KEY` (never the one from dev)
- [ ] `DEBUG=False`
- [ ] `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` set to the real domain
- [ ] `BEHIND_TLS_PROXY=True` only after nginx is actually forwarding `X-Forwarded-Proto`
- [ ] `python manage.py check --deploy` run on the server with prod `.env` — zero warnings
- [ ] Firewall: only 80/443 (and SSH) open; PostgreSQL not exposed publicly
- [ ] Backup cron confirmed with a real restore test, not just that it runs
