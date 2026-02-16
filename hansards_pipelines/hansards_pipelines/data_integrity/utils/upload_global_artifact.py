import json
import boto3
from hansards_pipelines.settings import AWS_REGION, S3_DATAPROC_BUCKET

def upload_global_artifact(layer: str, payload: dict):

    session = boto3.Session(region_name=AWS_REGION)
    s3 = session.client("s3")

    key = f"checks/{layer}/report.json"

    s3.put_object(
        Bucket=S3_DATAPROC_BUCKET,
        Key=key,
        Body=json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    return key
