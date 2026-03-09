"""
Insert seed author_history data from S3 into api_author_history.

Input : s3://<S3_DATAPROC_BUCKET>/canonical/seed/author_history.csv
        Columns: record_id, author_id, party, area_id,
                 exec_posts, service_posts, start_date, end_date

Behaviour:
    UPSERT behaviour using ON CONFLICT (record_id) DO UPDATE.

    - If record_id does not exist -> row is inserted
    - If record_id already exists -> row is updated with the new values

Usage:
    python insert_to_db.py
    python insert_to_db.py --dry-run   # print stats, don't write to DB
    python insert_to_db.py --bucket my-other-bucket
"""

import io
import sys
import argparse

import boto3
import pandas as pd
import psycopg

from hansards_pipelines.settings import HANSARD_DB_URL, S3_DATAPROC_BUCKET, AWS_REGION

# --------------------------------------------------------------------------- #
# S3 path
# --------------------------------------------------------------------------- #
INPUT_KEY = "canonical/seed/author_history.csv"

# Columns expected in the seed CSV (and inserted into the DB)
DB_COLUMNS = [
    "record_id",
    "party",
    "area_id",
    "exec_posts",
    "service_posts",
    "start_date",
    "end_date",
    "author_id",
]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def get_db_connection():
    if not HANSARD_DB_URL:
        print("Error: HANSARD_DB_URL environment variable is missing.")
        sys.exit(1)
    try:
        return psycopg.connect(HANSARD_DB_URL)
    except Exception as exc:
        print(f"Error connecting to database: {exc}")
        sys.exit(1)


def read_csv_from_s3(s3_client, bucket: str, key: str) -> pd.DataFrame:
    print(f"  Reading s3://{bucket}/{key} ...")
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read()
        df = pd.read_csv(io.BytesIO(content))
        print(f"  Loaded {len(df)} rows, columns: {list(df.columns)}")
        return df
    except Exception as exc:
        print(f"Failed to read s3://{bucket}/{key}: {exc}")
        sys.exit(1)


def coerce_row(row: pd.Series) -> tuple:
    """Convert a DataFrame row into the tuple expected by the INSERT statement."""

    def safe_int(val):
        if pd.isna(val) or str(val).strip() in ("", "nan", "null", "none"):
            return None
        return int(float(val))

    def safe_str(val):
        if pd.isna(val) or str(val).strip() in ("", "nan", "null", "none"):
            return None
        return str(val).strip()

    def safe_date(val):
        """Normalise various date formats to ISO YYYY-MM-DD for PostgreSQL."""
        from datetime import datetime
        if pd.isna(val) or str(val).strip() in ("", "nan", "null", "none"):
            return None
        raw = str(val).strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        # Fall back to raw string and let the DB report the error
        return raw

    record_id   = safe_int(row.get("record_id"))
    author_id   = safe_int(row.get("author_id"))
    party       = safe_str(row.get("party"))
    area_id     = safe_int(row.get("area_id"))
    exec_posts  = safe_str(row.get("exec_posts"))
    service_posts = safe_str(row.get("service_posts"))
    start_date  = safe_date(row.get("start_date"))
    end_date    = safe_date(row.get("end_date"))

    return (record_id, author_id, party, area_id, exec_posts, service_posts, start_date, end_date)


# --------------------------------------------------------------------------- #
# Core logic
# --------------------------------------------------------------------------- #

def insert_author_history(df: pd.DataFrame, dry_run: bool = False) -> None:
    """
    Insert rows from df into api_author_history using UPSERT.

    ON CONFLICT (record_id) DO UPDATE:
        - Inserts new rows
        - Updates existing rows with values from the seed CSV
    """
    # Ensure optional columns exist so coerce_row won't KeyError
    for col in DB_COLUMNS:
        if col not in df.columns:
            df[col] = None

    skipped_no_record_id = 0
    skipped_no_author_id = 0
    skipped_no_start_date = 0
    attempted = 0

    skipped_rows_missing_record_id = []
    skipped_rows_missing_author_id = []
    skipped_rows_missing_start_date = []

    rows_to_insert = []
    for _, row in df.iterrows():
        record_id  = None if pd.isna(row.get("record_id"))  else row["record_id"]
        author_id  = None if pd.isna(row.get("author_id"))  else row["author_id"]
        start_date_raw = row.get("start_date")
        start_date = None if pd.isna(start_date_raw) or str(start_date_raw).strip() in ("", "nan", "null", "none") else start_date_raw

        if record_id is None:
            skipped_no_record_id += 1
            skipped_rows_missing_record_id.append(row.to_dict())
            continue
        if author_id is None:
            skipped_no_author_id += 1
            skipped_rows_missing_author_id.append(row.to_dict())
            continue
        if start_date is None:
            skipped_no_start_date += 1
            skipped_rows_missing_start_date.append(row.to_dict())
            continue

        rows_to_insert.append(coerce_row(row))
        attempted += 1

    print(f"\n  Rows to attempt  : {attempted}")
    if skipped_no_record_id:
        print(f"  Skipped (no record_id) : {skipped_no_record_id}")
        skipped_df = pd.DataFrame(skipped_rows_missing_record_id)
        print("\n  Sample of rows missing (record_id):")
        print(skipped_df.head(10).to_string(index=False))

    if skipped_no_author_id:
        print(f"  Skipped (no author_id) : {skipped_no_author_id}")
        skipped_df = pd.DataFrame(skipped_rows_missing_author_id)
        print("\n  Sample of rows missing (author_id):")
        print(skipped_df.head(10).to_string(index=False))

    if skipped_no_start_date:
        print(f"  Skipped (no start_date) : {skipped_no_start_date}")
        skipped_df = pd.DataFrame(skipped_rows_missing_start_date)
        print("\n  Sample of rows missing (start_date):")
        print(skipped_df.head(10).to_string(index=False))


    if dry_run:
        print("\n  [DRY-RUN] No changes written to the database.")
        if rows_to_insert:
            sample = pd.DataFrame(rows_to_insert, columns=DB_COLUMNS).head(5)
            print("  Preview of first 5 rows:")
            print(sample.to_string(index=False))
        return

    INSERT_SQL = """
        INSERT INTO api_author_history
            (record_id, author_id, party, area_id, exec_posts, service_posts, start_date, end_date)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (record_id)
        DO UPDATE SET
            author_id = EXCLUDED.author_id,
            party = EXCLUDED.party,
            area_id = EXCLUDED.area_id,
            exec_posts = EXCLUDED.exec_posts,
            service_posts = EXCLUDED.service_posts,
            start_date = EXCLUDED.start_date,
            end_date = EXCLUDED.end_date
    """

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.executemany(INSERT_SQL, rows_to_insert)

        conn.commit()

        print(f"\n  Rows upserted : {attempted}")
        print("  Upsert completed successfully.")

    except Exception as exc:
        conn.rollback()
        print(f"\nError during insert — rolled back: {exc}")
        sys.exit(1)

    finally:
        conn.close()
# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser(
        description="Insert canonical/seed/author_history.csv from S3 into api_author_history."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read and validate data but do NOT write to the database.",
    )
    parser.add_argument(
        "--bucket",
        type=str,
        default=S3_DATAPROC_BUCKET,
        help="S3 bucket name (default: S3_DATAPROC_BUCKET from settings).",
    )
    args = parser.parse_args()

    bucket = args.bucket
    if not bucket:
        print("Error: S3_DATAPROC_BUCKET is not set. Pass --bucket or set the env variable.")
        sys.exit(1)

    print("=== Insert author_history seed data into api_author_history ===")

    # 1. Read seed CSV from S3
    print(f"\n[1/2] Reading seed CSV from S3 ...")
    s3_client = boto3.client("s3", region_name=AWS_REGION)
    df = read_csv_from_s3(s3_client, bucket, INPUT_KEY)

    # 2. Insert into DB
    print(f"\n[2/2] Inserting into api_author_history ...")
    insert_author_history(df, dry_run=args.dry_run)

    print("\nDone.")


if __name__ == "__main__":
    main()
