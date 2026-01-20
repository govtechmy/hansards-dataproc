"""
Utilities and CLI for moving arkib PDFs from the dataproc bucket to the public bucket.

Copies files from:
  s3://<S3_DATAPROC_BUCKET>/arkib/<house>/<original>.pdf

to:
  s3://<S3_PUBLIC_BUCKET>/arkib/<house>/<renamed>.pdf

This script is intended to be run AFTER scrape_arkib.py completes.
"""

from __future__ import annotations

import json
import logging
from typing import List, Tuple

import boto3
from botocore.exceptions import ClientError

from hansards_pipelines.settings import S3_DATAPROC_BUCKET, S3_PUBLIC_BUCKET
from hansards_pipelines.utils.s3_utils import s3_object_exists
from hansards_pipelines.utils.text_utils import get_sitting_object

MANIFEST_KEY = "arkib/manifest.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

def move_arkib_pdfs_to_public(
    s3,
    items: List[Tuple[str, str]],
):
    """
    Copy arkib PDFs from the dataproc bucket into the public bucket,
    renaming them using get_sitting_object rules.

    Args:
        s3: Boto3 S3 client
        items: List of (house_folder, filename) tuples
    """
    if not S3_DATAPROC_BUCKET or not S3_PUBLIC_BUCKET:
        raise ValueError("S3 buckets are not configured")

    results = []

    for house_folder, filename in items:
        source_key = f"arkib/{house_folder}/{filename}"

        # Remove .pdf extension and any trailing text after the date (e.g., _Updated, _Revised)
        # Expected format: DR-12122024 or DN-12122024
        base_name = filename.replace(".pdf", "")
        # Keep only the house-date portion (e.g., DR-12122024 from DR-12122024_Updated)
        if "_" in base_name:
            base_name = base_name.split("_")[0]
        
        sitting = get_sitting_object(base_name)
        dest_key = f"arkib/{sitting['house_folder']}/{sitting['renamed_filename']}.pdf" # TODO: remove arkib/ prefix after testing

        if not s3_object_exists(s3, S3_DATAPROC_BUCKET, source_key):
            logging.warning("Skipped (source missing): s3://%s/%s", S3_DATAPROC_BUCKET, source_key)
            continue

        try:
            s3.copy_object(
                Bucket=S3_PUBLIC_BUCKET,
                Key=dest_key,
                CopySource={
                    "Bucket": S3_DATAPROC_BUCKET,
                    "Key": source_key,
                },
                ContentType="application/pdf",
            )

            logging.info("Copied %s -> %s", source_key, dest_key)


            results.append(
                {
                    "source": source_key,
                    "destination": dest_key,
                }
            )

        except ClientError as exc:
            logging.error("Failed to copy s3://%s/%s -> s3://%s/%s", S3_DATAPROC_BUCKET, source_key, S3_PUBLIC_BUCKET, dest_key)
            raise exc

    return results


def main():
    s3 = boto3.client("s3")
    s3.head_bucket(Bucket=S3_DATAPROC_BUCKET)
    s3.head_bucket(Bucket=S3_PUBLIC_BUCKET)
    logging.info("Listing all PDFs in s3://%s/arkib/", S3_DATAPROC_BUCKET)
    response = s3.list_objects_v2(Bucket=S3_DATAPROC_BUCKET, Prefix="arkib/")
    items = []
    for obj in response.get('Contents', []):
        key = obj['Key']
        # Expected format: arkib/<house_folder>/<filename>.pdf
        parts = key.split('/')
        if len(parts) == 3 and parts[0] == 'arkib' and key.endswith('.pdf'):
            house_folder = parts[1]
            filename = parts[2]
            items.append((house_folder, filename))

    logging.info("Moving %d PDFs", len(items))

    move_arkib_pdfs_to_public(s3, items)

    logging.info("Done")


if __name__ == "__main__":
    main()
