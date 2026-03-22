"""
Author data management module.
Handles loading and upserting author data from CSV to database.
"""

import pandas as pd
import psycopg
import boto3
import io
from typing import Dict, Optional
from dagster import AssetExecutionContext


def load_author_csv_to_db(
    s3_bucket: str,
    s3_key: str,
    db_url: str,
    context: AssetExecutionContext,
    aws_region: Optional[str] = None
) -> Dict:
    """
    Load author data from S3 CSV into the api_author table in the database.
    Uses UPSERT logic (INSERT ... ON CONFLICT DO UPDATE) to:
    - Insert new authors that don't exist
    - Update existing authors if data has changed
    - Skip authors that already exist with the same data
    """
    context.log.info(f"Reading author data from S3: s3://{s3_bucket}/{s3_key}")

    s3_client = boto3.client("s3", region_name=aws_region or "ap-southeast-5")
    
    try:
        response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
        csv_content = response["Body"].read()
        
        df_author = pd.read_csv(io.BytesIO(csv_content))
        context.log.info(f"Loaded {len(df_author)} author records from S3")
    except Exception as e:
        raise FileNotFoundError(f"Failed to read author.csv from S3: s3://{s3_bucket}/{s3_key}. Error: {e}")
    
    if "author_id" in df_author.columns:
        df_author.rename(columns={"author_id": "new_author_id"}, inplace=True)
    
    required_columns = ["new_author_id", "name"]
    missing_columns = [col for col in required_columns if col not in df_author.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns in author.csv: {missing_columns}")
    optional_columns = ["birth_year", "ethnicity", "sex"]
    for col in optional_columns:
        if col not in df_author.columns:
            df_author[col] = None
            context.log.info(f"Added missing optional column: {col}")
    
    context.log.info(f"CSV columns: {df_author.columns.tolist()}")
    
    # Connect to database and insert data
    if not db_url:
        raise ValueError("Database URL not provided")
    
    context.log.info("Connecting to database...")
    
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:

            # Get existing authors to track what will be inserted vs updated
            context.log.info("Checking existing authors in database...")
            cur.execute("SELECT new_author_id, name, birth_year, ethnicity, sex FROM api_author")
            existing_authors = {row[0]: row for row in cur.fetchall()}
            context.log.info(f"Found {len(existing_authors)} existing authors in database")

            records = [
                (
                    int(r.new_author_id),
                    r.name,
                    None if pd.isna(r.birth_year) else int(r.birth_year),
                    None if pd.isna(r.ethnicity) else r.ethnicity,
                    None if pd.isna(r.sex) else r.sex,
                )
                for r in df_author.itertuples()
            ]

            cur.executemany(
                """
                INSERT INTO api_author (new_author_id, name, birth_year, ethnicity, sex)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (new_author_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    birth_year = EXCLUDED.birth_year,
                    ethnicity = EXCLUDED.ethnicity,
                    sex = EXCLUDED.sex
                """,
                records
            )

            conn.commit()

    context.log.info(f"UPSERT complete: {len(records)} authors processed")

    return {
        "total_records": len(records),
        "s3_path": f"s3://{s3_bucket}/{s3_key}"
    }
