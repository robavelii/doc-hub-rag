#!/usr/bin/env bash
# Deploy Doc-Hub to the shared OCI host.
#
#   scripts/deploy_oci.sh --init-env   # first time: write /opt/doc-hub/.env.prod with generated secrets
#   scripts/deploy_oci.sh [git-ref]    # ship a commit (default HEAD) and restart the doc-hub stack
#
# The host runs other apps. This script only touches the "doc-hub" compose project,
# /opt/doc-hub, and /etc/caddy/sites/doc-hub.caddy (validated, then Caddy is reloaded,
# never restarted). Never add global docker prune/down commands here.
#
# Env: DEPLOY_HOST (default ubuntu@51.170.178.91), DEPLOY_SSH_KEY (default ~/.ssh/oci_appt_deploy).
set -euo pipefail

DEPLOY_HOST="${DEPLOY_HOST:-ubuntu@51.170.178.91}"
DEPLOY_SSH_KEY="${DEPLOY_SSH_KEY:-$HOME/.ssh/oci_appt_deploy}"
REMOTE_DIR=/opt/doc-hub
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SSH=(ssh -i "$DEPLOY_SSH_KEY" -o BatchMode=yes -o ConnectTimeout=30 -o ServerAliveInterval=30 "$DEPLOY_HOST")

remote() { "${SSH[@]}" "bash -s" -- "$@"; }

if [[ "${1:-}" == "--init-env" ]]; then
  "${SSH[@]}" "sudo install -d -o \$(id -un) -g \$(id -gn) $REMOTE_DIR $REMOTE_DIR/releases $REMOTE_DIR/backups"
  "${SSH[@]}" "cat > $REMOTE_DIR/.env.prod.template" < "$ROOT/deploy/env.prod.example"
  remote <<EOF
set -euo pipefail
cd $REMOTE_DIR
if [[ -f .env.prod ]]; then echo ".env.prod already exists; not overwriting"; rm .env.prod.template; exit 0; fi
umask 077
cp .env.prod.template .env.prod && rm .env.prod.template
# One random value per distinct placeholder, reused wherever it repeats.
for token in \$(grep -o '__GENERATE[A-Z0-9_]*__' .env.prod | sort -u); do
  sed -i "s/\$token/\$(openssl rand -hex 24)/g" .env.prod
done
chmod 600 .env.prod
echo "Wrote $REMOTE_DIR/.env.prod. Add GEMINI_API_KEY / OPENAI_API_KEY, then deploy."
echo "Superadmin: \$(grep ^SUPERADMIN_EMAIL= .env.prod | cut -d= -f2) (password in .env.prod)"
EOF
  exit 0
fi

REF="${1:-HEAD}"
SHA="$(git -C "$ROOT" rev-parse --short=12 "$REF")"
[[ -z "$(git -C "$ROOT" status --porcelain)" ]] || echo "warning: uncommitted changes are NOT deployed (shipping $SHA)" >&2
echo "Deploying $SHA to $DEPLOY_HOST"

git -C "$ROOT" archive --format=tar "$REF" \
  | "${SSH[@]}" "mkdir -p $REMOTE_DIR/releases/$SHA && tar -x -C $REMOTE_DIR/releases/$SHA"

remote "$SHA" <<'EOF'
set -euo pipefail
SHA="$1"
REMOTE_DIR=/opt/doc-hub
REL="$REMOTE_DIR/releases/$SHA"
cd "$REL"
[[ -f "$REMOTE_DIR/.env.prod" ]] || { echo "missing $REMOTE_DIR/.env.prod (run --init-env)"; exit 1; }
ln -sf "$REMOTE_DIR/.env.prod" .env.prod
echo "$SHA" > RELEASE

# </dev/null: this script arrives on stdin (ssh bash -s); compose must not consume the rest of it.
dc() { docker compose -p doc-hub -f docker-compose.prod.yml --env-file .env.prod "$@" </dev/null; }

# Back up the database before migrations touch it.
if docker ps --format '{{.Names}}' | grep -qx doc_hub_postgres; then
  ts=$(date +%Y%m%d_%H%M%S)
  docker exec doc_hub_postgres pg_dump -U postgres -Fc ragdb > "$REMOTE_DIR/backups/ragdb_${ts}_pre_${SHA}.dump"
  ls -1t "$REMOTE_DIR"/backups/ragdb_*.dump | tail -n +15 | xargs -r rm --
  echo "Backup: ragdb_${ts}_pre_${SHA}.dump"
fi

# Build at low priority, one image at a time: the other apps on this host keep their CPU.
export COMPOSE_PARALLEL_LIMIT=1
nice -n 10 docker compose -p doc-hub -f docker-compose.prod.yml --env-file .env.prod build </dev/null

# Download the local embedding/reranker models once, before several workers start at the same time.
dc run --rm --no-deps -T celery_worker python -c "
from app.config import settings
from app.providers.local_provider import _embedding_model
from app.services.reranker import _cross_encoder
_embedding_model(settings.LOCAL_EMBED_MODEL); _cross_encoder(settings.LOCAL_RERANK_MODEL); print('models ready')"

dc up -d --remove-orphans

echo -n "Waiting for API health"
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8100/health/live >/dev/null 2>&1; then echo " ok"; break; fi
  echo -n "."; sleep 5
done
curl -fsS http://127.0.0.1:8100/health/live >/dev/null || { echo " FAILED"; dc ps; dc logs --tail 80 backend; exit 1; }

# Caddy site: install when changed (or when the running Caddy doesn't have it), validate
# as the caddy user, reload. A file Caddy can't load must never stay in sites/: the next
# reload by any other app on this host would fail on it.
SITE=/etc/caddy/sites/doc-hub.caddy
LOG=/var/log/caddy/doc-hub.log
if ! sudo cmp -s deploy/caddy/doc-hub.caddy "$SITE" || ! curl -fsS http://127.0.0.1:2019/config/ 2>/dev/null | grep -q doc.rfh.et; then
  restore_site() {
    echo "$1; restoring previous doc-hub site"
    if [[ -f "$SITE.bak" ]]; then sudo mv "$SITE.bak" "$SITE"; else sudo rm -f "$SITE"; fi
    exit 1
  }
  [[ -f "$SITE" ]] && sudo cp "$SITE" "$SITE.bak"
  sudo install -m 644 deploy/caddy/doc-hub.caddy "$SITE"
  # Caddy runs as "caddy"; a log file created by a root-run validate would be unwritable.
  [[ -f "$LOG" ]] || sudo install -o caddy -g caddy -m 600 /dev/null "$LOG"
  sudo -u caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null 2>&1 \
    || restore_site "Caddy config invalid"
  sudo systemctl reload caddy || restore_site "Caddy reload failed (running config unchanged)"
  sudo rm -f "$SITE.bak"
  echo "Caddy reloaded with doc-hub site"
fi

ln -sfn "$REL" "$REMOTE_DIR/current"
# Keep the last 5 releases.
ls -1dt "$REMOTE_DIR"/releases/*/ | tail -n +6 | xargs -r rm -rf --
dc ps --format 'table {{.Name}}\t{{.Status}}'
echo "Deployed $SHA"
EOF
