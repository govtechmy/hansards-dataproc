from datetime import datetime, timezone
from typing import List, Dict, Set

from hansards_pipelines.arkib.convert_key import convert_arkib_key_to_partition


def extract_date_from_partition(partition: str) -> datetime | None:
    # DR-31072000 -> 31-07-2000
    try:
        _, dmy = partition.split("-", 1)
        return datetime.strptime(dmy, "%d%m%Y")
    except Exception:
        return None


def build_arkib_partition_queue(
    *,
    s3_client,
    bucket: str,
    prefix: str,
    min_year: int,
    logger,
) -> dict:
    """
    Build arkib partition queue based on S3 + criteria.
    - Scans S3 bucket/prefix for PDF files.
    - Converts S3 keys to arkib partitions format. e.g. "arkib/dr_2000_07_31.pdf" -> "DR_31072000"
    - Filters partitions based on sitting date >= min_year.

    Returns a JSON-serialisable dict:
    {
        generated_at: str,
        criteria: { min_year: int },
        partitions: [str, ...]
    }
    """
    partitions: set[str] = set()

    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]

            if not key.lower().endswith(".pdf"):
                continue

            try:
                partition = convert_arkib_key_to_partition(key)
            except Exception as e:
                logger.warning(f"Skip invalid arkib key | key={key} | err={e}")
                continue

            date = extract_date_from_partition(partition)
            if not date:
                logger.warning("Skip arkib partition with invalid date | key=%s | partition=%s", key, partition)
                continue

            if date.year < min_year:
                continue

            partitions.add(partition)
    
    logger.info(f"Arkib queue built: {len(partitions)} partitions found in S3 {bucket} {prefix}. Following criteria: min_year={min_year}")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "criteria": {"min_year": min_year},
        "partitions": sorted(partitions),
    }
