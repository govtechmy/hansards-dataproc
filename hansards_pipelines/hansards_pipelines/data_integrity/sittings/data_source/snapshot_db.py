"""
Structured snapshot of parliamentary sittings from database.

Output is written to:
    checks/sittings/db/runs/YYYYMMDD/run_TIMESTAMP.json

Usage:
    python snapshot_db.py [--category CATEGORY] [--term term] [--term-range START END] [--dry-run]

Example:
    python snapshot_db.py --category dewannegara --term 14
    python snapshot_db.py --term-range 13 14 -- dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

import boto3
import psycopg2

from hansards_pipelines.settings import (
    AWS_REGION,
    S3_DATAPROC_BUCKET,
    HANSARD_DB_URL,
)

LOG_LEVEL = logging.INFO


# ----------------------------
# SQL Builder
# ----------------------------

def build_sql(category=None, term=None, term_range=None):

    filters = []

    house_map_reverse = {
        "dewanrakyat": 0,
        "dewannegara": 1,
        "kamarkhas": 2,
    }

    if category:
        filters.append(f"c.house = {house_map_reverse[category]}")

    if term:
        filters.append(f"c.term = {term}")

    if term_range:
        filters.append(f"c.term BETWEEN {term_range[0]} AND {term_range[1]}")

    where_clause = ""
    if filters:
        where_clause = "WHERE " + " AND ".join(filters)

    return f"""
    WITH base AS (
        SELECT
            c.house,
            c.term,
            c.session,
            c.meeting,
            COUNT(s.sitting_id) AS sitting_count
        FROM public.api_sitting s
        JOIN public.api_parliamentary_cycle c
            ON s.cycle_id = c.cycle_id
        {where_clause}
        GROUP BY c.house, c.term, c.session, c.meeting
    ),

    meeting_level AS (
        SELECT
            house,
            term,
            session,
            json_object_agg(
                meeting::text,
                json_build_object(
                    'sitting_count', sitting_count
                )
                ORDER BY meeting
            ) AS meeting_json,
            SUM(sitting_count) AS session_sitting_count
        FROM base
        GROUP BY house, term, session
    ),

    session_level AS (
        SELECT
            house,
            term,
            json_object_agg(
                session::text,
                json_build_object(
                    'sitting_count', session_sitting_count,
                    'meeting', meeting_json
                )
                ORDER BY session
            ) AS session_json,
            SUM(session_sitting_count) AS term_sitting_count
        FROM meeting_level
        GROUP BY house, term
    ),

    term_level AS (
        SELECT
            house,
            json_object_agg(
                term::text,
                json_build_object(
                    'sitting_count', term_sitting_count,
                    'session', session_json
                )
                ORDER BY term
            ) AS term_json
        FROM session_level
        GROUP BY house
    )

    SELECT
        json_object_agg(
            CASE house
                WHEN 0 THEN 'dewanrakyat'
                WHEN 1 THEN 'dewannegara'
                WHEN 2 THEN 'kamarkhas'
                ELSE house::text
            END,
            json_build_object(
                'term', term_json
            )
        )
    FROM term_level;
    """



# ----------------------------
# Summary
# ----------------------------

def compute_summary(structure: Dict) -> Dict:
    total_terms = 0
    total_sessions = 0
    total_meetings = 0
    total_sittings = 0

    for house in structure.values():
        for term in house.get("term", {}).values():
            total_terms += 1
            total_sittings += term.get("sitting_count", 0)

            for session in term.get("session", {}).values():
                total_sessions += 1

                for meeting in session.get("meeting", {}).values():
                    total_meetings += 1

    return {
        "total_terms": total_terms,
        "total_sessions": total_sessions,
        "total_meetings": total_meetings,
        "total_sittings": total_sittings,
    }


# ----------------------------
# Snapshot Builder
# ----------------------------

def build_snapshot(structure, category, term, term_range):
    return {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "artifact_type": "db_snapshot",
            "check_scope": "sittings",
            "category_filter": category,
            "term_filter": term,
            "term_range_filter": term_range,
        },
        "summary": compute_summary(structure),
        "data": structure,
    }


def upload_snapshot_to_s3(snapshot: Dict):
    now = datetime.now(timezone.utc)
    date_folder = now.strftime("%Y%m%d")
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")

    key = f"checks/sittings/db/runs/{date_folder}/run_{timestamp}.json"

    session = boto3.Session(region_name=AWS_REGION)
    s3_client = session.client("s3")

    s3_client.put_object(
        Bucket=S3_DATAPROC_BUCKET,
        Key=key,
        Body=json.dumps(snapshot, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    logging.info("DB snapshot uploaded to s3://%s/%s", S3_DATAPROC_BUCKET, key)
    return key


# ----------------------------
# Fetch Structure
# ----------------------------

def fetch_db_structure(category=None, term=None, term_range=None) -> Dict:

    sql = build_sql(category, term, term_range)

    conn = psycopg2.connect(HANSARD_DB_URL)
    cursor = conn.cursor()

    cursor.execute(sql)
    result = cursor.fetchone()

    cursor.close()
    conn.close()

    if not result or result[0] is None:
        return {}

    return result[0]


# ----------------------------
# Main
# ----------------------------

def main():
    parser = argparse.ArgumentParser(description="Snapshot Hansard DB")
    parser.add_argument("--category", choices=["dewanrakyat", "dewannegara", "kamarkhas"])
    parser.add_argument("--term", type=int)
    parser.add_argument("--term-range", nargs=2, type=int)
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(level=LOG_LEVEL)

    term_range = tuple(args.term_range) if args.term_range else None

    structure = fetch_db_structure(
        category=args.category,
        term=args.term,
        term_range=term_range,
    )

    snapshot = build_snapshot(
        structure,
        args.category,
        args.term,
        term_range,
    )

    if args.dry_run:
        print(json.dumps(snapshot, indent=2, ensure_ascii=False))
        return

    upload_snapshot_to_s3(snapshot)


if __name__ == "__main__":
    main()
