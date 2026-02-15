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
MAX_FILENAMES_PER_ISSUE = 50


# -------------------------------------------------
# ACTION MAPPING
# -------------------------------------------------

def map_issue_to_action(issue_type: str) -> Dict:
    """
    Maps issue type to deterministic action policy.
    """

    if issue_type == "MISSING_IN_DB":
        return {
            "name": "TRIGGER_INGEST",
            "safe_to_auto_execute": True,
        }

    if issue_type == "EXTRA_IN_DB":
        return {
            "name": "FLAG_FOR_REVIEW",
            "safe_to_auto_execute": False,
        }

    if issue_type == "COUNT_MISMATCH":
        return {
            "name": "REPROCESS_MEETING",
            "safe_to_auto_execute": True,
        }

    return {
        "name": "NO_ACTION",
        "safe_to_auto_execute": False,
    }

# -------------------------------------------------
# NORMALIZATION RULES
# -------------------------------------------------

def normalize_meeting_value(meeting: str) -> str:
    """
    Normalize meeting identifiers so source and DB align.
 
    Issues observed:
    - The Portal Parlimen (source) uses "11" to denote the mesyuarat khas, while the DB uses "0" for the same meeting.
    For info our db schema defines the following mapping for:
        0 - Mesyuarat Khas
        1 - Mesyuarat Pertama
        2 - Mesyuarat Kedua
        3 - Mesyuarat Ketiga
        -1 - Hidden (not displayed in the front end)

    So the normalization rule needs to account for this discrepancy.

    Rule:
    - Source meeting 11 == DB meeting 0
    """

    if meeting == "11":
        return "0"

    return meeting


def build_file_diff(
    source_files: set[str],
    db_files: set[str],
) -> Dict:
    """
    Build a diff of missing and extra files between source and DB, with truncation if the list exceeds MAX_FILENAMES_PER_ISSUE.
    """

    missing_files = sorted(source_files - db_files)
    extra_files = sorted(db_files - source_files)

    truncated = False

    if len(missing_files) > MAX_FILENAMES_PER_ISSUE:
        missing_files = missing_files[:MAX_FILENAMES_PER_ISSUE]
        truncated = True

    if len(extra_files) > MAX_FILENAMES_PER_ISSUE:
        extra_files = extra_files[:MAX_FILENAMES_PER_ISSUE]
        truncated = True

    return {
        "missing_file_count": len(source_files - db_files),
        "missing_filenames": missing_files,
        "extra_file_count": len(db_files - source_files),
        "extra_filenames": extra_files,
        "truncated": truncated,
    }


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

            # ---------------- TERM LEVEL ----------------

            if term not in db_terms:
                structural_counts["missing_terms"] += 1
                issue_type = "MISSING_IN_DB"

                issue = {
                    "type": issue_type,
                    "level": "term",
                    "category": house,
                    "term": int(term),
                    "action": map_issue_to_action(issue_type)
                }

                issues.append(issue)
                issue_summary_by_level["term"] += 1
                issue_summary_by_type[issue_type] += 1
                issue_summary_by_term[term] += 1
                continue

            if term not in src_terms:
                structural_counts["extra_terms"] += 1
                issue_type = "EXTRA_IN_DB"

                issue = {
                    "type": issue_type,
                    "level": "term",
                    "category": house,
                    "term": int(term),
                    "action": map_issue_to_action(issue_type)
                }

                issues.append(issue)
                issue_summary_by_level["term"] += 1
                issue_summary_by_type[issue_type] += 1
                issue_summary_by_term[term] += 1
                continue

            # ---------------- SESSION LEVEL ----------------

            src_sessions = src_terms[term].get("session", {})
            db_sessions = db_terms[term].get("session", {})

            for session in sorted(set(src_sessions) | set(db_sessions)):

                if session not in db_sessions:
                    structural_counts["missing_sessions"] += 1
                    issue_type = "MISSING_IN_DB"

                    issue = {
                        "type": issue_type,
                        "level": "session",
                        "category": house,
                        "term": int(term),
                        "session": int(session),
                        "action": map_issue_to_action(issue_type)
                    }

                    issues.append(issue)
                    issue_summary_by_level["session"] += 1
                    issue_summary_by_type[issue_type] += 1
                    issue_summary_by_term[term] += 1
                    continue

                if session not in src_sessions:
                    structural_counts["extra_sessions"] += 1
                    issue_type = "EXTRA_IN_DB"

                    issue = {
                        "type": issue_type,
                        "level": "session",
                        "category": house,
                        "term": int(term),
                        "session": int(session),
                        "action": map_issue_to_action(issue_type)
                    }

                    issues.append(issue)
                    issue_summary_by_level["session"] += 1
                    issue_summary_by_type[issue_type] += 1
                    issue_summary_by_term[term] += 1
                    continue

                # ---------------- MEETING LEVEL ----------------

                unormalized_src_meetings = src_sessions[session].get("meeting", {})
                unormalized_db_meetings = db_sessions[session].get("meeting", {})

                src_meetings = {
                    normalize_meeting_value(m): v
                    for m, v in unormalized_src_meetings.items()
                }

                db_meetings = {
                    normalize_meeting_value(m): v
                    for m, v in unormalized_db_meetings.items()
                }

                for meeting in sorted(set(src_meetings) | set(db_meetings)):

                    src_payload = src_meetings.get(meeting, {})
                    db_payload = db_meetings.get(meeting, {})

                    src_count = src_payload.get("sitting_count", 0)
                    db_count = db_payload.get("sitting_count", 0)

                    issue_type = None

                    if meeting not in db_meetings:
                        structural_counts["missing_meetings"] += 1
                        issue_type = "MISSING_IN_DB"

                    elif meeting not in src_meetings:
                        structural_counts["extra_meetings"] += 1
                        issue_type = "EXTRA_IN_DB"

                    elif src_count != db_count:
                        quantitative_issue_count += 1
                        issue_type = "COUNT_MISMATCH"

                    else:
                        continue

                    issue = {
                        "type": issue_type,
                        "level": "meeting",
                        "category": house,
                        "term": int(term),
                        "session": int(session),
                        "meeting": int(meeting),
                        "source_sitting_count": src_count,
                        "db_sitting_count": db_count,
                        "action": map_issue_to_action(issue_type),
                    }

                    # -------- FILE DIFF ENRICHMENT (CLEANLY SEPARATED) --------
                    src_files = set(src_payload.get("filenames", []))
                    db_files = set(db_payload.get("filenames", []))

                    if src_files or db_files:
                        issue["file_diff"] = build_file_diff(
                            src_files,
                            db_files,
                        )

                    issues.append(issue)

                    issue_summary_by_level["meeting"] += 1
                    issue_summary_by_type[issue_type] += 1
                    issue_summary_by_term[term] += 1


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
