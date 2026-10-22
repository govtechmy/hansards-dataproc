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

MANIFEST_KEY = "arkib/manifest_test.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def load_manifest(s3) -> List[Tuple[str, str]]:
    """
    Load manifest JSON from dataproc bucket.

    Returns:
        List of (house_folder, filename)
    """
    try:
        obj = s3.get_object(Bucket=S3_DATAPROC_BUCKET, Key=MANIFEST_KEY)
        payload = json.loads(obj["Body"].read())
    except ClientError as exc:
        logging.error("Failed to read manifest s3://%s/%s", S3_DATAPROC_BUCKET, MANIFEST_KEY)
        raise exc

    items = [
        (item["house_folder"], item["filename"])
        for item in payload.get("items", [])
    ]

    return items


def move_arkib_pdfs_to_public(
    s3,
    items: List[Tuple[str, str]],
):
    """
    Copy arkib PDFs from the dataproc bucket into the public bucket,
    renaming them using get_sitting_object rules.
    """
    if not S3_DATAPROC_BUCKET or not S3_PUBLIC_BUCKET:
        raise ValueError("S3 buckets are not configured")

    results = []

    for house_folder, filename in items:
        source_key = f"arkib/{house_folder}/{filename}"

        try:
            sitting = get_sitting_object(filename)
        except ValueError as exc:
            logging.warning(
                "Skipped (invalid filename format): %s (%s)",
                filename,
                exc,
            )
            continue
        dest_key = f"arkib/{sitting['house_folder']}/{sitting['renamed_filename']}.pdf"

        if not s3_object_exists(s3, S3_DATAPROC_BUCKET, source_key):
            logging.warning(
                "Skipped (source missing): s3://%s/%s",
                S3_DATAPROC_BUCKET,
                source_key,
            )
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
            logging.error(
                "Failed to copy s3://%s/%s -> s3://%s/%s",
                S3_DATAPROC_BUCKET,
                source_key,
                S3_PUBLIC_BUCKET,
                dest_key,
            )
            raise exc

    return results


def main(category: str | None = "__from_cli__"):
    """
    Move arkib PDFs from dataproc to public bucket using manifest.
    """
    if category == "__from_cli__":
        parser = argparse.ArgumentParser(
            description="Move and rename arkib PDFs from dataproc to public bucket (manifest-driven)"
        )
        parser.add_argument(
            "--category",
            type=str,
            help="House category to process (e.g., dewannegara, dewanrakyat)",
        )
        args = parser.parse_args()
        category = args.category

    s3 = boto3.client("s3")
    s3.head_bucket(Bucket=S3_DATAPROC_BUCKET)
    s3.head_bucket(Bucket=S3_PUBLIC_BUCKET)

    logging.info("Loading manifest s3://%s/%s", S3_DATAPROC_BUCKET, MANIFEST_KEY)
    items = load_manifest(s3)

    if category:
        items = [
            (house, fname)
            for house, fname in items
            if house == category
        ]
        logging.info("Filtered manifest to category=%s (%d items)", category, len(items))
    else:
        logging.info("Processing all manifest items (%d)", len(items))

    move_arkib_pdfs_to_public(s3, items)

    logging.info("Done")


if __name__ == "__main__":
    main()
