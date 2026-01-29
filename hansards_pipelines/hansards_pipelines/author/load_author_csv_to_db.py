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
    
    # Use provided region or default to ap-southeast-5
    region = aws_region
    s3_client = boto3.client("s3", region_name=region)
    
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
            # Create table if it doesn't exist
            context.log.info("Ensuring api_author table exists...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS api_author (
                    new_author_id INTEGER PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    birth_year INTEGER,
                    ethnicity VARCHAR(100),
                    sex VARCHAR(50)
                )
            """)
            conn.commit()
            context.log.info("Table api_author is ready")
            
            # Get existing authors to track what will be inserted vs updated
            context.log.info("Checking existing authors in database...")
            cur.execute("SELECT new_author_id, name, birth_year, ethnicity, sex FROM api_author")
            existing_authors = {row[0]: row for row in cur.fetchall()}
            context.log.info(f"Found {len(existing_authors)} existing authors in database")
            
            # Track statistics
            inserted_count = 0
            updated_count = 0
            skipped_count = 0
            
            # Prepare data for upsert
            for _, row in df_author.iterrows():
                new_author_id = int(row["new_author_id"])
                name = row["name"]
                
                birth_year = None if pd.isna(row["birth_year"]) or row["birth_year"] == "" else int(row["birth_year"])
                ethnicity = None if pd.isna(row["ethnicity"]) or row["ethnicity"] == "" else row["ethnicity"]
                sex = None if pd.isna(row["sex"]) or row["sex"] == "" else row["sex"]
                
                new_data = (new_author_id, name, birth_year, ethnicity, sex)
                
                # Check if author exists and if data has changed
                if new_author_id in existing_authors:
                    existing_data = existing_authors[new_author_id]
                    if existing_data == new_data:
                        skipped_count += 1
                        continue
                    else:
                        updated_count += 1
                else:
                    inserted_count += 1
                
                cur.execute(
                    """
                    INSERT INTO api_author (new_author_id, name, birth_year, ethnicity, sex)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (new_author_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        birth_year = EXCLUDED.birth_year,
                        ethnicity = EXCLUDED.ethnicity,
                        sex = EXCLUDED.sex
                    """,
                    (new_author_id, name, birth_year, ethnicity, sex)
                )
            
            conn.commit()
            
            context.log.info(
                f"Summary: "
                f"{len(df_author)} total records "
                f"{inserted_count} inserted, "
                f"{updated_count} updated, "
                f"{skipped_count} skipped"
            )
    
    return {
        "total_records": len(df_author),
        "inserted": inserted_count,
        "updated": updated_count,
        "skipped": skipped_count,
        "s3_path": f"s3://{s3_bucket}/{s3_key}"
    }
