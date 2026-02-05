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
    prefix: str | None = None,
    min_year: int,
    max_year: int | None,
    logger,
) -> dict:
    """
    Build arkib partition queue based on S3 + criteria.
    - Scans S3 bucket/prefix for PDF files.
    - Converts S3 keys to arkib partitions format. e.g. "arkib/dr_2000_07_31.pdf" -> "DR_31072000"
    - Filters partitions based on sitting date >= min_year (and <= max_year when provided).
    - Examples:
        - min_year = 2024 will include partitions from year 2000 and onwards (i.e. 2000, 2001, ..., 2024).
        - max_year = 2025 will include partitions up to year 2025.
        - both min_year = 2024 and max_year = 2025 will include partitions from year 2024 to 2025 inclusive.

    Returns a JSON-serialisable dict:
    {
        generated_at: str,
        criteria: { min_year: int, max_year: int | None },
        partitions: [str, ...]
    }
    """
    partitions: set[str] = set()

    prefix = prefix or ""

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

            if max_year is not None and date.year > max_year:
                continue

            partitions.add(partition)
    
    logger.info(
        "Arkib queue built: %s partitions found in S3 %s %s. Following criteria: min_year=%s, max_year=%s",
        len(partitions),
        bucket,
        prefix,
        min_year,
        max_year,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "criteria": {"min_year": min_year, "max_year": max_year},
        "partitions": sorted(partitions),
    }
