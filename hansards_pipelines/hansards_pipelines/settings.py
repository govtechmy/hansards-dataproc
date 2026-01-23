import os
import json
from typing import Optional

import boto3
from dotenv import load_dotenv

load_dotenv()

def _load_from_aws_secrets_manager_if_configured() -> None:
    """If AWS_SECRETS_NAME is set, attempt to load and inject secret values.

    - Secret value is expected to be a JSON object of key/value pairs.
    - If JSON parsing fails, falls back to parsing .env-style lines.
    - On any error, silently falls back to existing environment (.env already loaded).
    """
    secret_name = os.getenv("AWS_SECRETS_NAME")
    if not secret_name:
        return

    try:
        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=secret_name)
        secret_str = response.get("SecretString")
        if not secret_str:
            return

        try:
            parsed = json.loads(secret_str)
            if isinstance(parsed, dict):
                for key, value in parsed.items():
                    os.environ[key] = str(value)
                return
        except json.JSONDecodeError:
            pass

        # Fallback: parse as .env-style lines (KEY=VALUE)
        for line in secret_str.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ[key.strip()] = value.strip()
    except Exception:
        # Intentionally ignore errors and use existing env values
        return


_load_from_aws_secrets_manager_if_configured()


def get_env_str(name: str, default: Optional[str] = None) -> Optional[str]:

    value = os.getenv(name, default)
    return value


def get_env_int(name: str, default: int) -> int:

    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


S3_DATAPROC_BUCKET: Optional[str] = get_env_str("S3_DATAPROC_BUCKET")
S3_PUBLIC_BUCKET: Optional[str]   = get_env_str("S3_PUBLIC_BUCKET")
S3_TEXTRACT_BUCKET: Optional[str] = get_env_str("S3_TEXTRACT_BUCKET")

DEV_API_URL: Optional[str]   = get_env_str("DEV_API_URL")
PROD_API_URL: Optional[str]  = get_env_str("PROD_API_URL")
FRONTEND_URL: Optional[str]  = get_env_str("FRONTEND_URL")
FRONTEND_TOKEN: Optional[str] = get_env_str("FRONTEND_TOKEN")

HANSARD_DB_URL: Optional[str] = get_env_str("HANSARD_DB_URL")

DAGSTER_DB_URL: Optional[str] = get_env_str("DAGSTER_DB_URL")
DISCORD_WEBHOOK_URL: Optional[str]  = get_env_str("DISCORD_WEBHOOK_URL")
DAGIT_BASE_URL: Optional[str]  = get_env_str("DAGIT_BASE_URL")

AWS_SECRETS_NAME: Optional[str] = get_env_str("AWS_SECRETS_NAME")
AWS_REGION: Optional[str] = get_env_str("AWS_REGION")

HANSARD_DB_URL: Optional[str] = get_env_str("HANSARD_DB_URL")