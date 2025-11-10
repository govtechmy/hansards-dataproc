import boto3
import os
import re
import csv
import argparse
import tempfile
import concurrent.futures

from botocore.exceptions import ClientError
from textractor import Textractor
from textractor.data.constants import TextractFeatures
import os
from dotenv import load_dotenv
from hansards_pipelines.settings import S3_PUBLIC_BUCKET, S3_TEXTRACT_BUCKET, AWS_REGION

PREFIX_OPTIONS = ["dewannegara", "dewanrakyat", "kamarkhas"]
MAX_CONCURRENT_JOBS = 5

# === AWS Setup ===
session   = boto3.Session(region_name=AWS_REGION)
s3        = session.client("s3")
extractor = Textractor(region_name=AWS_REGION)

def list_pdfs(prefix, year_range):
    """
    List all PDFs under S3_PUBLIC_BUCKET/prefix whose filenames match YYYY-MM-DD
    and whose year falls within year_range.
    """
    paginator = s3.get_paginator("list_objects_v2")
    pdfs = []
    for page in paginator.paginate(Bucket=S3_PUBLIC_BUCKET, Prefix=prefix):
        for o in page.get("Contents", []):
            key = o["Key"]
            if key.lower().endswith(".pdf"):
                m = re.search(r"(\d{4})-\d{2}-\d{2}", key)
                if m and year_range[0] <= int(m.group(1)) <= year_range[1]:
                    pdfs.append(key)
    return pdfs

def layout_exists(s3_key):
    """
    Return True if S3_TEXTRACT_BUCKET/s3_key exists.
    Treat 404 or 403 as "not found" so we retry extraction.
    """
    try:
        s3.head_object(Bucket=S3_TEXTRACT_BUCKET, Key=s3_key)
        return True
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("404", "403"):
            return False
        raise

def process_pdf(pdf_key):
    prefix     = pdf_key.split("/",1)[0]
    base_name  = os.path.splitext(os.path.basename(pdf_key))[0]
    output_key = f"{prefix}/{base_name}_layout.csv"

    if layout_exists(output_key):
        print(f"{output_key} - already exists, skipping.")
        return

    print(f"{pdf_key} - Processing ...")
    try:
        # kicks off the async job and returns a LazyDocument
        doc = extractor.start_document_analysis(
            file_source=f"s3://{S3_PUBLIC_BUCKET}/{pdf_key}",
            features=[TextractFeatures.LAYOUT],
            save_image=False
        )

        # iterate doc.pages, LazyDocument will fetch & parse the real Document
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as tmp:
            writer = csv.writer(tmp, quoting=csv.QUOTE_MINIMAL)
            writer.writerow([
                "Page number", "Layout", "Text", "Reading Order", "Confidence"
            ])

            for page in doc.pages:
                counts = {}
                for layout in page.layouts:
                    # block type is in .layout_type (e.g. "LAYOUT_TEXT")
                    label = layout.layout_type
                    counts[label] = counts.get(label, 0) + 1
                    seq = counts[label]

                    writer.writerow([
                        # correct page number property is page.page_num :contentReference[oaicite:2]{index=2}
                        page.page_num,
                        f"{label} {seq}",
                        layout.text,
                        layout.reading_order,
                        layout.confidence
                    ])

            tmp_path = tmp.name

        s3.upload_file(tmp_path, S3_TEXTRACT_BUCKET, output_key)
        print(f" ✅ Uploaded {output_key} to s3://{S3_TEXTRACT_BUCKET}/{output_key}")

    except Exception as e:
        print(f"  ❌ Failed {pdf_key}: {e}")
    finally:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)

def run(prefix, year_range):
    pdfs = list_pdfs(f"{prefix}/", year_range)
    print(f"\nTotal PDFs found for `{prefix}` from {year_range[0]}-{year_range[1]}: {len(pdfs)}")
    for pdf in pdfs:
        print(pdf)
    print("\nChecking PDFs status:")
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS) as ex:
        ex.map(process_pdf, pdfs)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch extract layout.csv using AWS Textract LAYOUT")
    parser.add_argument("--prefix", required=True, choices=PREFIX_OPTIONS, help="Prefix to search under")
    parser.add_argument("--filename", help="Single PDF filename (e.g. 2001-03-20.pdf) to process under the prefix")
    parser.add_argument("--start-year", type=int, help="Start year for filtering")
    parser.add_argument("--end-year", type=int, help="End year for filtering")

    args = parser.parse_args()

    if args.filename:
        s3_key = f"{args.prefix}/{args.filename}"
        print(f"Running single file:")
        print(f"- S3 Key: {s3_key}")
        print(f"\nChecking PDFs status:")
        process_pdf(s3_key)

    else:
        if args.start_year is None or args.end_year is None:
            parser.error("--start-year and --end-year are required when not using --filename")

        print(f"Running batch:")
        print(f"- Prefix:     {args.prefix}")
        print(f"- Year range: {args.start_year}-{args.end_year}")
        run(args.prefix, (args.start_year, args.end_year))

    print("\nDone.")

# python run_textract.py --prefix dewannegara --start-year 1991 --end-year 1991
# python run_textract.py --prefix dewannegara --filename dn_1959-09-12.pdf