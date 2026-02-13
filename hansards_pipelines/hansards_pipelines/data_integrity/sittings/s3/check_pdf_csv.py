"""
This script verifies that for each sitting recorded in the `api_sitting` table of the Hansard database,
both the PDF and CSV files exist in the designated S3 public bucket.
It generates a report summarizing any sittings with missing files and uploads the report to a specified S3 bucket.

Reason: To ensure data integrity by confirming that all sittings have their associated PDF and CSV files available in S3.

Usage:
    python validate_sittings_pdf_csv_in_S3.py [--houses dewanrakyat dewannegara kamarkhas] [--dry-run]
Options:
    --houses: Specify which houses to check. Default checks all three houses.
    --dry-run: If set, the report will not be uploaded to S3; it will only be printed to the console.

Example:
    python validate_sittings_pdf_csv_in_S3.py --houses dewanrakyat kamarkhas

"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from typing import List, Sequence, Tuple, Dict, Set

import boto3
import psycopg2

from hansards_pipelines.settings import (
    AWS_REGION,
    HANSARD_DB_URL,
    S3_DATAPROC_BUCKET,
    S3_PUBLIC_BUCKET,
)

DEFAULT_HOUSES: Tuple[str, ...] = ("dewanrakyat", "dewannegara", "kamarkhas")

DATAPROC_PREFIX: str = "checks/sittings/pdf_csv"

def get_db_connection():
    if not HANSARD_DB_URL:
        raise RuntimeError("HANSARD_DB_URL is not set")
    return psycopg2.connect(HANSARD_DB_URL)


def fetch_db_filenames(conn, houses: Sequence[str]) -> List[Tuple[int, str]]:
    prefix_map = {
        "dewanrakyat": "dr_%",
        "dewannegara": "dn_%",
        "kamarkhas": "kkdr_%",
    }

    like_patterns = [prefix_map[h] for h in houses if h in prefix_map]

    if not like_patterns:
        return []

    where_clause = " OR ".join(["filename LIKE %s"] * len(like_patterns))

    query = f"""
        SELECT sitting_id, filename
        FROM api_sitting
        WHERE filename IS NOT NULL
        AND ({where_clause})
        ORDER BY sitting_id
    """

    with conn.cursor() as cur:
        cur.execute(query, like_patterns)
        rows = cur.fetchall()

    return [(int(row[0]), str(row[1]).strip()) for row in rows]


def list_s3_files_grouped(
    s3_client,
    bucket: str,
    prefixes: Sequence[str],
) -> Dict[str, Set[str]]:

    files: Dict[str, Set[str]] = {}
    paginator = s3_client.get_paginator("list_objects_v2")

    for prefix in prefixes:
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                base = os.path.basename(key)

                if not base:
                    continue

                name, ext = os.path.splitext(base)
                ext = ext.lower().replace(".", "")

                if ext not in ("pdf", "csv"):
                    continue

                files.setdefault(name, set()).add(ext)

    return files


def derive_partition_from_filename(filename: str) -> str:
    """
    Convert: dn_2023-11-30 to DN-30112023
    """

    try:
        house_prefix, date_part = filename.split("_")
        dt = datetime.strptime(date_part, "%Y-%m-%d")

        house = house_prefix.upper()
        formatted_date = dt.strftime("%d%m%Y")

        return f"{house}-{formatted_date}"

    except Exception:
        return "UNKNOWN"


def analyze_sittings(
    db_rows: Sequence[Tuple[int, str]],
    s3_files: Dict[str, Set[str]],
):

    missing_pdf = []
    missing_csv = []
    missing_both = []

    for sitting_id, filename in db_rows:
        extensions = s3_files.get(filename, set())

        has_pdf = "pdf" in extensions
        has_csv = "csv" in extensions

        row = {
            "sitting_id": sitting_id,
            "filename": filename,
            "partition": derive_partition_from_filename(filename),
        }

        if not has_pdf and not has_csv:
            missing_both.append(row)
        elif not has_pdf:
            missing_pdf.append(row)
        elif not has_csv:
            missing_csv.append(row)

    summary = {
        "total_checked": len(db_rows),
        "missing_pdf_only": len(missing_pdf),
        "missing_csv_only": len(missing_csv),
        "missing_both": len(missing_both),
        "total_problematic": len(missing_pdf)
        + len(missing_csv)
        + len(missing_both),
    }

    grouped = {
        "pdf_only_missing": missing_pdf,
        "csv_only_missing": missing_csv,
        "both_missing": missing_both,
    }

    return summary, grouped


# Report

def upload_report(s3_client, bucket: str, key: str, payload: dict):
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )


def build_report(summary, grouped, houses, output_key):
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "houses_scanned": list(houses),
        "summary": summary,
        "details": grouped,
        "output_key": output_key,
    }


# CLI

def parse_args():
    parser = argparse.ArgumentParser(description="Verify api_sitting filenames (PDF + CSV) exist in S3 public bucket.")
    parser.add_argument("--houses", nargs="+", default=list(DEFAULT_HOUSES), help=f"Available houses: {', '.join(DEFAULT_HOUSES)}",)
    parser.add_argument("--dry-run", action="store_true", help="Do not upload report; print only.",)

    return parser.parse_args()

def main():
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    args = parse_args()

    if not S3_PUBLIC_BUCKET:
        raise RuntimeError("S3_PUBLIC_BUCKET is not set")
    if not S3_DATAPROC_BUCKET:
        raise RuntimeError("S3_DATAPROC_BUCKET is not set")

    invalid = set(args.houses) - set(DEFAULT_HOUSES)
    if invalid:
        raise ValueError(f"Invalid houses specified: {invalid}")

    session = boto3.Session(region_name=AWS_REGION)
    s3_client = session.client("s3")

    logging.info("Fetching filenames from database ...")

    with get_db_connection() as conn:
        db_rows = fetch_db_filenames(conn, args.houses)

    logging.info("Listing S3 objects ...")

    s3_files = list_s3_files_grouped(
        s3_client,
        S3_PUBLIC_BUCKET,
        args.houses,
    )

    summary, grouped = analyze_sittings(db_rows, s3_files)

    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")

    year = now.strftime("%Y")
    month = now.strftime("%m")
    day = now.strftime("%d")

    output_key = (f"{DATAPROC_PREFIX}/runs/{year}{month}{day}/run_{timestamp}.json")

    report = build_report(
        summary,
        grouped,
        args.houses,
        output_key,
    )

    logging.info("Total problematic sittings: %s", summary["total_problematic"])

    if args.dry_run:
        logging.info("Dry-run enabled. Not uploading.")
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        logging.info("Uploading report to s3://%s/%s", S3_DATAPROC_BUCKET, output_key)
        upload_report(s3_client, S3_DATAPROC_BUCKET, output_key, report)
        logging.info("Done.")

if __name__ == "__main__":
    main()
