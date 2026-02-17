from datetime import datetime, timezone
import boto3
import json
from typing import Dict, List

from hansards_pipelines.settings import AWS_REGION, S3_DATAPROC_BUCKET


def normalize_meeting_value(meeting: str) -> str:
    """
    Apply the SAME normalization logic used in integrity engine.
    """
    if meeting in {"11"}: # {"11", "-1"}:
        return "0"
    return meeting


def build_sittings_integrity_comparison_source_db(houses: List[str]) -> Dict:

    session = boto3.Session(region_name=AWS_REGION)
    s3 = session.client("s3")

    rows = []

    for house in houses:

        prefix = f"checks/sittings/integrity_check/{house}/"

        response = s3.list_objects_v2(
            Bucket=S3_DATAPROC_BUCKET,
            Prefix=prefix,
            Delimiter="/",
        )

        if "CommonPrefixes" not in response:
            continue

        for term_prefix in response["CommonPrefixes"]:
            term = term_prefix["Prefix"].split("/")[-2]

            try:
                source_key = f"checks/sittings/source/{house}/{term}/latest_run.json"
                db_key = f"checks/sittings/db/{house}/{term}/latest_run.json"

                source_obj = s3.get_object(Bucket=S3_DATAPROC_BUCKET, Key=source_key)
                db_obj = s3.get_object(Bucket=S3_DATAPROC_BUCKET, Key=db_key)

                source_snapshot = json.loads(source_obj["Body"].read())
                db_snapshot = json.loads(db_obj["Body"].read())

            except Exception:
                continue

            source_terms = source_snapshot.get("data", {}).get(house, {}).get("term", {})
            db_terms = db_snapshot.get("data", {}).get(house, {}).get("term", {})

            src_term_data = source_terms.get(term, {})
            db_term_data = db_terms.get(term, {})

            src_sessions = src_term_data.get("session", {})
            db_sessions = db_term_data.get("session", {})

            all_sessions = set(src_sessions) | set(db_sessions)

            for session_id in all_sessions:

                un_src_meetings = src_sessions.get(session_id, {}).get("meeting", {})
                un_db_meetings = db_sessions.get(session_id, {}).get("meeting", {})

                src_meetings = {
                    normalize_meeting_value(m): v
                    for m, v in un_src_meetings.items()
                }

                db_meetings = {
                    normalize_meeting_value(m): v
                    for m, v in un_db_meetings.items()
                }

                all_meetings = set(src_meetings) | set(db_meetings)

                for meeting_id in all_meetings:

                    src_count = src_meetings.get(meeting_id, {}).get("sitting_count", 0)
                    db_count = db_meetings.get(meeting_id, {}).get("sitting_count", 0)

                    delta = db_count - src_count

                    rows.append({
                        "house": house,
                        "term": int(term),
                        "session": int(session_id),
                        "meeting": int(meeting_id),
                        "source_sitting_count": src_count,
                        "db_sitting_count": db_count,
                        "delta": delta,
                        "status": "MATCH" if delta == 0 else "MISMATCH",
                    })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_rows": len(rows),
        "rows": sorted(
            rows,
            key=lambda x: (
                x["house"],
                x["term"],
                x["session"],
                x["meeting"],
            ),
        ),
    }


def consolidate_all_latest_json_into_one(houses: List[str]) -> Dict:

    session = boto3.Session(region_name=AWS_REGION)
    s3 = session.client("s3")

    rows = []

    for house in houses:

        prefix = f"checks/sittings/integrity_check/{house}/"

        response = s3.list_objects_v2(
            Bucket=S3_DATAPROC_BUCKET,
            Prefix=prefix,
            Delimiter="/",
        )

        if "CommonPrefixes" not in response:
            continue

        for term_prefix in response["CommonPrefixes"]:
            term = term_prefix["Prefix"].split("/")[-2]

            latest_key = f"checks/sittings/integrity_check/{house}/{term}/latest_run.json"

            try:
                obj = s3.get_object(
                    Bucket=S3_DATAPROC_BUCKET,
                    Key=latest_key,
                )
                latest = json.loads(obj["Body"].read())
            except Exception:
                continue

            meta = latest.get("meta", {})
            summary = latest.get("summary", {})

            rows.append({
                "house": house,
                "term": int(term),
                "status": latest.get("status"),
                "structural_issue_count": summary.get("structural_issue_count"),
                "quantitative_issue_count": summary.get("quantitative_issue_count"),
                "total_issues": summary.get("total_issues"),
                "run_id": meta.get("run_id"),
                "generated_at": meta.get("generated_at"),
            })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_rows": len(rows),
        "rows": sorted(
            rows,
            key=lambda x: (x["house"], x["term"]),
        ),
    }