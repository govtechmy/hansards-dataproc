"""
Handle duplicate author_history records from S3 CSV
Removes duplicate rows based on: author_name + party + area_id + start_date + end_date
"""
import os
import logging
import boto3
from io import StringIO
import pandas as pd
from hansards_pipelines import settings

logger = logging.getLogger(__name__)


def download_from_s3(s3_client, bucket, key):
    """Download CSV file from S3 and return as pandas DataFrame"""
    logger.info(f"Downloading from S3...")
    logger.info(f" Bucket: {bucket}")
    logger.info(f" Key: {key}")

    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        csv_content = response['Body'].read().decode('utf-8')
        
        # Read CSV into DataFrame
        df = pd.read_csv(StringIO(csv_content))
        logger.info(f"  Downloaded {len(df)} rows")
        return df
    except Exception as e:
        logger.error(f"  Error downloading from S3: {e}")
        raise


def remove_duplicates(df):
    """
    Remove duplicate rows based on:
    - author_name
    - party
    - area_id
    - start_date
    - end_date
    """
    logger.info("\nRemoving duplicates...")
    
    initial_count = len(df)
    logger.info(f"  Initial records: {initial_count}")

    # Define duplicate criteria columns
    duplicate_columns = ['author_name', 'party', 'area_id', 'start_date', 'end_date']
    
    # Check which columns actually exist in the DataFrame
    existing_columns = [col for col in duplicate_columns if col in df.columns]
    missing_columns = [col for col in duplicate_columns if col not in df.columns]
    
    if missing_columns:
        error_msg = (
            f"Cannot proceed with deduplication: missing required columns {missing_columns}. "
            f"Deduplication requires all of: {duplicate_columns}"
        )
        logger.error(f" Error: {error_msg}")
        raise ValueError(error_msg)

    logger.info(f" Using duplicate detection columns: {existing_columns}")

    # Identify duplicate rows
    duplicates = df[df.duplicated(subset=existing_columns, keep=False)]

    if not duplicates.empty:
        logger.info("\nDuplicate rows detected:")
        logger.info("Showing first 20 duplicate rows:")
        logger.info(duplicates.head(20).to_string(index=False))

    # Remove duplicates - keep first occurrence
    df_deduped = df.drop_duplicates(subset=existing_columns, keep='first')
    
    final_count = len(df_deduped)
    removed_count = initial_count - final_count

    logger.info(f" Final records: {final_count}")
    logger.info(f" Removed {removed_count} duplicate rows")

    return df_deduped

def check_duplicate_history_ids(df):
    """Ensure author_id + start_date combination is unique"""

    if "record_id" not in df.columns:
        raise ValueError("CSV missing required columns for validation")

    duplicates = df[df.duplicated(["record_id"], keep=False)]

    if duplicates.empty:
        logger.info("No duplicate author history primary keys found")
        return

    logger.error("Duplicate author history primary keys detected. Fix the csv before proceeding.")
    logger.error("Showing first 20 duplicate records:")
    logger.error(duplicates.head(20).to_string(index=False))

    raise ValueError("Duplicate author history records detected")

def upload_to_s3(s3_client, df, bucket, key):
    """Upload DataFrame as CSV to S3"""
    logger.info(f"\nUploading to S3...")
    logger.info(f" Bucket: {bucket}")
    logger.info(f" Key: {key}")
    logger.info(f" Records: {len(df)}")

    try:
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_content = csv_buffer.getvalue()
        
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=csv_content.encode('utf-8'),
            ContentType='text/csv'
        )

        logger.info(f"Successfully uploaded to s3://{bucket}/{key}")

    except Exception as e:
        logger.error(f"Error uploading to S3: {e}")
        raise