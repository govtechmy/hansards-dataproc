"""
Structured snapshot of parliamentary Hansard sittings from source website.

Output is written to:
    data_integrity/sittings/source/runs/YYYYMMDD/run_TIMESTAMP.json

Usage:
    python snapshot_parlimen_portal.py [--category CATEGORY] [--term term] [--term-range START END]

Example:
    python snapshot_parlimen_portal.py --category dewannegara --term 14
    python snapshot_parlimen_portal.py --term-range 13 14

Usage:
    python snapshot_portal_parlimen.py --category dewannegara --term 14 --max-nodes 10
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Set
from urllib.parse import urljoin, urlparse

import boto3
import requests
from bs4 import BeautifulSoup

from hansards_pipelines.scrape_arkib import (
    make_session,
    fetch_html,
    extract_child_ids,
    seed_kamarkhas_start_nodes,
)

from hansards_pipelines.settings import (
    AWS_REGION,
    S3_DATAPROC_BUCKET,
)

sitting_BASE_URL = "https://www.parlimen.gov.my"
ROOT_ID = "0"
LOG_LEVEL = logging.INFO


CATEGORIES = {
    "dewannegara": {
        "base_url": "https://www.parlimen.gov.my/hansard-dewan-negara.html",
        "uweb": "dn",
    },
    "dewanrakyat": {
        "base_url": "https://www.parlimen.gov.my/hansard-dewan-rakyat.html",
        "uweb": "dr",
    },
    "kamarkhas": {
        "base_url": "https://www.parlimen.gov.my/hansard-dewan-khas.html",
        "uweb": "dr",
    },
}


# ----------------------------
# Extraction
# ----------------------------

def extract_sittings(html: str) -> List[Dict[str, str]]:
    sittings = []
    soup = BeautifulSoup(html, "html.parser")

    for a in soup.select("a[href$='.pdf'], a[href$='.PDF']"):
        url = urljoin(sitting_BASE_URL, a["href"])
        filename = urlparse(url).path.split("/")[-1]
        sittings.append({"filename": filename, "url": url})

    for u in soup.find_all("userdata"):
        m = re.search(
            r"loadResult\(['\"]([^'\"]+\.pdf)['\"],['\"]([^'\"]+)['\"]\)",
            u.text or "",
            flags=re.IGNORECASE,
        )
        if m:
            path, name = m.groups()
            sittings.append({
                "filename": name,
                "url": urljoin(sitting_BASE_URL, path),
            })

    return sittings


def parse_node_id(node_id: str):
    parts = node_id.split("_")
    result = {"term": None, "session": None, "meeting": None}

    if len(parts) >= 2:
        result["term"] = int(parts[1])
    if len(parts) >= 3:
        result["session"] = int(parts[2])
    if len(parts) >= 4:
        result["meeting"] = int(parts[3])

    return result


# ----------------------------
# Crawling
# ----------------------------

def crawl_structured(
    session: requests.Session,
    base_url: str,
    uweb: str,
    house_name: str,
    node_id: str,
    visited: Set[str],
    structure: Dict,
    seen_sittings: Set[str],
    max_nodes: int | None,
    node_counter: Dict[str, int],
):

    if max_nodes is not None and node_counter["count"] >= max_nodes:
        return

    if node_id in visited:
        return

    visited.add(node_id)
    node_counter["count"] += 1

    hierarchy = parse_node_id(node_id)

    logging.info(
        "Visiting %s | node %s | T%s S%s M%s",
        house_name,
        node_id,
        hierarchy["term"] or "-",
        hierarchy["session"] or "-",
        hierarchy["meeting"] or "-",
    )

    html = fetch_html(session, base_url, uweb, node_id)
    all_sittings = extract_sittings(html)

    sittings = []
    for sitting in all_sittings:
        key = f"{house_name}/{sitting['filename']}"
        if key not in seen_sittings:
            seen_sittings.add(key)
            sittings.append(sitting)

    if not sittings or hierarchy["term"] is None:
        # still continue recursion
        for child in sorted(
            extract_child_ids(html),
            key=lambda x: [int(p) for p in x.split("_") if p.isdigit()],
        ):
            crawl_structured(
                session,
                base_url,
                uweb,
                house_name,
                child,
                visited,
                structure,
                seen_sittings,
                max_nodes,
                node_counter,
            )
        return

    # Ensure house exists
    structure.setdefault(house_name, {})
    structure[house_name].setdefault("term", {})

    term_key = str(hierarchy["term"])
    structure[house_name]["term"].setdefault(
        term_key,
        {"sitting_count": 0, "session": {}},
    )

    # Add to term-level count
    structure[house_name]["term"][term_key]["sitting_count"] += len(sittings)

    # Session level
    if hierarchy["session"] is not None:

        session_key = str(hierarchy["session"])
        structure[house_name]["term"][term_key]["session"].setdefault(
            session_key,
            {"sitting_count": 0, "meeting": {}},
        )

        structure[house_name]["term"][term_key]["session"][session_key]["sitting_count"] += len(sittings)

        # Meeting level
        if hierarchy["meeting"] is not None:
            meeting_key = str(hierarchy["meeting"])
            structure[house_name]["term"][term_key]["session"][session_key]["meeting"].setdefault(
                meeting_key,
                {"sitting_count": 0},
            )

            structure[house_name]["term"][term_key]["session"][session_key]["meeting"][meeting_key]["sitting_count"] += len(sittings)

    # Continue recursion
    for child in sorted(
        extract_child_ids(html),
        key=lambda x: [int(p) for p in x.split("_") if p.isdigit()],
    ):
        crawl_structured(
            session,
            base_url,
            uweb,
            house_name,
            child,
            visited,
            structure,
            seen_sittings,
            max_nodes,
            node_counter,
        )


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
            "artifact_type": "portal_parlimen_snapshot",
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

    key = f"checks/sittings/source/runs/{date_folder}/run_{timestamp}.json"

    session = boto3.Session(region_name=AWS_REGION)
    s3_client = session.client("s3")

    s3_client.put_object(
        Bucket=S3_DATAPROC_BUCKET,
        Key=key,
        Body=json.dumps(snapshot, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    logging.info("Snapshot uploaded to s3://%s/%s", S3_DATAPROC_BUCKET, key)
    return key


# ----------------------------
# Main
# ----------------------------

def run_source_snapshot(category=None, term=None, term_range=None, max_nodes=None):

    session = make_session()
    structure: Dict = {}
    seen_sittings: Set[str] = set()
    node_counter = {"count": 0}

    categories = {category: CATEGORIES[category]} if category else CATEGORIES

    for name, cfg in categories.items():

        if term:
            start_nodes = [f"0_{term}"]
        elif term_range:
            start_nodes = [f"0_{p}" for p in range(term_range[0], term_range[1] + 1)]
        else:
            start_nodes = [ROOT_ID]

        for start_id in start_nodes:
            crawl_structured(
                session,
                cfg["base_url"],
                cfg["uweb"],
                name,
                start_id,
                visited=set(),
                structure=structure,
                seen_sittings=seen_sittings,
                max_nodes=max_nodes,
                node_counter=node_counter,
            )

    return structure


def main():
    parser = argparse.ArgumentParser(description="Snapshot Parlimen source website")
    parser.add_argument("--category", choices=CATEGORIES.keys())
    parser.add_argument("--term", type=int)
    parser.add_argument("--term-range", nargs=2, type=int)
    parser.add_argument("--max-nodes", type=int)
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(level=LOG_LEVEL)

    term_range = tuple(args.term_range) if args.term_range else None

    structure = run_source_snapshot(
        category=args.category,
        term=args.term,
        term_range=term_range,
        max_nodes=args.max_nodes,
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
