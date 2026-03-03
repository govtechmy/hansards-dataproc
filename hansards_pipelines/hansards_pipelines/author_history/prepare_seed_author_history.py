"""
Prepare seed data for author_history table

Input: s3://dataproc/canonical/preprocessing/master/author_history.csv
Output: s3://dataproc/canonical/seed/author_history.csv

Removes helper columns (author_name, area_name, area_state) to match database schema.
"""
import os
import logging
import boto3
from dotenv import load_dotenv
from io import StringIO
import pandas as pd

# Load environment variables
load_dotenv()
logger = logging.getLogger(__name__)


def download_from_s3(s3_client, bucket, key):
    """Download CSV file from S3 and return as pandas DataFrame"""
    logger.info("Downloading from S3...")
    logger.info(f"  Bucket: {bucket}")
    logger.info(f"  Key: {key}")
    
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        csv_content = response['Body'].read().decode('utf-8')
        
        # Read CSV into DataFrame
        df = pd.read_csv(StringIO(csv_content))
        logger.info(f"  Downloaded {len(df)} rows")
        logger.info(f"  Columns: {list(df.columns)}")
        return df
    except Exception as e:
        logger.error(f"  Error downloading from S3: {e}")
        raise


def prepare_seed_data(df):
    """
    Remove helper columns and keep only database table columns.
    
    Database schema columns (api_author_history):
    - record_id
    - author_id
    - party
    - area_id
    - exec_posts
    - service_posts
    - start_date
    - end_date
    
    Columns to remove:
    - author_name (helper)
    - area_name (helper)
    - area_state (helper)
    """
    logger.info("Preparing seed data...")
    
    # Define the columns to keep (matching database schema)
    db_columns = [
        'record_id',
        'author_id',
        'party',
        'area_id',
        'exec_posts',
        'service_posts',
        'start_date',
        'end_date'
    ]
    
    # Check which columns exist in the DataFrame
    existing_columns = [col for col in db_columns if col in df.columns]
    missing_columns = [col for col in db_columns if col not in df.columns]
    
    if missing_columns:
        logger.warning(f"  Missing columns: {missing_columns}")
    
    logger.info(f"  Keeping columns: {existing_columns}")
    
    # Select only the database columns
    df_seed = df[existing_columns].copy()
    
    # Show columns that were removed
    removed_columns = [col for col in df.columns if col not in db_columns]
    if removed_columns:
        logger.info(f"  Removed helper columns: {removed_columns}")
    
    logger.info(f"  Final seed data: {len(df_seed)} rows, {len(df_seed.columns)} columns")
    
    return df_seed


def upload_to_s3(s3_client, df, bucket, key):
    """Upload DataFrame as CSV to S3"""
    logger.info("Uploading to S3...")
    logger.info(f"  Bucket: {bucket}")
    logger.info(f"  Key: {key}")
    logger.info(f"  Records: {len(df)}")
    logger.info(f"  Columns: {list(df.columns)}")
    
    try:
        # Convert DataFrame to CSV string
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_content = csv_buffer.getvalue()
        
        # Upload to S3
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=csv_content.encode('utf-8'),
            ContentType='text/csv'
        )
        
        logger.info(f"  ✓ Successfully uploaded to s3://{bucket}/{key}")
        
    except Exception as e:
        logger.error(f"  ✗ Error uploading to S3: {e}")
        raise


def main():
    # Configuration
    bucket = os.getenv('S3_DATAPROC_BUCKET', 'my.gov.parlimen.hsd-dataproc-bucket-dev')
    aws_region = os.getenv('AWS_REGION', 'ap-southeast-5')
    input_key = 'canonical/preprocessing/master/author_history.csv'
    output_key = 'canonical/seed/author_history.csv'
    
    logger.info("=" * 80)
    logger.info("PREPARE SEED AUTHOR HISTORY")
    logger.info("=" * 80)
    
    # Initialize S3 client
    s3_client = boto3.client("s3", region_name=aws_region)
    
    # Download master CSV from S3
    df = download_from_s3(s3_client, bucket, input_key)
    
    # Prepare seed data (remove helper columns)
    df_seed = prepare_seed_data(df)
    
    # Upload seed CSV to S3
    upload_to_s3(s3_client, df_seed, bucket, output_key)
    
    logger.info("=" * 80)
    logger.info("COMPLETE!")
    logger.info(f"Input:  s3://{bucket}/{input_key}")
    logger.info(f"Output: s3://{bucket}/{output_key}")
    logger.info(f"Records: {len(df)} → {len(df_seed)}")
    logger.info(f"Columns: {len(df.columns)} → {len(df_seed.columns)}")
    logger.info("=" * 80)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    main()
