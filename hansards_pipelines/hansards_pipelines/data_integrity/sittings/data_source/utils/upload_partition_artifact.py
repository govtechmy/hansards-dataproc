from hansards_pipelines.settings import AWS_REGION, S3_DATAPROC_BUCKET
import boto3
import json
from datetime import datetime, timezone


def upload_partition_artifact(
    layer: str,
    house: str,
    term: int,
    payload: dict,
    run_id: str,
):
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    
    key = (
        f"checks/sittings/{layer}/"
        f"{house}/"
        f"{term}/"
        f"runs/run_{timestamp}_{run_id}.json"
    )

    session = boto3.Session(region_name=AWS_REGION)
    s3 = session.client("s3")

    s3.put_object(
        Bucket=S3_DATAPROC_BUCKET,
        Key=key,
        Body=json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    return key
