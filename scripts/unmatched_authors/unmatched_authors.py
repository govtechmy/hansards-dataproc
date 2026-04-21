"""
Unmatched Authors from S3

This script reads unmatched authors JSON files from S3 bucket:

And aggregates them into a single summary file per house, saving to:
    s3://my.gov.parlimen.hsd-dataproc-bucket-dev/unmatched_authors/unmatched_authors_years/{house}_unmatched_authors.csv
    s3://my.gov.parlimen.hsd-dataproc-bucket-dev/unmatched_authors/unmatched_authors_years/{house}_unmatched_authors.xlsx

Output format:
    author | total_mentions | years_appeared | documents_list
"""

import os
import re
import json
import io
import argparse
from collections import defaultdict
from typing import Optional

import boto3
from botocore.exceptions import ClientError, TokenRetrievalError, NoCredentialsError
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# S3 Configuration
S3_BUCKET = os.getenv("S3_DATAPROC_BUCKET", "my.gov.parlimen.hsd-dataproc-bucket-dev")
S3_PREFIX = "unmatched_authors"
HOUSES = ["dn", "dr", "kkdr"]


def get_s3_client(profile_name: Optional[str] = None):
    """
    Create and return an S3 client.
    
    Args:
        profile_name: AWS profile name to use. If None, uses default credentials.
    """
    try:
        if profile_name:
            session = boto3.Session(profile_name=profile_name)
            return session.client("s3")
        return boto3.client("s3")
    except (TokenRetrievalError, NoCredentialsError) as e:
        print(f"\nAWS Credentials Error: {e}")
        print("\nPlease ensure you have valid AWS credentials.")
        print("Options:")
        print("  1. Run 'aws sso login --profile <profile_name>' to refresh SSO token")
        print("  2. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables")
        print("  3. Configure credentials in ~/.aws/credentials")
        raise SystemExit(1)


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
        print(f"Error reading S3 object {key}: {e}")
        raise SystemExit(1)
    except UnicodeDecodeError as e:
        print(f"Error decoding UTF-8 content from {key}: {e}")
        raise SystemExit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON from {key}: {e}")
        raise SystemExit(1)


def aggregate_all_data(s3_client, bucket: str, house: str) -> list:
    """
    Aggregate all unmatched authors for a given house.
    
    Returns:
        list: [{"author": ..., "document": ..., "year": ...}, ...]
    """
    prefix = f"{S3_PREFIX}/{house}/"
    files = list_json_files(s3_client, bucket, prefix)
    
    print(f"Found {len(files)} files for house: {house}")
    
    all_records = []
    
    for file_key in files:
        filename = os.path.basename(file_key)
        date_str = extract_date_from_filename(filename)
        
        if not date_str:
            print(f"Skipping file with unrecognized format: {filename}")
            continue
            
        year = extract_year_from_date(date_str)
        if not year:
            print(f"Could not extract year from: {date_str}")
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


def create_summary_dataframe(all_records: list) -> pd.DataFrame:
    """
    Create a summary DataFrame.
    
    Output format:
        author | total_mentions | years_appeared | documents_list
    """
    if not all_records:
        return pd.DataFrame(columns=["author", "total_mentions", "years_appeared", "documents_list"])
    
    df = pd.DataFrame(all_records)
    
    # Aggregate by author
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


def save_to_s3(s3_client, bucket: str, df: pd.DataFrame, house: str):
    """Save DataFrame to S3 as both CSV and XLSX."""
    base_key = f"{S3_PREFIX}/unmatched_authors_years/{house}_unmatched_authors"
    
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
    print(f"  Uploaded: s3://{bucket}/{csv_key}")
    
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
    print(f"  Uploaded: s3://{bucket}/{xlsx_key}")


def save_to_local(df: pd.DataFrame, output_dir: str, house: str):
    """Save DataFrame locally as both CSV and XLSX."""
    os.makedirs(output_dir, exist_ok=True)
    
    base_path = os.path.join(output_dir, f"{house}_unmatched_authors")
    
    # Save CSV (utf-8-sig for Excel compatibility with non-ASCII characters)
    csv_path = f"{base_path}.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"  Saved: {csv_path}")
    
    # Save XLSX
    xlsx_path = f"{base_path}.xlsx"
    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    print(f"  Saved: {xlsx_path}")


def main(profile_name: Optional[str] = None, local_output: Optional[str] = None):
    """
    Main function to aggregate unmatched authors.
    
    Args:
        profile_name: AWS profile name to use. If None, uses default credentials.
        local_output: If provided, save files locally to this directory instead of S3.
    """
    print(f"=" * 60)
    print(f"Aggregating Unmatched Authors")
    print(f"Bucket: {S3_BUCKET}")
    if profile_name:
        print(f"AWS Profile: {profile_name}")
    if local_output:
        print(f"Local Output: {local_output}")
    print(f"=" * 60)
    
    s3_client = get_s3_client(profile_name)
    
    for house in HOUSES:
        print(f"\n{'='*40}")
        print(f"Processing house: {house.upper()}")
        print(f"{'='*40}")
        
        # Aggregate all data for this house
        all_records = aggregate_all_data(s3_client, S3_BUCKET, house)
        
        if not all_records:
            print(f"No data found for house: {house}")
            continue
        
        # Create summary dataframe
        df = create_summary_dataframe(all_records)
        
        # Count unique authors and years
        unique_authors = df["author"].nunique()
        total_mentions = df["total_mentions"].sum()
        
        print(f"\nSummary: {unique_authors} unique authors, {total_mentions} total mentions")
        
        # Save
        if local_output:
            save_to_local(df, local_output, house)
        else:
            save_to_s3(s3_client, S3_BUCKET, df, house)
    
    print(f"\n{'='*60}")
    print("Done!")
    print(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Aggregate unmatched authors from S3 and save as CSV/XLSX"
    )
    parser.add_argument(
        "--profile", "-p",
        type=str,
        default=None,
        help="AWS profile name to use (e.g., 'govtech-dev')"
    )
    parser.add_argument(
        "--local", "-l",
        type=str,
        default=None,
        help="Save files locally to this directory instead of uploading to S3"
    )
    parser.add_argument(
        "--bucket", "-b",
        type=str,
        default=None,
        help=f"Override the S3 bucket (default: {S3_BUCKET})"
    )
    
    args = parser.parse_args()
    
    if args.bucket:
        S3_BUCKET = args.bucket
    
    main(profile_name=args.profile, local_output=args.local)
