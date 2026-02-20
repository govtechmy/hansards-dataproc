from datetime import datetime, timezone
import boto3
import json
from typing import List, Dict

from hansards_pipelines.settings import AWS_REGION, S3_DATAPROC_BUCKET


def consolidate_all_latest_s3_pdf_csv_into_one(houses: List[str]) -> Dict:

    session = boto3.Session(region_name=AWS_REGION)
    s3 = session.client("s3")

    rows = []

    for house in houses:

        latest_key = f"checks/s3/{house}/latest_run.json"

        try:
            obj = s3.get_object(
                Bucket=S3_DATAPROC_BUCKET,
                Key=latest_key,
            )
            latest = json.loads(obj["Body"].read())
        except Exception:
            continue

        summary = latest.get("summary", {})

        total_problematic = summary.get("total_problematic", 0)

        rows.append({
            "house": house,
            "total_checked": summary.get("total_checked", 0),
            "missing_pdf_only": summary.get("missing_pdf_only", 0),
            "missing_csv_only": summary.get("missing_csv_only", 0),
            "missing_both": summary.get("missing_both", 0),
            "total_problematic": total_problematic,
            "status": "PASS" if total_problematic == 0 else "FAIL",
            "generated_at": latest.get("generated_at"),
        })

    total_checked_all = sum(r["total_checked"] for r in rows)
    total_problematic_all = sum(r["total_problematic"] for r in rows)

    total_pass = sum(1 for r in rows if r["status"] == "PASS")
    total_fail = sum(1 for r in rows if r["status"] == "FAIL")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),

        "summary": {
            "total_houses": len(rows),
            "total_checked": total_checked_all,
            "total_problematic": total_problematic_all,
            "total_pass": total_pass,
            "total_fail": total_fail,
        },

        "rows": sorted(
            rows,
            key=lambda x: x["house"],
        ),
    }
