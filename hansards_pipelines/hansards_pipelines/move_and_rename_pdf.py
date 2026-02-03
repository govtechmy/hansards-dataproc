"""
Utilities and CLI for moving arkib PDFs from the dataproc bucket to the public bucket.

Copies files from:
  s3://<S3_DATAPROC_BUCKET>/arkib/<house>/<original>.pdf

to:
  s3://<S3_PUBLIC_BUCKET>/arkib/<house>/<renamed>.pdf

This script is intended to be run AFTER scrape_arkib.py completes.
"""

from __future__ import annotations

import argparse
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
    logger=None,
):
    """
    Copy arkib PDFs from the dataproc bucket into the public bucket,
    renaming them using get_sitting_object rules.

    Args:
        s3: Boto3 S3 client
        items: List of (house_folder, filename) tuples
    """
    log = logger if logger else logging

    if not S3_DATAPROC_BUCKET or not S3_PUBLIC_BUCKET:
        raise ValueError("S3 buckets are not configured")

    moved = 0
    deleted = 0

    for house_folder, filename in items:
        source_key = f"arkib/{house_folder}/{filename}"

        sitting = get_sitting_object(filename, logger=log)
        if not sitting:
            continue
        dest_key = f"arkib/{sitting['house_folder']}/{sitting['renamed_filename']}.pdf"

        if not s3_object_exists(s3, S3_DATAPROC_BUCKET, source_key):
            log.warning("Skipped (source missing): s3://%s/%s", S3_DATAPROC_BUCKET, source_key)
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
            moved += 1

            # Delete from dataproc
            s3.delete_object(
                Bucket=S3_DATAPROC_BUCKET,
                Key=source_key,
            )
            deleted += 1

            log.info("Moved & cleanup old copy %s -> %s", source_key, dest_key)

        except ClientError:
            log.exception("Failed during move+cleanup for %s", source_key)
            raise

        except ClientError as exc:
            log.error("Failed to copy s3://%s/%s -> s3://%s/%s", S3_DATAPROC_BUCKET, source_key, S3_PUBLIC_BUCKET, dest_key)
            raise exc

    log.info("Completed arkib move from S3 DATAPROC arkib/ to S3 PUBLIC arkib/: moved=%d deleted=%d", moved, deleted)


def move_arkib_pdfs_to_public_main(
    *,
    category: str | None,
    logger,
):
    """Move arkib PDFs from dataproc to public bucket.
    
    Args:
        category: House category to process (e.g., dewannegara, dewanrakyat). 
                  If not provided, all categories will be processed.
                  When called from CLI, this will be parsed from arguments.
    """
    log = logger if logger else logging

    s3 = boto3.client("s3")

    prefix = f"arkib/{category}/" if category else "arkib/"
    log.info("Listing PDFs in s3://%s/%s", S3_DATAPROC_BUCKET, prefix)

    paginator = s3.get_paginator("list_objects_v2")
    page_iterator = paginator.paginate(
        Bucket=S3_DATAPROC_BUCKET,
        Prefix=prefix,
    )

    items = []
    for page in page_iterator:
        for obj in page.get("Contents", []):
            key = obj["Key"]
            parts = key.split("/")
            if len(parts) == 3 and key.endswith(".pdf"):
                items.append((parts[1], parts[2]))

    log.info("Moving %d PDFs", len(items))

    move_arkib_pdfs_to_public(s3, items, logger=log)

    log.info("Done")


def main():
    parser = argparse.ArgumentParser(description="Move and rename arkib PDFs from dataproc to public bucket")
    parser.add_argument("--category", type=str, help="House category (e.g. dewanrakyat, dewannegara). If not provided, all categories will be processed.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    move_arkib_pdfs_to_public_main(category=args.category, logger=logging)


if __name__ == "__main__":
    main()
