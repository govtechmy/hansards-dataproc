from hansards_pipelines.settings import AWS_REGION, S3_DATAPROC_BUCKET
from datetime import datetime, timezone
import boto3
import json


def upload_partition_artifact_by_house_term(
    layer: str,
    house: str,
    term: int,
    payload: dict,
    run_id: str,
):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    session = boto3.Session(region_name=AWS_REGION)
    s3 = session.client("s3")

    prefix=f"checks/sittings/{layer}/{house}/{term}"

    run_key = f"{prefix}/runs/run_{timestamp}_{run_id}.json"

    s3.put_object(
        Bucket=S3_DATAPROC_BUCKET,
        Key=run_key,
        Body=json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    latest_key = f"{prefix}/latest_run.json"

    latest_payload = payload

    s3.put_object(
        Bucket=S3_DATAPROC_BUCKET,
        Key=latest_key,
        Body=json.dumps(latest_payload, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    return run_key
