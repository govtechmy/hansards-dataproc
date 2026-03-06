"""
Author History Pipeline — main entry point

Runs the four steps in order:
  1. find_area_id_given_area_name  - resolve area_id from api_area and generate missing record_ids
  2. handle_duplicate_author_history - remove duplicate rows from the resolved CSV
  3. prepare_seed_author_history    - strip helper columns to produce the seed CSV
  4. insert_to_db                   - insert seed CSV rows into api_author_history

Usage:
    python main.py
    python main.py --dry-run   # skip S3 uploads and DB writes (where supported)
    python main.py --bucket my-other-bucket
"""

import argparse
import logging
import sys
import boto3

from hansards_pipelines.seed_data.author_history.find_area_id_given_area_name import (
    INPUT_KEY as MASTER_INPUT_KEY,
    OUTPUT_KEY as RESOLVED_OUTPUT_KEY,
    read_csv_from_s3 as find_area_read_csv_from_s3,
    resolve_area_ids,
    generate_record_ids,
    enforce_column_order,
    get_db_connection,
    build_area_lookup,
    upload_csv_to_s3 as upload_resolved_csv_to_s3,
)
from hansards_pipelines.seed_data.author_history.handle_duplicate_author_history import (
    download_from_s3 as download_resolved_from_s3,
    remove_duplicates,
    upload_to_s3 as upload_master_to_s3,
)
from hansards_pipelines.seed_data.author_history.prepare_seed_author_history import (
    download_from_s3 as download_master_from_s3,
    prepare_seed_data,
    upload_to_s3 as upload_seed_to_s3,
)
from hansards_pipelines.seed_data.author_history.insert_to_db import (
    read_csv_from_s3 as read_seed_from_s3,
    insert_author_history,
    INPUT_KEY as SEED_INPUT_KEY,
)
from hansards_pipelines.settings import AWS_REGION, S3_DATAPROC_BUCKET



logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger(__name__)


DEDUP_INPUT_KEY = RESOLVED_OUTPUT_KEY
DEDUP_OUTPUT_KEY = MASTER_INPUT_KEY
SEED_OUTPUT_KEY = SEED_INPUT_KEY


def run_find_area_id(args):
    """Step 1: Resolve area_id and generate missing record_ids."""

    logger.info("\n" + "=" * 60)
    logger.info("STEP 1 — find_area_id_given_area_name")
    logger.info("=" * 60)

    bucket = args.bucket
    if not bucket:
        logger.error("Error: S3_DATAPROC_BUCKET is not set.")
        sys.exit(1)

    conn = get_db_connection()
    try:
        area_lookup = build_area_lookup(conn)
    finally:
        conn.close()

    s3_client = boto3.client("s3", region_name=AWS_REGION)
    df = find_area_read_csv_from_s3(s3_client, bucket, MASTER_INPUT_KEY)
    df = resolve_area_ids(df, area_lookup)
    df = generate_record_ids(df, start_id=3000)
    df = enforce_column_order(df)

    if args.dry_run:
        logger.info("\n[DRY-RUN] Skipping S3 upload. Preview of last 5 rows:")
        logger.info(df.tail().to_string(index=False))
    else:
        upload_resolved_csv_to_s3(s3_client, df, bucket, RESOLVED_OUTPUT_KEY)
        logger.info("\nPreview of last 5 rows:")
        logger.info(df.tail().to_string(index=False))

    logger.info("Step 1 complete.\n")


def run_handle_duplicates(args):
    """Step 2: Remove duplicate rows from the resolved CSV."""

    logger.info("\n" + "=" * 60)
    logger.info("STEP 2 — handle_duplicate_author_history")
    logger.info("=" * 60)

    bucket = args.bucket or S3_DATAPROC_BUCKET
    if not bucket:
        logger.error("Error: S3_DATAPROC_BUCKET is not set.")
        sys.exit(1)

    s3_client = boto3.client("s3", region_name=AWS_REGION)
    df = download_resolved_from_s3(s3_client, bucket, DEDUP_INPUT_KEY)
    df_deduped = remove_duplicates(df)

    if args.dry_run:
        logger.info(f"\n[DRY-RUN] Skipping S3 upload. Records after dedup: {len(df_deduped)}")
    else:
        upload_master_to_s3(s3_client, df_deduped, bucket, DEDUP_OUTPUT_KEY)

    logger.info(f"Records: {len(df)} → {len(df_deduped)} (removed {len(df) - len(df_deduped)})")
    logger.info("Step 2 complete.\n")


def run_prepare_seed(args):
    """Step 3: Strip helper columns to produce the seed CSV."""

    logger.info("\n" + "=" * 60)
    logger.info("STEP 3 — prepare_seed_author_history")
    logger.info("=" * 60)

    bucket = args.bucket or S3_DATAPROC_BUCKET
    if not bucket:
        logger.error("Error: S3_DATAPROC_BUCKET is not set.")
        sys.exit(1)

    s3_client = boto3.client("s3", region_name=AWS_REGION)
    df = download_master_from_s3(s3_client, bucket, MASTER_INPUT_KEY)
    df_seed = prepare_seed_data(df)

    if args.dry_run:
        logger.info(f"\n[DRY-RUN] Skipping S3 upload. Seed rows: {len(df_seed)}, columns: {list(df_seed.columns)}")
    else:
        upload_seed_to_s3(s3_client, df_seed, bucket, SEED_OUTPUT_KEY)

    logger.info(f"Columns: {len(df.columns)} → {len(df_seed.columns)}")
    logger.info("Step 3 complete.\n")


def run_insert_to_db(args):
    """Step 4: Insert seed CSV rows into api_author_history."""

    logger.info("\n" + "=" * 60)
    logger.info("STEP 4 — insert_to_db")
    logger.info("=" * 60)

    bucket = args.bucket or S3_DATAPROC_BUCKET
    if not bucket:
        logger.error("Error: S3_DATAPROC_BUCKET is not set.")
        sys.exit(1)

    s3_client = boto3.client("s3", region_name=AWS_REGION)
    df = read_seed_from_s3(s3_client, bucket, SEED_INPUT_KEY)
    insert_author_history(df, dry_run=args.dry_run)

    logger.info("Step 4 complete.\n")


def main():

    parser = argparse.ArgumentParser(
        description="Run the full author_history pipeline (steps 1-4)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process data but skip all S3 uploads and DB writes.",
    )
    parser.add_argument(
        "--bucket",
        type=str,
        default=S3_DATAPROC_BUCKET,
        help="S3 bucket name (default: S3_DATAPROC_BUCKET from settings).",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("AUTHOR HISTORY PIPELINE")
    if args.dry_run:
        logger.info("  [DRY-RUN mode — no uploads or DB writes]")
    logger.info("=" * 60)

    run_find_area_id(args)
    run_handle_duplicates(args)
    run_prepare_seed(args)
    run_insert_to_db(args)

    logger.info("\n" + "=" * 60)
    logger.info("ALL STEPS COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
