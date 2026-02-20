"""
This standalone script compares partitions listed in a JSON file against those stored in a PostgreSQL
database table. It identifies partitions that are present in the JSON file but missing from
the database, and outputs these missing partitions to a new JSON file along with metadata.

Reason: To ensure that all expected partitions are accounted for in the database, facilitating
data integrity and completeness checks.
"""
import json
import psycopg2
from urllib.parse import urlparse
from datetime import datetime, timezone

from hansards_pipelines.settings import DAGSTER_DB_URL

DAGSTER_DB_URL = DAGSTER_DB_URL

PARTITION_DEF_NAME = "house_sittings"
JSON_FILE = "example-arkib_partitions.pending.json"
OUTPUT_FILE = "missing_partitions_in_db.json"


def parse_db_url(db_url):
    db_url = db_url.replace("postgresql+psycopg2://", "postgresql://")
    parsed = urlparse(db_url)

    return dict(
        host=parsed.hostname,
        port=parsed.port,
        dbname=parsed.path.lstrip("/"),
        user=parsed.username,
        password=parsed.password,
    )


def main():
    with open(JSON_FILE) as f:
        payload = json.load(f)

    json_partitions = set(payload.get("partitions", []))
    criteria = payload.get("criteria", {})

    print(f"JSON partitions: {len(json_partitions)}")

    # ---- Connect to DB ----
    db_config = parse_db_url(DAGSTER_DB_URL)
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()

    cur.execute("""
        SELECT partition
        FROM dynamic_partitions
        WHERE partitions_def_name = %s
    """, (PARTITION_DEF_NAME,))

    db_partitions = {row[0] for row in cur.fetchall()}

    cur.close()
    conn.close()

    print(f"DB partitions: {len(db_partitions)}")

    missing = sorted(json_partitions - db_partitions)
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "criteria": criteria,
        "partitions": missing,
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Missing in DB: {len(missing)}")
    print(f"Output written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
