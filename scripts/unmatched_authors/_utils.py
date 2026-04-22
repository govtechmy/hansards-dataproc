"""
Shared utilities for unmatched authors scripts.
"""

import csv
import os
import re
import json
import io
from typing import Optional


import boto3
import numpy as np
from botocore.exceptions import ClientError, TokenRetrievalError, NoCredentialsError, ProfileNotFound
import pandas as pd

from hansards_pipelines.settings import S3_DATAPROC_BUCKET #type: ignore



# S3 Configuration
S3_BUCKET = S3_DATAPROC_BUCKET
S3_UNMATCHED_AUTHORS = "unmatched_authors"
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
    except ProfileNotFound as e:
        print(f"\nAWS Profile Error: {e}")
        print(f"\nThe profile '{profile_name}' was not found.")
        print("Please check your ~/.aws/config file for available profiles.")
        raise SystemExit(1)
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


def is_valid_document_name(doc_name: str) -> bool:
    """
    Check if document name starts with valid prefix (dr, dn, or kkdr).
    """
    if not isinstance(doc_name, str):
        return False
    doc_lower = doc_name.lower().strip()
    return doc_lower.startswith(("dr_", "dn_", "kkdr_"))


def is_valid_author(author) -> bool:
    """
    Check if author is a valid string (not a number, date fragment, or empty).
    Valid examples: Tuan Kerk Kim Hock, Dr Tan Seng Giaw
    """
    if not isinstance(author, str):
        return False
    
    author = author.strip()
    
    if not author:
        return False
    
    if re.match(r'^-\d+', author):
        return False
    
    if author.lstrip('-').isdigit():
        return False
    
    # Skip if it looks like a date fragment (e.g., -25, 11-25, 1982-11-25)
    # Date fragments typically match patterns like: -XX, XX-XX, XXXX-XX-XX
    date_fragment_pattern = r'^-?\d{1,4}(-\d{1,2})?(-\d{1,2})?$'
    if re.match(date_fragment_pattern, author):
        return False
    
    return True


def validate_row(row: pd.Series) -> bool:
    """
    Validate a row has correct data types:
    - author: string (not a number or date fragment)
    - total_mentions: int
    - years_appeared: string of years (e.g., "1990, 1991, 1992")
    - documents_list: doc names that start with dr_, dn_, or kkdr_
    
    Returns True if row is valid, False otherwise.
    """
    # Check author is a valid string
    if not is_valid_author(row["author"]):
        return False
    
    total_mentions = row["total_mentions"]
    if isinstance(total_mentions, str):
        # If it's a string, it's invalid (could be shifted column data)
        return False
    if not isinstance(total_mentions, (int, np.integer)):
        return False
    
    # years_appeared should be a string of years like "1990, 1991, 1992"
    years_appeared = row["years_appeared"]
    if not isinstance(years_appeared, str):
        return False
    # Validate each year is a 4-digit number
    years = [y.strip() for y in years_appeared.split(",")]
    for year in years:
        if not year.isdigit() or len(year) != 4:
            return False
    
    if not isinstance(row["documents_list"], str):
        return False
    
    doc_names = [d.strip() for d in row["documents_list"].split(",")]
    if not doc_names or not doc_names[0]:
        return False
    
    for doc_name in doc_names:
        if doc_name and not is_valid_document_name(doc_name):
            return False
    
    return True


def create_summary_dataframe(all_records: list) -> pd.DataFrame:
    """
    Create a summary DataFrame.
    
    Output format:
        author | total_mentions | years_appeared | documents_list
    
    Rows with invalid data types are skipped:
    - author: must be string
    - total_mentions: must be int
    - years_appeared: must be int
    - documents_list: doc names must start with dr, dn, or kkdr
    """
    if not all_records:
        return pd.DataFrame(columns=["author", "total_mentions", "years_appeared", "documents_list"])
    
    df = pd.DataFrame(all_records)
    
    summary = df.groupby(["author"]).agg({
        "year": lambda x: sorted(set(x)),
        "document": lambda x: list(x)
    }).reset_index()
    
    summary["total_mentions"] = summary["document"].apply(len)
    
    # Convert years list to comma-separated string (e.g., "1990, 1991, 1992")
    summary["years_appeared"] = summary["year"].apply(lambda x: ", ".join(str(y) for y in sorted(set(x))))
    
    summary["documents_list"] = summary["document"].apply(lambda x: ", ".join(sorted(set(x))))
    
    summary = summary.drop(columns=["year", "document"])
    summary = summary.sort_values(["total_mentions", "author"], ascending=[False, True])
    
    result = summary[["author", "total_mentions", "years_appeared", "documents_list"]].copy()
    
    initial_count = len(result)
    valid_mask = result.apply(validate_row, axis=1)
    
    skipped_rows = result[~valid_mask]
    if len(skipped_rows) > 0:
        print(f"\nSkipping {len(skipped_rows)} invalid rows:")
        for _, row in skipped_rows.iterrows():
            print(f"  - author='{row['author']}', total_mentions={row['total_mentions']}, years_appeared={row['years_appeared']}")
    
    result = result[valid_mask].reset_index(drop=True)
    
    return result


def save_dataframe_to_s3(s3_client, bucket: str, df: pd.DataFrame, base_key: str):
    """Save DataFrame to S3 as both CSV and XLSX."""
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False, quoting=csv.QUOTE_ALL)
    csv_key = f"{base_key}.csv"
    s3_client.put_object(
        Bucket=bucket,
        Key=csv_key,
        Body=csv_buffer.getvalue().encode("utf-8-sig"),
        ContentType="text/csv"
    )
    print(f"Uploaded: s3://{bucket}/{csv_key}")
    
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
    print(f"Uploaded: s3://{bucket}/{xlsx_key}")


def save_dataframe_to_local(df: pd.DataFrame, output_dir: str, filename: str):
    """Save DataFrame locally as both CSV and XLSX."""
    os.makedirs(output_dir, exist_ok=True)
    
    base_path = os.path.join(output_dir, filename)
    
    csv_path = f"{base_path}.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_ALL)
    print(f"Saved: {csv_path}")
    
    xlsx_path = f"{base_path}.xlsx"
    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    print(f"Saved: {xlsx_path}")
