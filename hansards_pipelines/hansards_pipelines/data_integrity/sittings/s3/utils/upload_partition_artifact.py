import json
from datetime import datetime, timezone
import boto3
from hansards_pipelines.settings import AWS_REGION, S3_DATAPROC_BUCKET

def upload_partition_artifact_by_house(
    layer: str,
    house: str,
    payload: dict,
    run_id: str,
):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    session = boto3.Session(region_name=AWS_REGION)
    s3 = session.client("s3")

    run_key = (
        f"checks/{layer}/"
        f"{house}/"
        f"runs/run_{timestamp}_{run_id}.json"
    )

    s3.put_object(
        Bucket=S3_DATAPROC_BUCKET,
        Key=run_key,
        Body=json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    latest_key = (
        f"checks/{layer}/"
        f"{house}/"
        f"latest.json"
    )

    latest_payload = {
        "run_id": run_id,
        "generated_at": timestamp,
        "status": payload.get("status"),
        "summary": payload.get("summary"),
    }

    s3.put_object(
        Bucket=S3_DATAPROC_BUCKET,
        Key=latest_key,
        Body=json.dumps(latest_payload, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    return run_key
