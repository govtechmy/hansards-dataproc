import json
import csv
import io
import boto3
from hansards_pipelines.settings import AWS_REGION, S3_DATAPROC_BUCKET


def upload_global_artifact(layer: str, payload: dict):

    session = boto3.Session(region_name=AWS_REGION)
    s3 = session.client("s3")

    base_key = f"checks/{layer}/report"

    # Upload JSON
    s3.put_object(
        Bucket=S3_DATAPROC_BUCKET,
        Key=f"{base_key}.json",
        Body=json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    # Upload CSV (from rows)
    rows = payload.get("rows", [])

    if rows:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

        s3.put_object(
            Bucket=S3_DATAPROC_BUCKET,
            Key=f"{base_key}.csv",
            Body=output.getvalue().encode("utf-8"),
            ContentType="text/csv",
        )

    return f"{base_key}.json"
