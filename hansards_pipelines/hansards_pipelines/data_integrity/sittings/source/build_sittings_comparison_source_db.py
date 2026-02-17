from datetime import datetime, timezone
import boto3
import json
from typing import Dict, List

from hansards_pipelines.settings import AWS_REGION, S3_DATAPROC_BUCKET

# -------------------------------------------------
# SHARED NORMALIZATION
# -------------------------------------------------

def normalize_meeting_value(meeting: str) -> str:
    """
    Apply the SAME normalization logic used in integrity engine.
    """
    if meeting in {"11"}:
        return "0"
    return meeting


# -------------------------------------------------
# MEETING-LEVEL COUNT + STRUCTURAL COMPARISON
# -------------------------------------------------

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

                    src_exists = meeting_id in src_meetings
                    db_exists = meeting_id in db_meetings

                    src_count = src_meetings.get(meeting_id, {}).get("sitting_count", 0)
                    db_count = db_meetings.get(meeting_id, {}).get("sitting_count", 0)

                    # -------------------------------------------------
                    # CLASSIFY STATUS (STRUCTURAL + QUANTITATIVE)
                    # -------------------------------------------------

                    if not db_exists and src_exists:
                        status = "MEETING_MISSING_IN_DB"

                    elif not src_exists and db_exists:
                        status = "MEETING_EXTRA_IN_DB"

                    elif db_count != src_count:
                        status = "SITTING_COUNT_MISMATCH"

                    else:
                        status = "MATCH"

                    delta = db_count - src_count

                    rows.append({
                        "house": house,
                        "term": int(term),
                        "session": int(session_id),
                        "meeting": int(meeting_id),
                        "source_sitting_count": src_count,
                        "db_sitting_count": db_count,
                        "delta": delta,
                        "status": status,
                    })

    # -------------------------------------------------
    # SUMMARY
    # -------------------------------------------------

    total_rows = len(rows)

    status_counts = {}
    for r in rows:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),

        "summary": {
            "total_rows": total_rows,
            "total_match": status_counts.get("MATCH", 0),
            "total_meeting_missing_in_db": status_counts.get("MEETING_MISSING_IN_DB", 0),
            "total_meeting_extra_in_db": status_counts.get("MEETING_EXTRA_IN_DB", 0),
            "total_sitting_count_mismatch": status_counts.get("SITTING_COUNT_MISMATCH", 0),
            "houses_checked": sorted(set(r["house"] for r in rows)),
        },

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



# -------------------------------------------------
# CONSOLIDATE LATEST INTEGRITY REPORTS
# -------------------------------------------------

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
                "cycle_issue_count": summary.get("cycle_issue_count", 0),
                "sitting_count_mismatches": summary.get("sitting_count_mismatches", 0),
                "total_issues": summary.get("total_issues", 0),
                "run_id": meta.get("run_id"),
                "generated_at": meta.get("generated_at"),
            })

    total_fail = sum(1 for r in rows if r["status"] == "FAIL")
    total_pass = sum(1 for r in rows if r["status"] == "PASS")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),

        "summary": {
            "total_terms": len(rows),
            "total_pass": total_pass,
            "total_fail": total_fail,
        },

        "rows": sorted(
            rows,
            key=lambda x: (x["house"], x["term"]),
        ),
    }
