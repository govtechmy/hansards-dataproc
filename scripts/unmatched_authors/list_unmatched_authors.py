"""
Consolidated Unmatched Authors from S3

This script reads unmatched authors JSON files from all houses (dn, dr, kkdr) from S3 bucket
and consolidates them into a single CSV/XLSX file.

Output:
    s3://<bucket>/unmatched_authors/unmatched_authors_years/all_unmatched_authors.csv
    s3://<bucket>/unmatched_authors/unmatched_authors_years/all_unmatched_authors.xlsx

Output format:
    author | total_mentions | years_appeared | documents_list
    
Note: Documents from all houses (DN, DR, KKDR) are combined for each author.
"""

import os
import re
import json
import io
import argparse
import logging
from collections import defaultdict
from typing import Optional

import boto3
from botocore.exceptions import ClientError
import pandas as pd

from hansards_pipelines.hansards_pipelines.settings import S3_DATAPROC_BUCKET

# S3 Configuration
S3_BUCKET = S3_DATAPROC_BUCKET
S3_UNMATCHED_AUTHORS = "unmatched_authors"
HOUSES = ["dn", "dr", "kkdr"]
LOG_LEVEL = logging.INFO

logger = logging.getLogger(__name__)


def get_s3_client():
    """Create and return an S3 client."""
    return boto3.client("s3")


def extract_date_from_filename(filename: str) -> Optional[str]:
    """
    Extract date from filename like 'dr_1980-11-25.json'.
    Returns the date string (YYYY-MM-DD) or None if not found.
    """
    match = re.search(r'_(\d{4}-\d{2}-\d{2})\.json$', filename)
    if match:
        return match.group(1)
    return None


def extract_year_from_date(date_str: str) -> Optional[int]:
    """Extract year from date string YYYY-MM-DD."""
    try:
        return int(date_str.split("-")[0])
    except (ValueError, IndexError):
        return None


def list_json_files(s3_client, bucket: str, prefix: str) -> list:
    """List all JSON files under a given S3 prefix."""
    files = []
    paginator = s3_client.get_paginator("list_objects_v2")
    
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        if "Contents" in page:
            for obj in page["Contents"]:
                key = obj["Key"]
                if key.endswith(".json"):
                    files.append(key)
    return files


def read_json_from_s3(s3_client, bucket: str, key: str) -> list:
    """Read and parse a JSON file from S3."""
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")
        return json.loads(content)
    except ClientError as e:
        logger.error(f"Error reading S3 object {key}: {e}")
        raise SystemExit(1)
    except UnicodeDecodeError as e:
        logger.error(f"Error decoding UTF-8 content from {key}: {e}")
        raise SystemExit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON from {key}: {e}")
        raise SystemExit(1)


def aggregate_all_houses(s3_client, bucket: str) -> list:
    """
    Aggregate all unmatched authors from all houses.
    
    Returns:
        list: [{"author": ..., "document": ..., "year": ...}, ...]
    """
    all_records = []
    
    for house in HOUSES:
        prefix = f"{S3_UNMATCHED_AUTHORS}/{house}/"
        files = list_json_files(s3_client, bucket, prefix)
        
        logger.info(f"Found {len(files)} files for house: {house.upper()}")
        
        for file_key in files:
            filename = os.path.basename(file_key)
            date_str = extract_date_from_filename(filename)
            
            if not date_str:
                logger.warning(f"Skipping file with unrecognized format: {filename}")
                continue
                
            year = extract_year_from_date(date_str)
            if not year:
                logger.warning(f"Could not extract year from: {date_str}")
                continue
            
            # Read the JSON file
            authors = read_json_from_s3(s3_client, bucket, file_key)
            
            # Add each author to records
            for author in authors:
                # Normalize None and empty/whitespace-only strings
                author_name = "(NULL/EMPTY)" if author is None or not str(author).strip() else author
                all_records.append({
                    "author": author_name,
                    "document": filename.replace(".json", ""),
                    "year": year
                })
    
    return all_records


def create_consolidated_dataframe(all_records: list) -> pd.DataFrame:
    """
    Create a consolidated summary DataFrame for all houses.
    Authors are aggregated across all houses - documents from DN, DR, KKDR are combined.
    
    Output format:
        author | total_mentions | years_appeared | documents_list
    """
    if not all_records:
        return pd.DataFrame(columns=["author", "total_mentions", "years_appeared", "documents_list"])
    
    df = pd.DataFrame(all_records)
    
    # Aggregate by author only (combining all houses)
    summary = df.groupby(["author"]).agg({
        "year": lambda x: sorted(set(x)),
        "document": lambda x: list(x)
    }).reset_index()
    
    # Calculate total mentions
    summary["total_mentions"] = summary["document"].apply(len)
    
    # Format years appeared
    summary["years_appeared"] = summary["year"].apply(lambda x: ", ".join(map(str, x)))
    
    # Get unique documents sorted as comma-separated string
    summary["documents_list"] = summary["document"].apply(lambda x: ", ".join(sorted(set(x))))
    
    # Clean up and sort
    summary = summary.drop(columns=["year", "document"])
    summary = summary.sort_values(["total_mentions", "author"], ascending=[False, True])
    
    # Reorder columns
    return summary[["author", "total_mentions", "years_appeared", "documents_list"]]


def save_to_s3(s3_client, bucket: str, df: pd.DataFrame):
    """Save DataFrame to S3 as both CSV and XLSX."""
    base_key = f"{S3_UNMATCHED_AUTHORS}/unmatched_authors_years/all_unmatched_authors"
    
    # Save CSV (utf-8-sig for Excel compatibility with non-ASCII characters)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_key = f"{base_key}.csv"
    s3_client.put_object(
        Bucket=bucket,
        Key=csv_key,
        Body=csv_buffer.getvalue().encode("utf-8-sig"),
        ContentType="text/csv"
    )
    logger.info(f"Uploaded: s3://{bucket}/{csv_key}")
    
    # Save XLSX
    xlsx_buffer = io.BytesIO()
    df.to_excel(xlsx_buffer, index=False, engine="openpyxl")
    xlsx_buffer.seek(0)
    xlsx_key = f"{base_key}.xlsx"
    s3_client.put_object(
        Bucket=bucket,
        Key=xlsx_key,
        Body=xlsx_buffer.getvalue(),
        ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    logger.info(f"Uploaded: s3://{bucket}/{xlsx_key}")


def save_to_local(df: pd.DataFrame, output_dir: str):
    """Save DataFrame locally as both CSV and XLSX."""
    os.makedirs(output_dir, exist_ok=True)
    
    base_path = os.path.join(output_dir, "all_unmatched_authors")
    
    # Save CSV (utf-8-sig for Excel compatibility with non-ASCII characters)
    csv_path = f"{base_path}.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    logger.info(f"Saved: {csv_path}")
    
    # Save XLSX
    xlsx_path = f"{base_path}.xlsx"
    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    logger.info(f"Saved: {xlsx_path}")


def run(local_output: Optional[str] = None):
    """
    Run the consolidation of unmatched authors from all houses.
    
    Args:
        local_output: If provided, save files locally to this directory instead of S3.
    """
    logger.info("=" * 60)
    logger.info("Consolidating All Unmatched Authors")
    logger.info(f"Bucket: {S3_BUCKET}")
    logger.info(f"Houses: {', '.join([h.upper() for h in HOUSES])}")
    if local_output:
        logger.info(f"Local Output: {local_output}")
    logger.info("=" * 60)
    
    s3_client = get_s3_client()
    
    # Aggregate all data from all houses
    logger.info("Aggregating data from all houses...")
    all_records = aggregate_all_houses(s3_client, S3_BUCKET)
    
    if not all_records:
        logger.warning("No data found!")
        return
    
    # Create consolidated dataframe
    df = create_consolidated_dataframe(all_records)
    
    # Statistics
    unique_authors = len(df)
    total_mentions = df["total_mentions"].sum()
    
    logger.info("=" * 40)
    logger.info("Summary Statistics")
    logger.info("=" * 40)
    logger.info(f"Unique authors: {unique_authors}")
    logger.info(f"Total mentions: {total_mentions}")
    
    # Save
    logger.info("=" * 40)
    logger.info("Saving files...")
    logger.info("=" * 40)
    
    if local_output:
        save_to_local(df, local_output)
    else:
        save_to_s3(s3_client, S3_BUCKET, df)
    
    logger.info("Done!")


def main():
    parser = argparse.ArgumentParser(
        description="Consolidate unmatched authors from all houses into a single CSV/XLSX"
    )
    parser.add_argument(
        "--local", "-l",
        type=str,
        default=None,
        help="Save files locally to this directory instead of uploading to S3"
    )
    args = parser.parse_args()

    logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(message)s")

    run(local_output=args.local)


if __name__ == "__main__":
    main()
