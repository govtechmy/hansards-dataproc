"""
This script traverses all PDF files in a specified S3 bucket folder.
- checks if they are marked as "DRAFT" based on certain phrases in the content.
- summarizes the findings including total files checked, total draft files, and date ranges.

Usage:
    python DEBUG_traverseS3.py <house>
"""

import sys
import boto3
import pdfplumber
from io import BytesIO
from datetime import datetime


# --- Check argument ---
if len(sys.argv) != 2:
    print("Usage: python script.py <house>")
    print("Example: python script.py dewanrakyat")
    sys.exit(1)

HOUSE_FOLDER = sys.argv[1]  # e.g. dewanrakyat, dewannegara, kamarkhas
S3_PUBLIC_BUCKET = "downloads.hansard.parlimen.gov.my"
s3_prefix = f"{HOUSE_FOLDER}/"

s3_client = boto3.client("s3")

# def list_pdf_keys(bucket, prefix):
#     response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
#     contents = response.get("Contents", [])
#     return [item["Key"] for item in contents if item["Key"].endswith(".pdf")]

def list_pdf_keys(bucket, prefix):
    keys = []
    continuation_token = None

    while True:
        if continuation_token:
            response = s3_client.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix,
                ContinuationToken=continuation_token
            )
        else:
            response = s3_client.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix
            )

        contents = response.get("Contents", [])
        keys.extend([item["Key"] for item in contents if item["Key"].endswith(".pdf")])

        # Check if there are more results
        if response.get("IsTruncated"):
            continuation_token = response["NextContinuationToken"]
        else:
            break

    return keys

def check_is_final(pdf_bytes):
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages[:2]:  # Only check first 2 pages
            words = [w["text"].lower() for w in page.extract_words()]
            joined = " ".join(words)
            if any(phrase in joined for phrase in DRAFT_PHRASES):
                return False
    return True


DRAFT_PHRASES = [
    "naskhah belum disemak",
    "naskhah belum semak",
    "nskhah belum disemak",
    "belum semak",
    "belum disemak"
]

def extract_date_from_filename(filename):
    try:
        basename = filename.split("/")[-1]  # e.g., kkdr_2017-11-21.pdf
        date_str = basename.split("_")[1].split(".")[0]  # "2017-11-21"
        return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception as e:
        print(f"Date extract failed for {filename}: {e}")
        return None


def extract_year_from_filename(filename):
    try:
        basename = filename.split("/")[-1]  # kkdr_2017-10-23.pdf
        date_str = basename.split("_")[1].split(".")[0]  # 2017-10-23
        year = int(date_str.split("-")[0])  # 2017
        return year
    except:
        return None

def main():
    pdf_keys = list(list_pdf_keys(S3_PUBLIC_BUCKET, s3_prefix))
    print(f"Found {len(pdf_keys)} PDFs in s3://{S3_PUBLIC_BUCKET}/{s3_prefix}")

    draft_keys = []
    all_years = []
    all_dates = []

    for key in pdf_keys:
        try:
            obj = s3_client.get_object(Bucket=S3_PUBLIC_BUCKET, Key=key)
            pdf_bytes = obj["Body"].read()

            # Always extract these for the full summary
            year = extract_year_from_filename(key)
            date = extract_date_from_filename(key)
            if year:
                all_years.append(year)
            if date:
                all_dates.append(date)

            # Only log and collect DRAFT files
            is_final = check_is_final(pdf_bytes)
            if not is_final:
                print(f"{key}: DRAFT ❌ | Year: {year if year else 'Unknown'}")
                draft_keys.append(key)

        except Exception as e:
            print(f"{key}: ERROR - {e}")

    print(f"\nTotal files checked: {len(pdf_keys)}")
    print(f"Total DRAFT files: {len(draft_keys)}")

    if all_years:
        print(f"Year range (all files): {min(all_years)}–{max(all_years)}")
    else:
        print("Year range: Unknown")

    if all_dates:
        print(f"Date range (all files): {min(all_dates).strftime('%d %b %Y')} - {max(all_dates).strftime('%d %b %Y')}")
    else:
        print("Date range: Unknown")

    return draft_keys

if __name__ == "__main__":
    main()



