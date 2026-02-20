"""
This script compares the sitting counts from the source (portal.parlimen.gov.my) against the counts in the database for a given scope (category, term, session). 
- It generates a report of any discrepancies found and uploads the report to S3.

Uploads report to S3 at:
checks/sittings/integrity_check/runs/{run_id}/integrity.json

Usage:
    python validate_sittings_integrity.py [--category CATEGORY] [--term term] [--term-range START END] [--dry-run]
Example:
    python validate_sittings_integrity.py --category dewannegara --term 14
    python validate_sittings_integrity.py --term-range 13 14
    python validate_sittings_integrity.py --category dewanrakyat --term 14 --dry-run

"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
import re
from typing import Dict, Tuple
from collections import defaultdict

import boto3

from hansards_pipelines.settings import (
    AWS_REGION,
    S3_DATAPROC_BUCKET,
)

from hansards_pipelines.data_integrity.sittings.source.snapshot_portal_parlimen import (
    run_source_snapshot,
    build_snapshot as build_source_snapshot,
)

from hansards_pipelines.data_integrity.sittings.source.snapshot_db import (
    fetch_db_structure,
    build_snapshot as build_db_snapshot,
)

LOG_LEVEL = logging.INFO
MAX_FILENAMES_PER_ISSUE = 50


# -------------------------------------------------
# ACTION MAPPING
# -------------------------------------------------

def map_issue_to_action(issue_type: str, level: str) -> Dict:
    """
    Maps issue type to deterministic action.
    """

    if issue_type.endswith("_MISSING_IN_DB"):
        return {
            "name": f"INGEST_{level.upper()}",
            "details": (
                f"This {level} exists in the source (Portal Parlimen) but is missing in the database. "
                f"Add the missing {level} and all dependent sittings in the db."
            ),
        }

    if issue_type.endswith("_EXTRA_IN_DB"):
        return {
            "name": f"REVIEW_{level.upper()}",
            "details": (
                f"This {level} exists in the database but not in the source (Portal Parlimen). "
                f"Validate whether the {level} is valid. If valid, keep it. "
                f"If invalid, correct or remove it along with its dependent sittings."
            ),
        }

    if issue_type == "MEETING_SITTING_COUNT_MISMATCH":
        return {
            "name": "REVIEW_SITTING_IN_DB",
            "details": (
                "The meeting exists in both source and database, but the number of sittings differs. "
                "Investigate the missing or extra sittings and reconcile with source."
            ),
        }
    
    if issue_type == "MEETING_CYCLE_DATE_MISMATCH":
        return {
            "name": "REVIEW_CYCLE_DATES_IN_DB",
            "details": (
                "The meeting exists in both source and database, but the cycle dates (start_date/end_date) differ. "
                "Validate which date range is correct and update the database if necessary."
            ),
        }

    return {
        "name": "NO_ACTION",
        "details": "No automated action is defined for this issue type.",
    }


def normalize_filename(name: str) -> str | None:
    """
    Convert both source and DB filename formats into canonical YYYY-MM-DD.

    Handles:
    - KKDR-15032023.pdf
    - DN-23101978.pdf
    - DR-10121990.pdf
    - KKDR-15032023-1.pdf
    - KKDR-13102025.PindaanTimMDN.pdf
    - kkdr_2023-03-15
    """

    if not name:
        return None

    name = name.strip().lower()

    # -----------------------
    # DB FORMAT: kkdr_2023-03-15
    # -----------------------
    if "_" in name and re.search(r"\d{4}-\d{2}-\d{2}", name):
        match = re.search(r"(\d{4}-\d{2}-\d{2})", name)
        if match:
            return match.group(1)

    # -----------------------
    # SOURCE FORMAT: PREFIX-DDMMYYYY
    # -----------------------
    match = re.search(r"-(\d{1,2})(\d{1,2})(\d{4})", name) # -anything-DDMMYYYY
    if match:
        day, month, year = match.groups()
        try:
            dt = datetime(int(year), int(month), int(day))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None

    return None


def build_canonical_map(files: list[str]) -> dict[str, str]:
    mapping = {}
    for f in files:
        canon = normalize_filename(f)
        if canon:
            mapping[canon] = f.strip()
    return mapping

def build_file_diff(
    src_map: dict[str, str],
    db_map: dict[str, str],
) -> Dict:

    src_keys = set(src_map.keys())
    db_keys = set(db_map.keys())

    missing_keys = sorted(src_keys - db_keys)
    extra_keys = sorted(db_keys - src_keys)

    truncated = False

    if len(missing_keys) > MAX_FILENAMES_PER_ISSUE:
        missing_keys = missing_keys[:MAX_FILENAMES_PER_ISSUE]
        truncated = True

    if len(extra_keys) > MAX_FILENAMES_PER_ISSUE:
        extra_keys = extra_keys[:MAX_FILENAMES_PER_ISSUE]
        truncated = True

    return {
        "missing_file_count": len(src_keys - db_keys),
        "missing_filenames": [
            src_map[k] for k in missing_keys
        ],
        "extra_file_count": len(db_keys - src_keys),
        "extra_filenames": [
            db_map[k] for k in extra_keys
        ],
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
    structural_diff = {
        "missing_meetings": [],
        "extra_meetings": [],
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
                issue_type = "TERM_MISSING_IN_DB"

                issue = {
                    "type": issue_type,
                    "level": "term",
                    "category": house,
                    "term": int(term),
                    "action": map_issue_to_action(issue_type, "term")
                }

                issues.append(issue)
                issue_summary_by_level["term"] += 1
                issue_summary_by_type[issue_type] += 1
                issue_summary_by_term[term] += 1
                continue

            if term not in src_terms:
                structural_counts["extra_terms"] += 1
                issue_type = "TERM_EXTRA_IN_DB"

                issue = {
                    "type": issue_type,
                    "level": "term",
                    "category": house,
                    "term": int(term),
                    "action": map_issue_to_action(issue_type, "term")

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
                    issue_type = "SESSION_MISSING_IN_DB"

                    src_meetings = src_sessions[session].get("meeting", {})

                    total_sittings = 0
                    src_all_files = []

                    for meeting_payload in src_meetings.values():
                        total_sittings += meeting_payload.get("sitting_count", 0)
                        src_all_files.extend(meeting_payload.get("filenames", []))

                    issue = {
                        "type": issue_type,
                        "level": "session",
                        "category": house,
                        "term": int(term),
                        "session": int(session),
                        "source_sitting_count": total_sittings,
                        "file_diff": {
                            "missing_file_count": len(src_all_files),
                            "missing_filenames": src_all_files[:MAX_FILENAMES_PER_ISSUE],
                            "truncated": len(src_all_files) > MAX_FILENAMES_PER_ISSUE,
                        },
                        "action": map_issue_to_action(issue_type, "session")
                    }

                    issues.append(issue)

                    issue_summary_by_level["session"] += 1
                    issue_summary_by_type[issue_type] += 1
                    issue_summary_by_term[term] += 1
                    continue

                if session not in src_sessions:
                    structural_counts["extra_sessions"] += 1
                    issue_type = "SESSION_EXTRA_IN_DB"

                    db_meetings = db_sessions[session].get("meeting", {})

                    total_sittings = 0
                    db_all_files = []

                    for meeting_payload in db_meetings.values():
                        total_sittings += meeting_payload.get("sitting_count", 0)
                        db_all_files.extend(meeting_payload.get("filenames", []))

                    issue = {
                        "type": issue_type,
                        "level": "session",
                        "category": house,
                        "term": int(term),
                        "session": int(session),
                        "db_sitting_count": total_sittings,
                        "file_diff": {
                            "extra_file_count": len(db_all_files),
                            "extra_filenames": db_all_files[:MAX_FILENAMES_PER_ISSUE],
                            "truncated": len(db_all_files) > MAX_FILENAMES_PER_ISSUE,
                        },
                        "action": map_issue_to_action(issue_type, "session")
                    }

                    issues.append(issue)

                    issue_summary_by_level["session"] += 1
                    issue_summary_by_type[issue_type] += 1
                    issue_summary_by_term[term] += 1
                    continue

                # ---------------- MEETING LEVEL ----------------

                src_meetings = src_sessions[session].get("meeting", {})
                db_meetings = db_sessions[session].get("meeting", {})

                for meeting in sorted(set(src_meetings) | set(db_meetings)):

                    src_payload = src_meetings.get(meeting)
                    db_payload = db_meetings.get(meeting)

                    # -------------------------------------------------
                    # STRUCTURAL ISSUES (existence)
                    # -------------------------------------------------

                    if meeting not in db_meetings:
                        structural_counts["missing_meetings"] += 1

                        issue = {
                            "type": "MEETING_MISSING_IN_DB",
                            "level": "meeting",
                            "category": house,
                            "term": int(term),
                            "session": int(session),
                            "meeting": int(meeting),

                            "source": {
                                "sitting_count": src_payload.get("sitting_count", 0),
                                "start_date": src_payload.get("start_date"),
                                "end_date": src_payload.get("end_date"),
                            },

                            "db": None,

                            "action": map_issue_to_action("MEETING_MISSING_IN_DB", "meeting"),
                        }

                        issues.append(issue)
                        issue_summary_by_level["meeting"] += 1
                        issue_summary_by_type["MEETING_MISSING_IN_DB"] += 1
                        issue_summary_by_term[term] += 1
                        continue

                    if meeting not in src_meetings:
                        structural_counts["extra_meetings"] += 1

                        issue = {
                            "type": "MEETING_EXTRA_IN_DB",
                            "level": "meeting",
                            "category": house,
                            "term": int(term),
                            "session": int(session),
                            "meeting": int(meeting),

                            "source": None,

                            "db": {
                                "sitting_count": db_payload.get("sitting_count", 0),
                                "start_date": db_payload.get("start_date"),
                                "end_date": db_payload.get("end_date"),
                            },

                            "action": map_issue_to_action("MEETING_EXTRA_IN_DB", "meeting"),
                        }

                        issues.append(issue)
                        issue_summary_by_level["meeting"] += 1
                        issue_summary_by_type["MEETING_EXTRA_IN_DB"] += 1
                        issue_summary_by_term[term] += 1
                        continue

                    # -------------------------------------------------
                    # QUANTITATIVE ISSUES (can have multiple)
                    # -------------------------------------------------

                    meeting_issues = []

                    # Normalize files
                    src_map = build_canonical_map(src_payload.get("filenames", []))
                    db_map = build_canonical_map(db_payload.get("filenames", []))

                    src_count = len(src_map)
                    db_count = db_payload.get("sitting_count", 0)

                    # Cycle date mismatch
                    if (
                        src_payload.get("start_date") != db_payload.get("start_date")
                        or
                        src_payload.get("end_date") != db_payload.get("end_date")
                    ):
                        meeting_issues.append("MEETING_CYCLE_DATE_MISMATCH")

                    # Sitting count mismatch
                    if src_count != db_count:
                        meeting_issues.append("MEETING_SITTING_COUNT_MISMATCH")

                    if not meeting_issues:
                        continue

                    for issue_type in meeting_issues:

                        quantitative_issue_count += 1

                        issue = {
                            "type": issue_type,
                            "level": "meeting",
                            "category": house,
                            "term": int(term),
                            "session": int(session),
                            "meeting": int(meeting),

                            "source": {
                                "sitting_count": src_count,
                                "start_date": src_payload.get("start_date"),
                                "end_date": src_payload.get("end_date"),
                            },

                            "db": {
                                "sitting_count": db_count,
                                "start_date": db_payload.get("start_date"),
                                "end_date": db_payload.get("end_date"),
                            },

                            "action": map_issue_to_action(issue_type, "meeting"),
                        }

                        if src_map or db_map:
                            issue["file_diff"] = build_file_diff(src_map, db_map)

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

    # ensure deterministic ordering for cycle_diff
    for k in structural_diff:
        structural_diff[k] = sorted(
            structural_diff[k],
            key=lambda x: (x["term"], x["session"], x["meeting"])
        )

    return {
        "meta": scope,

        "status": status,

        "summary": {
            "sitting_delta": sitting_delta,
            "meeting_delta": meeting_delta,

            # hierarchy-level issues (term/session/meeting existence)
            "cycle_issue_count": structural_issue_count,

            # meeting-level sitting count mismatches
            "sitting_count_mismatches": quantitative_issue_count,

            "total_issues": total_issues,
        },

        # aggregated statistics
        "issue_summary": {
            "by_level": dict(issue_summary_by_level),
            "by_type": dict(issue_summary_by_type),
            "by_term": dict(issue_summary_by_term),
        },

        # structural hierarchy breakdown only
        "issue_breakdown": {
            "cycle": structural_counts
        },

        # explicit hierarchy diff (no filenames)
        "cycle_diff": structural_diff,

        # full detailed issues (includes file diff)
        "issues": issues,
    }