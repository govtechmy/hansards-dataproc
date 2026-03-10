"""
Main entry point for the author seed pipeline.

Pipeline:
1. Download author CSV from S3
2. Validate primary key (new_author_id)
3. Normalize names
4. Detect duplicate names
5. Detect attribute conflicts
6. Deduplicate records
7. Upload cleaned CSV to S3
8. Load cleaned CSV into database

Usage:
    python main.py --dry-run
"""


import argparse
import logging
import boto3

from hansards_pipelines.seed_data.author.handle_duplicate_author import (
    download_from_s3,
    check_duplicates,
    check_duplicate_ids,
    detect_conflicts,
    deduplicate,
    upload_to_s3,
    normalize_names,
)

from hansards_pipelines.seed_data.author.load_author_csv_to_db import (
    load_author_csv_to_db
)

from hansards_pipelines import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)

logger = logging.getLogger(__name__)


def run_handle_duplicates_author(args):
    """Step 1: Deduplicate author CSV in S3."""

    logger.info("STEP 1 — handle_duplicate_author")

    bucket = settings.S3_DATAPROC_BUCKET
    region = settings.AWS_REGION or "ap-southeast-5"

    input_key = "canonical/master/author.csv"
    output_key = "canonical/seed/author.csv"

    logger.info("\nConfiguration:")
    logger.info(f"  Input : s3://{bucket}/{input_key}")
    logger.info(f"  Output: s3://{bucket}/{output_key}")

    s3_client = boto3.client("s3", region_name=region)

    df = download_from_s3(s3_client, bucket, input_key)

    check_duplicate_ids(df)

    df["_normalized_name"] = normalize_names(df)

    check_duplicates(df)

    detect_conflicts(df)

    final_df = deduplicate(df)

    final_df = final_df.drop(columns=["_normalized_name"])

    if args.dry_run:
        logger.info("\n[DRY-RUN] Preview:")
        logger.info(final_df.head().to_string(index=False))
    else:
        upload_to_s3(s3_client, final_df, bucket, output_key)

    logger.info(
        f"\nRecords: input={len(df)} → output={len(final_df)} "
        f"(removed {len(df) - len(final_df)})"
    )

    logger.info("Step 1 complete.\n")

    return output_key


def run_load_to_db(s3_key):
    """Step 2: Load cleaned CSV into database."""

    logger.info("STEP 2 — load_author_csv_to_db")

    result = load_author_csv_to_db(
        s3_bucket=settings.S3_DATAPROC_BUCKET,
        s3_key=s3_key,
        db_url=settings.HANSARD_DB_URL,
        context=type("obj", (), {"log": logger}),
        aws_region=settings.AWS_REGION,
    )

    logger.info(f"\nDB Load Result: {result}")
    logger.info("Step 2 complete.\n")


def main():

    parser = argparse.ArgumentParser(description="Run the author seed pipeline.")
    parser.add_argument("--dry-run", action="store_true", help="Run deduplication only, skip DB load.")
    args = parser.parse_args()

    logger.info("AUTHOR PIPELINE")

    if args.dry_run:
        logger.info("  [DRY-RUN mode — no uploads or DB writes]")

    try:
        # Step 1
        seed_key = run_handle_duplicates_author(args)

        # Step 2
        if not args.dry_run:
            run_load_to_db(seed_key)

        logger.info("ALL STEPS COMPLETE")

    except ValueError as e:
        logger.error(f"\nPipeline failed: {e}")
        raise


if __name__ == "__main__":
    main()