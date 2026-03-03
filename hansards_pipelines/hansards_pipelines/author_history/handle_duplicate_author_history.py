"""
Handle duplicate author_history records from S3 CSV
Removes duplicate rows based on: author_name + party + area_id + start_date + end_date
"""
import os
import logging
import boto3
from dotenv import load_dotenv
from io import StringIO
import pandas as pd

load_dotenv()
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
        logger.warning(f" Warning: Missing columns for duplicate detection: {missing_columns}")

    logger.info(f" Using duplicate detection columns: {existing_columns}")

    # Remove duplicates - keep first occurrence
    df_deduped = df.drop_duplicates(subset=existing_columns, keep='first')
    
    final_count = len(df_deduped)
    removed_count = initial_count - final_count

    logger.info(f" Final records: {final_count}")
    logger.info(f" Removed {removed_count} duplicate rows")

    if removed_count > 0:
        logger.info(f" Duplicate removal rate: {(removed_count/initial_count)*100:.2f}%")

    return df_deduped


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


def main():
    # Configuration
    bucket = os.getenv('S3_DATAPROC_BUCKET', 'my.gov.parlimen.hsd-dataproc-bucket-dev')
    aws_region = os.getenv('AWS_REGION', 'ap-southeast-5')
    input_key = 'canonical/preprocessing/author_history/resolved/author_history.csv'
    output_key = 'canonical/preprocessing/master/author_history.csv'
    logger.info("AUTHOR HISTORY DUPLICATE REMOVER")
    
    # Initialize S3 client
    s3_client = boto3.client("s3", region_name=aws_region)
    
    # Download input CSV from S3
    df = download_from_s3(s3_client, bucket, input_key)
    
    # Show current columns
    logger.info(f"Columns in CSV: {list(df.columns)}")
    
    # Remove duplicates (keeps existing record_id from first occurrence)
    df_deduped = remove_duplicates(df)
    
    # Upload deduplicated CSV to S3
    upload_to_s3(s3_client, df_deduped, bucket, output_key)
    
    logger.info("COMPLETE!")
    logger.info(f"Input:  s3://{bucket}/{input_key}")
    logger.info(f"Output: s3://{bucket}/{output_key}")
    logger.info(f"Records: {len(df)} → {len(df_deduped)} (removed {len(df) - len(df_deduped)})")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    main()
