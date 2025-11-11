#!/usr/bin/env bash
# Minimal entrypoint: fetch secret, export DAGSTER_DB_URL (only), fail fast if absent, then exec.
set -euo pipefail

SECRET_NAME=${AWS_SECRETS_NAME:-}
REGION=${AWS_REGION:-}

echo "[entrypoint] Fetching DAGSTER_DB_URL from secret '$SECRET_NAME' in region '${REGION:-default}'."

python3 - <<'PY' > /tmp/export_env.sh || { echo '[entrypoint] ERROR: secret retrieval helper failed'; exit 1; }
import os, json, sys, boto3
secret_name = os.getenv('AWS_SECRETS_NAME')
region = os.getenv('AWS_REGION') or None
if not secret_name:
    print('# No AWS_SECRETS_NAME set; skipping secret fetch', file=sys.stderr)
    sys.exit(0)
sm = boto3.session.Session(region_name=region).client('secretsmanager') if region else boto3.client('secretsmanager')
try:
    resp = sm.get_secret_value(SecretId=secret_name)
except Exception as e:
    print(f'# Failed to retrieve secret: {e}', file=sys.stderr)
    sys.exit(0)
raw = resp.get('SecretString') or resp.get('SecretBinary')
if not raw:
    print('# Secret empty', file=sys.stderr); sys.exit(0)
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    # Treat whole secret as URL
    url = raw.strip()
else:
    url = (data.get('DAGSTER_DB_URL') or '').strip()
if url:
    print(f"export DAGSTER_DB_URL='{url}'")
else:
    print('# DAGSTER_DB_URL key missing or empty', file=sys.stderr)
PY

source /tmp/export_env.sh || true

if [[ -z "${DAGSTER_DB_URL:-}" ]]; then
  echo "[entrypoint] ERROR: DAGSTER_DB_URL not set; cannot start Dagster." >&2
  exit 2
fi

echo "[entrypoint] DAGSTER_DB_URL loaded. Starting main process..."
echo "[entrypoint] DAGSTER_DB_URL=${DAGSTER_DB_URL}" 

exec "$@"
