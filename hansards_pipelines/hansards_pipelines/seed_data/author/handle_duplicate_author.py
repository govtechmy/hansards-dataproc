"""
Deduplicate author records from S3 CSV.

Source of truth: CSV stored in S3.

Pipeline:
S3 master CSV
    ↓
validate primary key (new_author_id)
    ↓
normalize names
    ↓
detect duplicate names
    ↓
detect attribute conflicts
    ↓
dedupe name + birth_year + sex
    ↓
upload seed CSV to S3
    ↓
load to DB

| Case                               | Result         |
| ---------------------------------- | -------------- |
| duplicate `new_author_id`          | raise Error     |
| same name + same birth_year + sex  | merged         |
| same name but different birth_year | kept           |
| same name but different sex        | kept           |
| conflicting attributes             | logged         |
| clean CSV                          | uploaded to S3 |

"""

import logging
from io import StringIO

import boto3
import pandas as pd

from hansards_pipelines import settings

logger = logging.getLogger(__name__)


def download_from_s3(s3_client, bucket, key):
    """Download CSV from S3"""

    logger.info("Downloading CSV from S3...")
    logger.info(f" Bucket: {bucket}")
    logger.info(f" Key: {key}")

    response = s3_client.get_object(Bucket=bucket, Key=key)
    csv_content = response["Body"].read().decode("utf-8")

    df = pd.read_csv(StringIO(csv_content))

    logger.info(f" Loaded {len(df)} records")
    logger.info(f" Columns: {list(df.columns)}")

    required_columns = ["new_author_id", "name", "birth_year", "sex"]

    missing = [c for c in required_columns if c not in df.columns]

    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    return df


def normalize_names(df):
    """Normalize names for duplicate detection"""

    return (
        df["name"]
        .str.lower()
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

def check_duplicate_ids(df):
    """Ensure new_author_id is unique"""

    if "new_author_id" not in df.columns:
        raise ValueError("CSV missing required column 'new_author_id'")

    duplicates = df[df.duplicated("new_author_id", keep=False)]

    if duplicates.empty:
        logger.info("No duplicate new_author_id found")
        return

    logger.error(f"Found {duplicates['new_author_id'].nunique()} duplicated new_author_id values")

    logger.error("\nDuplicated ID rows:\n%s", duplicates.to_string(index=False))

    raise ValueError("Duplicate new_author_id detected in author.csv. Fix the csv before proceeding.")

def check_duplicates(df):
    """Log duplicate normalized names"""

    logger.info("\nChecking duplicate names...")

    duplicates = df[df.duplicated("_normalized_name", keep=False)]

    if duplicates.empty:
        logger.info(" No duplicate names found")
        return

    dup_count = len(duplicates)
    unique_dup_names = duplicates["_normalized_name"].nunique()

    logger.warning(f" Found {dup_count} duplicate rows ({unique_dup_names} unique names)")

    logger.info("\nSample duplicate names:")

    counts = duplicates["_normalized_name"].value_counts().head(20)

    for name, count in counts.items():
        original = duplicates[duplicates["_normalized_name"] == name]["name"].iloc[0]
        logger.info(f" '{original}' appears {count} times")


def detect_conflicts(df):
    """
    Detect conflicting attributes among duplicate names
    (vectorized implementation for performance)
    """

    logger.info("\nChecking attribute conflicts...")

    conflict_columns = ["birth_year", "ethnicity", "sex"]

    available_cols = [c for c in conflict_columns if c in df.columns]

    if not available_cols:
        logger.info(" No conflict columns found")
        return

    dup_names = df["_normalized_name"].duplicated(keep=False)

    agg = (
        df[dup_names]
        .groupby("_normalized_name")[available_cols]
        .nunique(dropna=False)
        .reset_index()
    )

    conflict_mask = (agg[available_cols] > 1).any(axis=1)

    conflicts = agg[conflict_mask]

    if conflicts.empty:
        logger.info(" No attribute conflicts found")
        return

    logger.warning(f" Found {len(conflicts)} names with conflicting attributes")

    sample_names = conflicts["_normalized_name"].head(20)

    rows = df[df["_normalized_name"].isin(sample_names)]

    logger.warning("\nSample conflicts:\n%s", rows.to_string(index=False))


def deduplicate(df):
    """Deduplicate using normalized name + birth_year + sex"""

    logger.info("\nDeduplicating authors...")

    before = len(df)

    df_deduped = df.drop_duplicates(
        subset=["_normalized_name", "birth_year", "sex"],
        keep="first",
    ).copy()

    after = len(df_deduped)

    logger.info(f"Records before: {before}")
    logger.info(f"Records after : {after}")
    logger.info(f"Removed       : {before - after}")

    return df_deduped


def upload_to_s3(s3_client, df, bucket, key):
    """Upload cleaned CSV to S3"""

    logger.info("\nUploading cleaned CSV to S3...")
    logger.info(f" Bucket: {bucket}")
    logger.info(f" Key: {key}")
    logger.info(f" Records: {len(df)}")

    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)

    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=csv_buffer.getvalue().encode("utf-8"),
        ContentType="text/csv",
    )

    logger.info(f" Successfully uploaded to s3://{bucket}/{key}")