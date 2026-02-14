"""
This standalone script lists all filenames in a specified S3 bucket (and optional prefix) and writes them to a CSV file.
Each row in the CSV contains the filename (with extension)

Reason: To create a reference list of files stored in S3 for auditing or processing purposes.
"""

import boto3
import csv
import os

from hansards_pipelines.hansards_pipelines.settings import S3_PUBLIC_BUCKET

def s3_filenames_to_csv(
    bucket_name: str,
    output_csv: str,
    prefix: str | None = None,
    aws_region: str | None = None,
    profile_name: str | None = None,
) -> None:
    session = boto3.Session(
        profile_name=profile_name,
        region_name=aws_region,
    )
    s3 = session.client("s3")

    paginator = s3.get_paginator("list_objects_v2")

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["new_author_id"]) # header

        for page in paginator.paginate(
            Bucket=bucket_name,
            Prefix=prefix or "",
        ):
            for obj in page.get("Contents", []):
                key = obj["Key"]

                # skip folder placeholders
                if key.endswith("/"):
                    continue

                basename = os.path.basename(key)
                filename_no_ext, _ = os.path.splitext(basename)

                writer.writerow([basename])
                # writer.writerow([filename_no_ext])


if __name__ == "__main__":
    BUCKET = S3_PUBLIC_BUCKET
    PREFIX = "img/mp-240/" # optional prefix to filter files
    OUTPUT_CSV = "mp_images_in_s3.csv"

    s3_filenames_to_csv(
        bucket_name=BUCKET,
        output_csv=OUTPUT_CSV,
        prefix=PREFIX,
        aws_region="x", # optional AWS region
        profile_name="x", # optional AWS profile name
    )

    print(f"CSV written to {OUTPUT_CSV}")
