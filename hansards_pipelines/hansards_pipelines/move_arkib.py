import json
import logging
import boto3

from hansards_pipelines.settings import S3_DATAPROC_BUCKET, S3_PUBLIC_BUCKET
from hansards_pipelines.hansards_pipelines.move_and_rename_pdf import move_arkib_pdfs_to_public

MANIFEST_KEY = "arkib/manifest.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def main():
    s3 = boto3.client("s3")
    s3.head_bucket(Bucket=S3_DATAPROC_BUCKET)
    s3.head_bucket(Bucket=S3_PUBLIC_BUCKET)

    obj = s3.get_object(Bucket=S3_DATAPROC_BUCKET, Key=MANIFEST_KEY)
    manifest = json.loads(obj["Body"].read())

    items = [
        (item["house_folder"], item["filename"])
        for item in manifest["items"]
    ]

    logging.info("Moving %d PDFs", len(items))
    move_arkib_pdfs_to_public(s3, items)
    logging.info("Done")


if __name__ == "__main__":
    main()
