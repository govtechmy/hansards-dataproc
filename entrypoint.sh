#!/bin/bash
set -e

echo "[entrypoint] Loading DAGSTER_DB_URL from AWS Secrets Manager..."

python - <<'EOF'
import os, json, boto3

secret_name = os.getenv("AWS_SECRETS_NAME")
region = os.getenv("AWS_REGION", "ap-southeast-5")

if not secret_name:
    print("[entrypoint] No AWS_SECRETS_NAME set, skipping.")
else:
    client = boto3.client("secretsmanager", region_name=region)
    secret = client.get_secret_value(SecretId=secret_name)["SecretString"]
    data = json.loads(secret)

    dagster_db_url = data.get("DAGSTER_DB_URL")
    if dagster_db_url:
        print(f"export DAGSTER_DB_URL='{dagster_db_url}'")
    else:
        print("[entrypoint] DAGSTER_DB_URL not found in secret.")
EOF > /tmp/export_env.sh

source /tmp/export_env.sh

echo "[entrypoint] DAGSTER_DB_URL loaded. Starting Dagster..."
exec "$@"
