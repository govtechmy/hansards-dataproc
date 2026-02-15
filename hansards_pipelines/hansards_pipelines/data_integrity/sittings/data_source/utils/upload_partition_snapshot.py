from hansards_pipelines.settings import AWS_REGION, S3_DATAPROC_BUCKET
from datetime import datetime, timezone
import boto3
import json


def upload_partition_snapshot(
    layer: str,
    house: str,
    term: int,
    payload: dict,
    run_id: str,
):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    session = boto3.Session(region_name=AWS_REGION)
    s3 = session.client("s3")

    run_key = (
        f"checks/sittings/{layer}/"
        f"{house}/"
        f"{term}/"
        f"runs/run_{timestamp}_{run_id}.json"
    )

    s3.put_object(
        Bucket=S3_DATAPROC_BUCKET,
        Key=run_key,
        Body=json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    latest_key = (
        f"checks/sittings/{layer}/"
        f"{house}/"
        f"{term}/"
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
