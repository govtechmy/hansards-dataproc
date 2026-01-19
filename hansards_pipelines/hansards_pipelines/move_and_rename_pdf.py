"""Utilities for moving arkib PDFs from the dataproc bucket to the public bucket.

Copies files from ``s3://<S3_DATAPROC_BUCKET>/arkib/<house>/<original>.pdf``
to ``s3://<S3_PUBLIC_BUCKET>/arkib/<house>/<renamed>.pdf`` where
``<renamed>`` follows ``get_sitting_object`` naming (e.g. ``dn_2024-12-12``).
"""

from __future__ import annotations

import logging
from typing import List, Tuple

from botocore.exceptions import ClientError

from hansards_pipelines.settings import S3_DATAPROC_BUCKET, S3_PUBLIC_BUCKET
from hansards_pipelines.utils.s3_utils import s3_object_exists
from hansards_pipelines.utils.text_utils import get_sitting_object


def move_arkib_pdfs_to_public(
    s3,
    items: List[Tuple[str, str]],
):
    if not S3_DATAPROC_BUCKET or not S3_PUBLIC_BUCKET:
        raise ValueError("S3 buckets not configured")

    results = []

    for house_folder, filename in items:
        source_key = f"arkib/{house_folder}/{filename}"

        sitting = get_sitting_object(filename.replace(".pdf", ""))
        dest_key = f"arkib/{sitting['house_folder']}/{sitting['renamed_filename']}.pdf"

        logging.info("Copy %s -> %s", source_key, dest_key)

        if not s3_object_exists(s3, S3_DATAPROC_BUCKET, source_key):
            logging.warning("Source missing: %s", source_key)
            continue

        try:
            s3.copy_object(
                Bucket=S3_PUBLIC_BUCKET,
                Key=dest_key,
                CopySource={"Bucket": S3_DATAPROC_BUCKET, "Key": source_key},
                ContentType="application/pdf",
            )

            results.append(
                {
                    "source": source_key,
                    "destination": dest_key,
                }
            )
        except ClientError as exc:
            logging.error("Failed copy %s -> %s", source_key, dest_key)
            raise exc

    return results
