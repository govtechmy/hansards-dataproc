"""
Author History Pipeline — main entry point

Runs the four steps in order:
  1. find_area_id_given_area_name  – resolve area_id from api_area and generate missing record_ids
  2. handle_duplicate_author_history – remove duplicate rows from the resolved CSV
  3. prepare_seed_author_history    – strip helper columns to produce the seed CSV
  4. insert_to_db                   – insert seed CSV rows into api_author_history

Usage:
    python main.py
    python main.py --dry-run   # skip S3 uploads and DB writes (where supported)
    python main.py --bucket my-other-bucket
"""

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger(__name__)


def run_find_area_id(args):
    """Step 1: Resolve area_id and generate missing record_ids."""
    import find_area_id_given_area_name as step

    logger.info("\n" + "=" * 60)
    logger.info("STEP 1 — find_area_id_given_area_name")
    logger.info("=" * 60)

    from hansards_pipelines.settings import AWS_REGION
    import boto3

    bucket = args.bucket
    if not bucket:
        logger.error("Error: S3_DATAPROC_BUCKET is not set.")
        sys.exit(1)

    conn = step.get_db_connection()
    try:
        area_lookup = step.build_area_lookup(conn)
    finally:
        conn.close()

    s3_client = boto3.client("s3", region_name=AWS_REGION)
    df = step.read_csv_from_s3(s3_client, bucket, step.INPUT_KEY)
    df = step.resolve_area_ids(df, area_lookup)
    df = step.generate_record_ids(df, start_id=3000)
    df = step.enforce_column_order(df)

    if args.dry_run:
        logger.info("\n[DRY-RUN] Skipping S3 upload. Preview of first 5 rows:")
        logger.info(df.head().to_string(index=False))
    else:
        step.upload_csv_to_s3(s3_client, df, bucket, step.OUTPUT_KEY)

    logger.info("Step 1 complete.\n")


def run_handle_duplicates(args):
    """Step 2: Remove duplicate rows from the resolved CSV."""
    import handle_duplicate_author_history as step

    logger.info("\n" + "=" * 60)
    logger.info("STEP 2 — handle_duplicate_author_history")
    logger.info("=" * 60)

    import os
    import boto3

    bucket = args.bucket or os.getenv("S3_DATAPROC_BUCKET", "my.gov.parlimen.hsd-dataproc-bucket-dev")
    aws_region = os.getenv("AWS_REGION", "ap-southeast-5")
    input_key = "canonical/preprocessing/author_history/resolved/author_history.csv"
    output_key = "canonical/preprocessing/master/author_history.csv"

    s3_client = boto3.client("s3", region_name=aws_region)
    df = step.download_from_s3(s3_client, bucket, input_key)
    df_deduped = step.remove_duplicates(df)

    if args.dry_run:
        logger.info(f"\n[DRY-RUN] Skipping S3 upload. Records after dedup: {len(df_deduped)}")
    else:
        step.upload_to_s3(s3_client, df_deduped, bucket, output_key)

    logger.info(f"Records: {len(df)} → {len(df_deduped)} (removed {len(df) - len(df_deduped)})")
    logger.info("Step 2 complete.\n")


def run_prepare_seed(args):
    """Step 3: Strip helper columns to produce the seed CSV."""
    import prepare_seed_author_history as step

    logger.info("\n" + "=" * 60)
    logger.info("STEP 3 — prepare_seed_author_history")
    logger.info("=" * 60)

    import os
    import boto3

    bucket = args.bucket or os.getenv("S3_DATAPROC_BUCKET", "my.gov.parlimen.hsd-dataproc-bucket-dev")
    aws_region = os.getenv("AWS_REGION", "ap-southeast-5")
    input_key = "canonical/preprocessing/master/author_history.csv"
    output_key = "canonical/seed/author_history.csv"

    s3_client = boto3.client("s3", region_name=aws_region)
    df = step.download_from_s3(s3_client, bucket, input_key)
    df_seed = step.prepare_seed_data(df)

    if args.dry_run:
        logger.info(f"\n[DRY-RUN] Skipping S3 upload. Seed rows: {len(df_seed)}, columns: {list(df_seed.columns)}")
    else:
        step.upload_to_s3(s3_client, df_seed, bucket, output_key)

    logger.info(f"Columns: {len(df.columns)} → {len(df_seed.columns)}")
    logger.info("Step 3 complete.\n")


def run_insert_to_db(args):
    """Step 4: Insert seed CSV rows into api_author_history."""
    import insert_to_db as step

    logger.info("\n" + "=" * 60)
    logger.info("STEP 4 — insert_to_db")
    logger.info("=" * 60)

    from hansards_pipelines.settings import AWS_REGION
    import boto3

    bucket = args.bucket
    if not bucket:
        logger.error("Error: S3_DATAPROC_BUCKET is not set.")
        sys.exit(1)

    s3_client = boto3.client("s3", region_name=AWS_REGION)
    df = step.read_csv_from_s3(s3_client, bucket, step.INPUT_KEY)
    step.insert_author_history(df, dry_run=args.dry_run)

    logger.info("Step 4 complete.\n")


def main():
    from hansards_pipelines.settings import S3_DATAPROC_BUCKET

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
