"""
Structured snapshot of parliamentary Hansard sittings from source website.
Includes:
- Arkib structured crawl
- Active cycle injection

Output is written to:
    checks/sittings/source/runs/YYYYMMDD/run_TIMESTAMP.json

Usage:
    python snapshot_parlimen_portal.py [--category CATEGORY] [--term term] [--term-range START END] [--max-nodes N] [--dry-run]

Example:
    python snapshot_parlimen_portal.py --category dewannegara --term 14
    python snapshot_parlimen_portal.py --term-range 13 14
    python snapshot_parlimen_portal.py --category dewanrakyat --term 14 --dry-run --max-nodes 10

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

from hansards_pipelines.scrape_parliamentary_cycle import (
    scrape_active_cycles, 
    scrape_arkib_cycles,
    HOUSE_MAP,
)

from hansards_pipelines.data_integrity.utils.normalize_meeting_value import normalize_meeting_value

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


# -------------------------------------------------
# EXTRACTION
# -------------------------------------------------

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


def extract_pdf_date_from_filename(filename: str):
    matches = re.findall(r"\d{8}", filename)
    for date_str in matches:
        try:
            return datetime.strptime(date_str, "%d%m%Y").date()
        except ValueError:
            continue
    return None


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


# -------------------------------------------------
# ARKIB CRAWL (UNCHANGED)
# -------------------------------------------------

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
    cycle_lookup: Dict,
):

    if max_nodes is not None and node_counter["count"] >= max_nodes:
        return

    if node_id in visited:
        return

    visited.add(node_id)
    node_counter["count"] += 1

    hierarchy = parse_node_id(node_id)

    html = fetch_html(session, base_url, uweb, node_id)
    all_sittings = extract_sittings(html)

    sittings = []
    for sitting in all_sittings:
        key = f"{house_name}/{sitting['filename']}"
        if key not in seen_sittings:
            seen_sittings.add(key)
            sittings.append(sitting)

    if not sittings or hierarchy["term"] is None:
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
                cycle_lookup,
            )
        return

    structure.setdefault(house_name, {})
    structure[house_name].setdefault("term", {})

    term_key = str(hierarchy["term"])
    structure[house_name]["term"].setdefault(
        term_key,
        {"sitting_count": 0, "session": {}},
    )

    structure[house_name]["term"][term_key]["sitting_count"] += len(sittings)

    if hierarchy["session"] is not None:

        session_key = str(hierarchy["session"])
        structure[house_name]["term"][term_key]["session"].setdefault(
            session_key,
            {"sitting_count": 0, "meeting": {}},
        )

        structure[house_name]["term"][term_key]["session"][session_key]["sitting_count"] += len(sittings)

        if hierarchy["meeting"] is not None:
            meeting_key = normalize_meeting_value(str(hierarchy["meeting"]))
            meeting_obj = structure[house_name]["term"][term_key]["session"][session_key]["meeting"].setdefault(
                meeting_key,
                {"sitting_count": 0, "filenames": []},
            )

            # Attach cycle date (arkib)
            house_code = HOUSE_MAP.get(house_name)

            meeting_norm = int(normalize_meeting_value(str(hierarchy["meeting"])))

            lookup_key = (
                house_code,
                hierarchy["term"],
                hierarchy["session"],
                meeting_norm,
            )

            cycle_info = cycle_lookup.get(lookup_key)

            if cycle_info:
                meeting_obj["start_date"] = cycle_info["start_date"]
                meeting_obj["end_date"] = cycle_info["end_date"]
                meeting_obj["source"] = "arkib"


            meeting_obj["sitting_count"] += len(sittings)

            for s in sittings:
                meeting_obj["filenames"].append(s["filename"])


# -------------------------------------------------
# ACTIVE INJECTION (NEW)
# -------------------------------------------------
def inject_active(structure, session, seen_sittings, category=None):

    active_cycles = scrape_active_cycles()
    reverse_house_map = {v: k for k, v in HOUSE_MAP.items()}

    for cycle in active_cycles:

        house_name = reverse_house_map.get(cycle["house"])

        if category and house_name != category:
            continue

        cfg = CATEGORIES[house_name]

        url = f"{cfg['base_url']}?uweb={cfg['uweb']}&lang=bm"
        response = session.get(url, timeout=120)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        divs = soup.find_all("div", class_="boxAktivitiContentText")

        for div in divs:
            for a_tag in div.find_all("a"):

                href = a_tag.get("href", "")
                if "loadResult" not in href:
                    continue

                match = re.search(r"'([^']+\.pdf)'", href)
                if not match:
                    continue

                filename = match.group(1).split("/")[-1]

                key = f"{house_name}/{filename}"
                if key in seen_sittings:
                    continue

                pdf_date = extract_pdf_date_from_filename(filename)
                if not pdf_date:
                    continue

                cycle_start = datetime.strptime(cycle["start_date"], "%Y-%m-%d").date()
                cycle_end = datetime.strptime(cycle["end_date"], "%Y-%m-%d").date()

                if not (cycle_start <= pdf_date <= cycle_end):
                    continue


                seen_sittings.add(key)

                term_key = str(cycle["term"])
                session_key = str(cycle["session"])
                meeting_key = normalize_meeting_value(str(cycle["meeting"]))

                structure.setdefault(house_name, {})
                structure[house_name].setdefault("term", {})
                structure[house_name]["term"].setdefault(
                    term_key, {"sitting_count": 0, "session": {}}
                )

                structure[house_name]["term"][term_key]["sitting_count"] += 1

                structure[house_name]["term"][term_key]["session"].setdefault(
                    session_key, {"sitting_count": 0, "meeting": {}}
                )

                structure[house_name]["term"][term_key]["session"][session_key]["sitting_count"] += 1

                meeting_obj = structure[house_name]["term"][term_key]["session"][session_key]["meeting"].setdefault(
                    meeting_key, {"sitting_count": 0, "filenames": []}
                )

                meeting_obj["sitting_count"] += 1
                meeting_obj["filenames"].append(filename)

                meeting_obj["start_date"] = cycle["start_date"]
                meeting_obj["end_date"] = cycle["end_date"]
                meeting_obj["source"] = "active"


def build_cycle_lookup():
    """
    Build a lookup of cycle dates keyed by house, term, session, meeting
    Combines arkib and active cycles and normalizes meeting values (e.g. source "11" -> "0") so cycle dates align with the db.
    """
    cycles = scrape_arkib_cycles() + scrape_active_cycles()

    lookup = {}
    for c in cycles:

        meeting_norm = normalize_meeting_value(str(c["meeting"]))

        key = (
            c["house"],
            c["term"],
            c["session"],
            int(meeting_norm),
        )

        lookup[key] = {
            "start_date": c["start_date"],
            "end_date": c["end_date"],
        }

    return lookup


# -------------------------------------------------
# SUMMARY / SNAPSHOT / UPLOAD (UNCHANGED)
# -------------------------------------------------

def compute_summary(structure: Dict) -> Dict:
    total_terms = total_sessions = total_meetings = total_sittings = 0

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
    key = f"checks/sittings/source/runs/{now.strftime('%Y%m%d')}/run_{now.strftime('%Y%m%dT%H%M%SZ')}.json"

    boto3.Session(region_name=AWS_REGION).client("s3").put_object(
        Bucket=S3_DATAPROC_BUCKET,
        Key=key,
        Body=json.dumps(snapshot, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )

    return key


# -------------------------------------------------
# MAIN
# -------------------------------------------------

def run_source_snapshot(category=None, term=None, term_range=None, max_nodes=None):

    session = make_session()
    structure: Dict = {}
    seen_sittings: Set[str] = set()
    node_counter = {"count": 0}
    cycle_lookup = build_cycle_lookup()

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
                cycle_lookup=cycle_lookup,
            )

    inject_active(structure, session, seen_sittings, category)

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
