"""
This script compares the sitting counts from the source (portal.parlimen.gov.my) against the counts in the database for a given scope (category, term, session). 
- It generates a report of any discrepancies found and uploads the report to S3.

Uploads report to S3 at:
checks/sittings/integrity/runs/{run_id}/integrity.json

Usage:
    python verify_sittings_integrity.py [--category CATEGORY] [--term term] [--term-range START END] [--dry-run]
Example:
    python verify_sittings_integrity.py --category dewannegara --term 14
    python verify_sittings_integrity.py --term-range 13 14
    python verify_sittings_integrity.py --category dewanrakyat --term 14 --dry-run

"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Tuple
from collections import defaultdict

import boto3

from hansards_pipelines.settings import (
    AWS_REGION,
    S3_DATAPROC_BUCKET,
)

from snapshot_portal_parlimen import (
    run_source_snapshot,
    build_snapshot as build_source_snapshot,
)

from snapshot_db import (
    fetch_db_structure,
    build_snapshot as build_db_snapshot,
)

LOG_LEVEL = logging.INFO


# -------------------------------------------------
# DIFF ENGINE
# -------------------------------------------------

def build_integrity_report(source: Dict, db: Dict, scope: Dict) -> Dict:

    issues = []

    structural_counts = {
        "missing_terms": 0,
        "extra_terms": 0,
        "missing_sessions": 0,
        "extra_sessions": 0,
        "missing_meetings": 0,
        "extra_meetings": 0,
    }

    quantitative_issue_count = 0

    issue_summary_by_level = defaultdict(int)
    issue_summary_by_type = defaultdict(int)
    issue_summary_by_term = defaultdict(int)

    src_houses = source.get("data", {})
    db_houses = db.get("data", {})

    for house in sorted(set(src_houses) | set(db_houses)):

        src_house = src_houses.get(house, {})
        db_house = db_houses.get(house, {})

        src_terms = src_house.get("term", {})
        db_terms = db_house.get("term", {})

        for term in sorted(set(src_terms) | set(db_terms)):

            if term not in db_terms:
                structural_counts["missing_terms"] += 1
                issue_summary_by_level["term"] += 1
                issue_summary_by_type["MISSING_IN_DB"] += 1
                issue_summary_by_term[term] += 1

                issues.append({
                    "type": "MISSING_IN_DB",
                    "level": "term",
                    "category": house,
                    "term": int(term),
                })
                continue

            if term not in src_terms:
                structural_counts["extra_terms"] += 1
                issue_summary_by_level["term"] += 1
                issue_summary_by_type["EXTRA_IN_DB"] += 1
                issue_summary_by_term[term] += 1

                issues.append({
                    "type": "EXTRA_IN_DB",
                    "level": "term",
                    "category": house,
                    "term": int(term),
                })
                continue

            src_sessions = src_terms[term].get("session", {})
            db_sessions = db_terms[term].get("session", {})

            for session in sorted(set(src_sessions) | set(db_sessions)):

                if session not in db_sessions:
                    structural_counts["missing_sessions"] += 1
                    issue_summary_by_level["session"] += 1
                    issue_summary_by_type["MISSING_IN_DB"] += 1
                    issue_summary_by_term[term] += 1

                    issues.append({
                        "type": "MISSING_IN_DB",
                        "level": "session",
                        "category": house,
                        "term": int(term),
                        "session": int(session),
                    })
                    continue

                if session not in src_sessions:
                    structural_counts["extra_sessions"] += 1
                    issue_summary_by_level["session"] += 1
                    issue_summary_by_type["EXTRA_IN_DB"] += 1
                    issue_summary_by_term[term] += 1

                    issues.append({
                        "type": "EXTRA_IN_DB",
                        "level": "session",
                        "category": house,
                        "term": int(term),
                        "session": int(session),
                    })
                    continue

                src_meetings = src_sessions[session].get("meeting", {})
                db_meetings = db_sessions[session].get("meeting", {})

                for meeting in sorted(set(src_meetings) | set(db_meetings)):

                    src_count = src_meetings.get(meeting, {}).get("sitting_count", 0)
                    db_count = db_meetings.get(meeting, {}).get("sitting_count", 0)

                    if meeting not in db_meetings:
                        structural_counts["missing_meetings"] += 1
                        issue_summary_by_level["meeting"] += 1
                        issue_summary_by_type["MISSING_IN_DB"] += 1
                        issue_summary_by_term[term] += 1

                        issues.append({
                            "type": "MISSING_IN_DB",
                            "level": "meeting",
                            "category": house,
                            "term": int(term),
                            "session": int(session),
                            "meeting": int(meeting),
                            "source_sitting_count": src_count,
                            "db_sitting_count": 0,
                        })
                        continue

                    if meeting not in src_meetings:
                        structural_counts["extra_meetings"] += 1
                        issue_summary_by_level["meeting"] += 1
                        issue_summary_by_type["EXTRA_IN_DB"] += 1
                        issue_summary_by_term[term] += 1

                        issues.append({
                            "type": "EXTRA_IN_DB",
                            "level": "meeting",
                            "category": house,
                            "term": int(term),
                            "session": int(session),
                            "meeting": int(meeting),
                            "source_sitting_count": 0,
                            "db_sitting_count": db_count,
                        })
                        continue

                    if src_count != db_count:
                        quantitative_issue_count += 1
                        issue_summary_by_level["meeting"] += 1
                        issue_summary_by_type["COUNT_MISMATCH"] += 1
                        issue_summary_by_term[term] += 1

                        issues.append({
                            "type": "COUNT_MISMATCH",
                            "level": "meeting",
                            "category": house,
                            "term": int(term),
                            "session": int(session),
                            "meeting": int(meeting),
                            "source_sitting_count": src_count,
                            "db_sitting_count": db_count,
                        })

    # Deltas
    sitting_delta = (
        db["summary"]["total_sittings"]
        - source["summary"]["total_sittings"]
    )

    meeting_delta = (
        db["summary"]["total_meetings"]
        - source["summary"]["total_meetings"]
    )

    structural_issue_count = sum(structural_counts.values())
    total_issues = structural_issue_count + quantitative_issue_count

    status = "PASS" if total_issues == 0 else "FAIL"

    return {
        "meta": scope,
        "status": status,
        "summary": {
            "sitting_delta": sitting_delta,
            "meeting_delta": meeting_delta,
            "structural_issue_count": structural_issue_count,
            "quantitative_issue_count": quantitative_issue_count,
            "total_issues": total_issues
        },
        "issue_summary_by_level": dict(issue_summary_by_level),
        "issue_summary_by_type": dict(issue_summary_by_type),
        "issue_summary_by_term": dict(issue_summary_by_term),
        "breakdown": {
            "structural": structural_counts,
            "quantitative": {
                "count_mismatches": quantitative_issue_count
            }
        },
        "issues": issues
    }


# -------------------------------------------------
# S3 UPLOAD
# -------------------------------------------------

def upload_to_s3(run_id: str, payload: Dict):

    key = f"checks/sittings/integrity/runs/{run_id}/integrity.json"

    session = boto3.Session(region_name=AWS_REGION)
    s3 = session.client("s3")

    s3.put_object(
        Bucket=S3_DATAPROC_BUCKET,
        Key=key,
        Body=json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    logging.info("Uploaded integrity result to s3://%s/%s", S3_DATAPROC_BUCKET, key)


# -------------------------------------------------
# MAIN
# -------------------------------------------------

def main():

    parser = argparse.ArgumentParser(description="Run Hansard integrity check")
    parser.add_argument("--category", choices=["dewanrakyat", "dewannegara", "kamarkhas"])
    parser.add_argument("--term", type=int)
    parser.add_argument("--term-range", nargs=2, type=int)
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(level=LOG_LEVEL)

    term_range: Tuple[int, int] | None = (
        tuple(args.term_range) if args.term_range else None
    )

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    scope = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "category": args.category,
            "term": args.term,
            "term_range": term_range,
        }
    }

    source_structure = run_source_snapshot(
        category=args.category,
        term=args.term,
        term_range=term_range,
    )

    source_snapshot = build_source_snapshot(
        source_structure,
        args.category,
        args.term,
        term_range,
    )

    db_structure = fetch_db_structure(
        category=args.category,
        term=args.term,
        term_range=term_range,
    )

    db_snapshot = build_db_snapshot(
        db_structure,
        args.category,
        args.term,
        term_range,
    )

    report = build_integrity_report(source_snapshot, db_snapshot, scope)

    if args.dry_run:
        print("\n===== INTEGRITY RESULT =====\n")
        print(json.dumps(report, indent=2))
        return

    upload_to_s3(run_id, report)
    logging.info("Integrity run complete. run_id=%s", run_id)


if __name__ == "__main__":
    main()
