import json
import boto3
from hansards_pipelines.settings import AWS_REGION, S3_DATAPROC_BUCKET


def upload_report_entrypoint(payload: dict):

    session = boto3.Session(region_name=AWS_REGION)
    s3 = session.client("s3")

    key = "checks/report/latest.json"

    s3.put_object(
        Bucket=S3_DATAPROC_BUCKET,
        Key=key,
        Body=json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    return key
