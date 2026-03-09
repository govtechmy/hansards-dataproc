import argparse
import logging
import sys
from pathlib import Path

from hansards_pipelines.seed_data.author.handle_duplicate_author import (
    load_csv_data,
    load_db_data,
    check_csv_duplicates,
    check_cross_duplicates,
    merge_and_deduplicate,
    save_output,
)
from hansards_pipelines import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger(__name__)


def run_handle_duplicates(args):
    """Step 1: Check CSV and DB for duplicates, merge and deduplicate."""

    logger.info("STEP 1 — handle_duplicate_author")

    # Configuration
    project_root = Path(__file__).parent.parent.parent.parent.parent
    csv_path = project_root / "scripts" / "ahli_parlimen" / "outputs" / "author.csv"
    output_dir = Path(__file__).parent / "output"
    db_url = settings.HANSARD_DB_URL

    logger.info(f"\nConfiguration:")
    logger.info(f"  CSV Input: {csv_path}")
    logger.info(f"  Output Dir: {output_dir}")
    logger.info(f"  DB URL: {'Configured' if db_url else 'Not configured'}")

    # Step 1: Load CSV data
    csv_df = load_csv_data(str(csv_path))

    # Step 2: Load DB data (if available)
    db_df = load_db_data(db_url) if db_url else None
    if db_df is None:
        import pandas as pd
        db_df = pd.DataFrame()

    # Step 3: Check for duplicates in CSV
    check_csv_duplicates(csv_df, "CSV")

    # Step 4: Check for duplicates in DB (if available)
    if not db_df.empty:
        check_csv_duplicates(db_df, "DATABASE")

    # Step 5: Check for cross-duplicates
    if not db_df.empty:
        check_cross_duplicates(csv_df, db_df)

    # Step 6: Merge and deduplicate
    final_df = merge_and_deduplicate(csv_df, db_df)

    # Step 7: Save output
    if args.dry_run:
        logger.info(f"\n[DRY-RUN] Skipping file write. Preview of first 5 rows:")
        logger.info(final_df.head().to_string(index=False))
    else:
        output_path = save_output(final_df, str(output_dir))
        logger.info(f"\nOutput saved to: {output_path}")

    logger.info(f"\nRecords: CSV={len(csv_df)}, DB={len(db_df)} → Final={len(final_df)}")
    logger.info("Step 1 complete.\n")

    return final_df


def main():
    """Main execution"""

    parser = argparse.ArgumentParser(
        description="Run the author deduplication pipeline."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process data but skip file writes (preview only).",
    )
    args = parser.parse_args()

    logger.info("AUTHOR PIPELINE")
    if args.dry_run:
        logger.info("  [DRY-RUN mode — no file writes]")

    # Run deduplication
    run_handle_duplicates(args)

    logger.info("ALL STEPS COMPLETE")


if __name__ == "__main__":
    main()
