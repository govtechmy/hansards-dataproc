"""
Resolve area_id for each row in author_history.csv by looking up area_name in api_area.
Also generates record_id for any rows missing it, starting from 3000.

Input  : s3://<S3_DATAPROC_BUCKET>/canonical/preprocessing/master/author_history.csv
          Columns: record_id, author_id, author_name, party, area_id, area_name,
                   area_state, exec_posts, service_posts, start_date, end_date

Output : s3://<S3_DATAPROC_BUCKET>/canonical/preprocessing/author_history/resolved/author_history.csv
          Same columns, with area_id filled where it can be resolved from api_area,
          and record_id generated for any missing entries.

Usage:
    python find_area_id_given_area_name.py
    python find_area_id_given_area_name.py --dry-run   # print stats, don't upload
"""

import io
import sys
import argparse
import boto3
import pandas as pd
import psycopg
from dotenv import load_dotenv

from ...settings import HANSARD_DB_URL, S3_DATAPROC_BUCKET, AWS_REGION

load_dotenv()


# --------------------------------------------------------------------------- #
# S3 paths
# --------------------------------------------------------------------------- #
INPUT_KEY  = "canonical/preprocessing/master/author_history.csv"
OUTPUT_KEY = "canonical/preprocessing/author_history/resolved/author_history.csv"

# Expected columns (in output order)
EXPECTED_COLUMNS = [
    "record_id",
    "author_id",
    "author_name",
    "party",
    "area_id",
    "area_name",
    "area_state",
    "exec_posts",
    "service_posts",
    "start_date",
    "end_date",
]


# --------------------------------------------------------------------------- #
# DB helpers
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


def build_area_lookup(conn) -> dict[str, int]:
    """
    Return a mapping of area_name (case-insensitive, stripped) -> area_id
    from the api_area table.

    When multiple rows share the same name (different states / types),
    the first occurrence (by id ASC) is used.
    """
    query = """
        SELECT id, name
        FROM   api_area
        WHERE  name IS NOT NULL
        ORDER  BY id ASC
    """
    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()

    lookup: dict[str, int] = {}
    for area_id, name in rows:
        key = name.strip().lower()
        if key not in lookup:          # keep first (lowest id)
            lookup[key] = area_id

    print(f"  Loaded {len(lookup)} distinct area names from api_area.")
    return lookup


# --------------------------------------------------------------------------- #
# S3 helpers
# --------------------------------------------------------------------------- #

def read_csv_from_s3(s3_client, bucket: str, key: str) -> pd.DataFrame:
    print(f"  Reading s3://{bucket}/{key} ...")
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content  = response["Body"].read()
        df = pd.read_csv(io.BytesIO(content))
        print(f"  Loaded {len(df)} rows, {len(df.columns)} columns.")
        return df
    except Exception as exc:
        print(f"Failed to read s3://{bucket}/{key}: {exc}")
        sys.exit(1)


def upload_csv_to_s3(s3_client, df: pd.DataFrame, bucket: str, key: str) -> None:
    print(f"  Uploading to s3://{bucket}/{key} ...")
    try:
        buf = io.BytesIO()
        df.to_csv(buf, index=False)
        buf.seek(0)
        s3_client.put_object(Bucket=bucket, Key=key, Body=buf.getvalue())
        print(f"  Upload complete — {len(df)} rows written.")
    except Exception as exc:
        print(f"Failed to upload to s3://{bucket}/{key}: {exc}")
        sys.exit(1)


# --------------------------------------------------------------------------- #
# Core logic
# --------------------------------------------------------------------------- #

def resolve_area_ids(df: pd.DataFrame, area_lookup: dict[str, int]) -> pd.DataFrame:
    """
    For each row where area_id is blank/null, try to fill it by matching
    area_name (case-insensitive) against the lookup dict.
    Existing non-null area_ids are preserved unchanged.
    """
    df = df.copy()

    # Ensure the column exists even if the CSV omitted it
    if "area_id" not in df.columns:
        df["area_id"] = None

    filled      = 0
    already_set = 0
    not_found   = 0
    no_name     = 0

    for idx, row in df.iterrows():
        existing = row["area_id"]

        # Already filled — leave it alone
        if pd.notna(existing) and str(existing).strip() != "":
            already_set += 1
            continue

        area_name = row.get("area_name")
        if (
              pd.isna(area_name)
             or str(area_name).strip().lower() in {"", "nan", "null", "none"}
        ):
            no_name += 1
            continue

        key = str(area_name).strip().lower()
        if key in area_lookup:
            df.at[idx, "area_id"] = area_lookup[key]
            filled += 1
        else:
            not_found += 1
            if not_found <= 20:                      # show first 20 misses
                print(f"    [WARN] No match for area_name='{area_name}' (record_id={row.get('record_id', '?')})")

    if not_found > 20:
        print(f"    [WARN] ... and {not_found - 20} more unmatched area_name(s) not shown.")

    print(
        f"\n  Resolution summary:\n"
        f"    Already had area_id : {already_set}\n"
        f"    Resolved from DB    : {filled}\n"
        f"    Unresolved (no name): {no_name}\n"
        f"    Unresolved (no match): {not_found}"
    )
    return df


def generate_record_ids(df: pd.DataFrame, start_id: int = 3000) -> pd.DataFrame:
    """
    Generate record_id for rows that don't have one, starting from start_id.
    Ensures all record_id values are integers.
    """
    df = df.copy()
    
    # Ensure the column exists
    if "record_id" not in df.columns:
        df["record_id"] = None
    
    # Convert existing record_ids to int where possible
    def safe_int_convert(val):
        if pd.isna(val) or str(val).strip() in {"", "nan", "null", "none"}:
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None
    
    df["record_id"] = df["record_id"].apply(safe_int_convert)
    
    # Find the next available ID
    existing_ids = df[df["record_id"].notna()]["record_id"].astype(int).tolist()
    next_id = max(start_id, max(existing_ids, default=0) + 1) if existing_ids else start_id
    
    # Generate IDs for missing records
    missing_count = 0
    for idx, row in df.iterrows():
        if pd.isna(row["record_id"]):
            df.at[idx, "record_id"] = next_id
            next_id += 1
            missing_count += 1
    
    # Convert all to int
    df["record_id"] = df["record_id"].astype(int)
    
    print(f"    Generated {missing_count} new record_id(s) starting from {start_id}")
    
    return df


def enforce_column_order(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only expected columns (adding nulls for any that's missing) in the right order."""
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[EXPECTED_COLUMNS]


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser(
        description="Resolve area_id from area_name in author_history.csv using api_area."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process and print stats but do NOT upload the resolved CSV to S3.",
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

    print("=== Resolve area_id in author_history ===")

    # 1. DB connection & area lookup
    print("\n[1/5] Building area lookup from database ...")
    conn = get_db_connection()
    try:
        area_lookup = build_area_lookup(conn)
    finally:
        conn.close()

    # 2. Read input CSV from S3
    print(f"\n[2/5] Reading input CSV from S3 ...")
    s3_client = boto3.client("s3", region_name=AWS_REGION)
    df = read_csv_from_s3(s3_client, bucket, INPUT_KEY)

    # 3. Resolve area_ids
    print("\n[3/5] Resolving area_ids ...")
    df_resolved = resolve_area_ids(df, area_lookup)
    
    # 4. Generate missing record_ids
    print("\n[4/5] Generating missing record_ids ...")
    df_resolved = generate_record_ids(df_resolved, start_id=3000)
    
    df_resolved = enforce_column_order(df_resolved)

    # 5. Upload (or skip if dry-run)
    print(f"\n[5/5] Uploading resolved CSV ...")
    if args.dry_run:
        print("  [DRY-RUN] Skipping upload. Preview of first 5 rows:")
        print(df_resolved.head().to_string(index=False))
    else:
        upload_csv_to_s3(s3_client, df_resolved, bucket, OUTPUT_KEY)

    print("\nDone.")


if __name__ == "__main__":
    main()
