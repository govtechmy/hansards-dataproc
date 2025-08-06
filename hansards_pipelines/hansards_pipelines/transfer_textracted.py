import boto3
import os
import re
import argparse
import concurrent.futures

from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

PREFIX_OPTIONS = ["dewannegara", "dewanrakyat", "kamarkhas"]
MAX_CONCURRENT_JOBS = 5

REGION = os.getenv("REGION")
S3_PUBLIC_BUCKET = os.getenv("S3_PUBLIC_BUCKET")
S3_TEXTRACT_BUCKET = os.getenv("S3_TEXTRACT_BUCKET")

# === AWS Setup ===
session   = boto3.Session(region_name=REGION)
s3        = session.client("s3")

def list_csvs(prefix, year_range):
    """
    List all CSVs exclude "_layout.csv" under S3_TEXTRACT_BUCKET/prefix whose filenames match YYYY-MM-DD
    and whose year falls within year_range.
    """
    paginator = s3.get_paginator("list_objects_v2")
    csvs = []
    for page in paginator.paginate(Bucket=S3_TEXTRACT_BUCKET, Prefix=prefix):
        for o in page.get("Contents", []):
            key = o["Key"]
            if key.lower().endswith(".csv") and not key.lower().endswith("_layout.csv"):
                m = re.search(r"(\d{4})-\d{2}-\d{2}", key)
                if m and year_range[0] <= int(m.group(1)) <= year_range[1]:
                    csvs.append(key)
    return csvs

def csv_exists(s3_key):
    """
    Return True if S3_PUBLIC_BUCKET/s3_key exists.
    Treat 404 or 403 as "not found" so we retry extraction.
    """
    try:
        s3.head_object(Bucket=S3_PUBLIC_BUCKET, Key=s3_key)
        return True
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("404", "403"):
            return False
        raise

def process_csv(s3_key, overwrite=False):
    """
    Copy CSVs S3_TEXTRACT_BUCKET/processed/prefix to S3_PUBLIC_BUCKET/prefix.
    Skip if already exists, unless overwrite is enabled.
    If copy is successful, delete the original file from S3_TEXTRACT_BUCKET.
    """
    prefix = s3_key.split("/")[1]
    dest_key = f"{prefix}/{os.path.basename(s3_key)}"

    if not overwrite and csv_exists(dest_key):
        print(f"✅ {dest_key} already exists in public bucket, skipping.")
        return
    try:
        print(f"📤 Copying {s3_key} to s3://{S3_PUBLIC_BUCKET}/{dest_key} ...")
        copy_source = {
            "Bucket": S3_TEXTRACT_BUCKET,
            "Key": s3_key
        }
        s3.copy(copy_source, S3_PUBLIC_BUCKET, dest_key)
        print(f"✅ Successfully copied {s3_key}")
    
        s3.delete_object(Bucket=S3_TEXTRACT_BUCKET, Key=s3_key)
        print(f"🗑️ Deleted {s3_key} from textract bucket")
    
    except ClientError as e:
        print(f"❌ Failed to copy {s3_key}: {e.response['Error']['Message']}")
    except Exception as e:
        print(f"❌ Unexpected error while copying {s3_key}: {e}")

def run(prefix, year_range, overwrite=False):
    csvs = list_csvs(f"processed/{prefix}/", year_range)
    print(f"\nTotal CSVs found for `{prefix}` from {year_range[0]}-{year_range[1]}: {len(csvs)}")
    for csv in csvs:
        print(csv)
    print("\nChecking CSVs status:")
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS) as ex:
        ex.map(lambda key: process_csv(key, overwrite=overwrite), csvs)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch extract layout.csv using AWS Textract LAYOUT")
    parser.add_argument("--prefix", required=True, choices=PREFIX_OPTIONS, help="Prefix to search under")
    parser.add_argument("--filename", help="Single CSV filename (e.g. 2001-03-20.csv) to process under the prefix")
    parser.add_argument("--start-year", type=int, help="Start year for filtering")
    parser.add_argument("--end-year", type=int, help="End year for filtering")
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting existing files")

    args = parser.parse_args()

    if args.filename:
        s3_key = f"processed/{args.prefix}/{args.filename}"
        print(f"Running single file:")
        print(f"- S3 Key: {s3_key}")
        print(f"\nChecking CSVs status:")
        process_csv(s3_key, overwrite=args.overwrite)

    else:
        if args.start_year is None or args.end_year is None:
            parser.error("--start-year and --end-year are required when not using --filename")

        print(f"Running batch:")
        print(f"- Prefix:     {args.prefix}")
        print(f"- Year range: {args.start_year}-{args.end_year}")
        run(args.prefix, (args.start_year, args.end_year), overwrite=args.overwrite)

    print("\nDone.")

# python transfer_textracted.py --prefix dewannegara --start-year 1991 --end-year 1991
# python transfer_textracted.py --prefix dewannegara --start-year 1991 --end-year 1991 --overwrite
# python transfer_textracted.py --prefix dewannegara --filename dn_1959-09-12.csv
# python transfer_textracted.py --prefix dewannegara --filename dn_1959-09-12.csv --overwrite
