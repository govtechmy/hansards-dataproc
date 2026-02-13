"""
Count parliamentary hansard PDFs and organize by parliament, session, and meeting.

This script walks the parliament archive tree and creates a hierarchical JSON structure:
{
    "category": {
        "parliament_number": {
            "sessions": {
                "session_number": {
                    "meetings": {
                        "meeting_number": {
                            "pdf_count": 5
                        }
                    }
                }
            }
        }
    }
}

Usage:
    python -m hansards_pipelines.count_website_files
    python -m hansards_pipelines.count_website_files --category dewannegara
    python -m hansards_pipelines.count_website_files --category dewannegara --parliament 13
    python -m hansards_pipelines.count_website_files --category dewannegara --parliament-range 10 15

Environment Variables:
    DISABLE_TLS_VERIFY: Set to 'true', '1', or 'yes' to disable TLS certificate verification
                        (only use if encountering SSL errors with the parliament website)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set
from urllib.parse import urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry

PDF_BASE_URL = "https://www.parlimen.gov.my"
ROOT_ID = "0"
REQUEST_DELAY = 0.2
LOG_LEVEL = logging.INFO

CATEGORIES = {
    "dewannegara": {
        "base_url": "https://www.parlimen.gov.my/hansard-dewan-negara.html",
        "uweb": "dn",
        "house_folder": "dewannegara",
    },
    "dewanrakyat": {
        "base_url": "https://www.parlimen.gov.my/hansard-dewan-rakyat.html",
        "uweb": "dr",
        "house_folder": "dewanrakyat",
    },
    "kamarkhas": {
        "base_url": "https://www.parlimen.gov.my/hansard-dewan-khas.html",
        "uweb": "dr",
        "house_folder": "kamarkhas",
    },
}


def make_session() -> requests.Session:
    """
    Create HTTP session with retry logic and custom headers.
    
    TLS verification is enabled by default for security. To disable (not recommended),
    set the DISABLE_TLS_VERIFY environment variable to 'true', '1', or 'yes'.
    """
    session = requests.Session()
    session.headers.update(
        {"User-Agent": "hansards-dataproc/structured-scraper"}
    )

    retries = Retry(
        total=5,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # Only disable TLS verification if explicitly requested via environment variable
    if os.getenv("DISABLE_TLS_VERIFY", "").lower() in ("true", "1", "yes"):
        logging.warning("TLS verification disabled (DISABLE_TLS_VERIFY is set)")
        session.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    return session


def fetch_html(session: requests.Session, base_url: str, uweb: str, node_id: str) -> str:
    """Fetch HTML from parliament archive API."""
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            resp = session.get(
                base_url,
                params={
                    "uweb": uweb,
                    "arkib": "yes",
                    "ajx": "1",
                    "id": node_id,
                },
                timeout=30,
            )
            resp.raise_for_status()

            if REQUEST_DELAY:
                time.sleep(REQUEST_DELAY)

            return resp.text
        except requests.exceptions.RequestException as e:
            if attempt < max_attempts - 1:
                wait_time = 5 * (attempt + 1)
                logging.warning(
                    f"Timeout on attempt {attempt + 1}/{max_attempts}, "
                    f"retrying in {wait_time}s: {e}"
                )
                time.sleep(wait_time)
            else:
                logging.error(f"Failed after {max_attempts} attempts: {e}")
                raise


def extract_pdfs(html: str) -> List[Dict[str, str]]:
    """Extract PDF information from HTML."""
    pdfs = []
    soup = BeautifulSoup(html, "html.parser")

    # Method 1: Direct PDF links
    for a in soup.select("a[href$='.pdf'], a[href$='.PDF']"):
        url = urljoin(PDF_BASE_URL, a["href"])
        filename = urlparse(url).path.split("/")[-1]
        pdfs.append({
            "filename": filename,
            "url": url,
        })

    # Method 2: JavaScript loadResult calls in userdata tags
    for u in soup.find_all("userdata"):
        m = re.search(
            r"loadResult\(['\"]([^'\"]+\.pdf)['\"],['\"]([^'\"]+)['\"]\)",
            u.text or "",
        )
        if m:
            path, name = m.groups()
            pdfs.append({
                "filename": name,
                "url": urljoin(PDF_BASE_URL, path),
            })

    return pdfs


def extract_child_ids(html: str) -> Set[str]:
    """Extract child node IDs from HTML."""
    return set(re.findall(r"<item[^>]+id=['\"]([^'\"]+)['\"]", html))


def parse_node_id(node_id: str) -> Dict[str, int | None]:
    """
    Parse node ID to extract hierarchy information.
    
    Examples:
        "0" -> root
        "0_15" -> parliament 15
        "0_15_3" -> parliament 15, session 3
        "0_15_3_2" -> parliament 15, session 3, meeting 2
    """
    parts = node_id.split("_")
    
    result = {
        "parliament": None,
        "session": None,
        "meeting": None,
    }
    
    if len(parts) >= 2:
        result["parliament"] = int(parts[1])
    if len(parts) >= 3:
        result["session"] = int(parts[2])
    if len(parts) >= 4:
        result["meeting"] = int(parts[3])
    
    return result


def crawl_structured(
    session: requests.Session,
    base_url: str,
    uweb: str,
    category_name: str,
    node_id: str,
    visited: Set[str],
    structure: Dict,
    seen_pdfs: Set[str],
) -> None:
    """
    Recursively crawl the archive tree and build structured data.
    
    Updates the structure dict in place with hierarchy:
    structure[category][parliament][sessions][session][meetings][meeting][pdf_count] = N
    """
    if node_id in visited:
        return
    visited.add(node_id)

    hierarchy = parse_node_id(node_id)
    logging.info(
        "Visiting %s | node %s | P%s S%s M%s",
        category_name,
        node_id,
        hierarchy["parliament"] or "-",
        hierarchy["session"] or "-",
        hierarchy["meeting"] or "-",
    )

    html = fetch_html(session, base_url, uweb, node_id)
    
    # Extract PDFs at this level
    all_pdfs = extract_pdfs(html)
    
    # Filter out PDFs we've already seen
    pdfs = []
    for pdf in all_pdfs:
        pdf_key = f"{category_name}/{pdf['filename']}"
        if pdf_key not in seen_pdfs:
            seen_pdfs.add(pdf_key)
            pdfs.append(pdf)
    
    if pdfs and hierarchy["parliament"] is not None:
        # Initialize category structure
        if category_name not in structure:
            structure[category_name] = {}
        
        parl_key = f"P{hierarchy['parliament']}"
        
        # Initialize parliament structure
        if parl_key not in structure[category_name]:
            structure[category_name][parl_key] = {
                "parliament_number": hierarchy["parliament"],
                "sessions": {}
            }
        
        # Handle session level
        if hierarchy["session"] is not None:
            sess_key = f"S{hierarchy['session']}"
            
            if sess_key not in structure[category_name][parl_key]["sessions"]:
                structure[category_name][parl_key]["sessions"][sess_key] = {
                    "session_number": hierarchy["session"],
                    "meetings": {}
                }
            
            # Handle meeting level
            if hierarchy["meeting"] is not None:
                meet_key = f"M{hierarchy['meeting']}"
                
                if meet_key not in structure[category_name][parl_key]["sessions"][sess_key]["meetings"]:
                    structure[category_name][parl_key]["sessions"][sess_key]["meetings"][meet_key] = {
                        "meeting_number": hierarchy["meeting"],
                        "pdf_count": 0
                    }
                
                # Count PDFs in this meeting
                structure[category_name][parl_key]["sessions"][sess_key]["meetings"][meet_key]["pdf_count"] += len(pdfs)
            else:
                # PDFs at session level (no specific meeting)
                if "pdf_count" not in structure[category_name][parl_key]["sessions"][sess_key]:
                    structure[category_name][parl_key]["sessions"][sess_key]["pdf_count"] = 0
                structure[category_name][parl_key]["sessions"][sess_key]["pdf_count"] += len(pdfs)
        else:
            # PDFs at parliament level (no specific session)
            if "pdf_count" not in structure[category_name][parl_key]:
                structure[category_name][parl_key]["pdf_count"] = 0
            structure[category_name][parl_key]["pdf_count"] += len(pdfs)

    # Recursively process child nodes
    child_ids = extract_child_ids(html)
    for child in sorted(
        child_ids,
        key=lambda x: [int(p) for p in x.split("_") if p.isdigit()]
    ):
        crawl_structured(
            session=session,
            base_url=base_url,
            uweb=uweb,
            category_name=category_name,
            node_id=child,
            visited=visited,
            structure=structure,
            seen_pdfs=seen_pdfs,
        )


def seed_kamarkhas_start_nodes(session: requests.Session) -> List[str]:
    """
    Kamar Khas does not list parliament nodes at root (id=0),
    so try possible IDs and keep valid ones.
    """
    seeds = []
    
    for parlimen in range(1, 50):
        node_id = f"0_{parlimen}"
        try:
            html = fetch_html(
                session,
                base_url=CATEGORIES["kamarkhas"]["base_url"],
                uweb="dr",
                node_id=node_id,
            )
        except Exception:
            continue
        
        if extract_child_ids(html):
            seeds.append(node_id)
    
    return seeds


def run_scrape_structured(
    *,
    category: str | None = None,
    parliament: int | None = None,
    parliament_range: tuple[int, int] | None = None,
    output_file: str = "website_file_count.json",
) -> Dict:
    """
    Main function to scrape and structure hansard data.
    
    Returns the structured data dictionary.
    """
    session = make_session()
    structure: Dict = {}
    seen_pdfs: Set[str] = set()
    
    categories = (
        {category: CATEGORIES[category]}
        if category
        else CATEGORIES
    )
    
    for name, cfg in categories.items():
        logging.info("=== START %s ===", name)
        
        # Determine start nodes
        if name == "kamarkhas":
            if parliament:
                start_nodes = [f"0_{parliament}"]
            elif parliament_range:
                start_nodes = [f"0_{p}" for p in range(parliament_range[0], parliament_range[1] + 1)]
            else:
                start_nodes = seed_kamarkhas_start_nodes(session)
        else:
            if parliament:
                start_nodes = [f"0_{parliament}"]
            elif parliament_range:
                start_nodes = [f"0_{p}" for p in range(parliament_range[0], parliament_range[1] + 1)]
            else:
                start_nodes = [ROOT_ID]
        
        # Crawl each start node
        for start_id in start_nodes:
            crawl_structured(
                session=session,
                base_url=cfg["base_url"],
                uweb=cfg["uweb"],
                category_name=name,
                node_id=start_id,
                visited=set(),
                structure=structure,
                seen_pdfs=seen_pdfs,
            )
        
        logging.info("=== END %s ===", name)
    
    # Add metadata
    output_data = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "script": "count_website_files.py",
            "category_filter": category,
            "parliament_filter": parliament,
            "parliament_range_filter": parliament_range,
        },
        "data": structure,
    }
    
    # Write to file
    output_path = Path(output_file)
    output_path.write_text(json.dumps(output_data, indent=2, ensure_ascii=False))
    logging.info("Structured data written to %s", output_path.absolute())
    
    return output_data


def main():
    parser = argparse.ArgumentParser(
        description="Count hansard PDFs and organize by parliament/session/meeting"
    )
    parser.add_argument(
        "--category",
        choices=CATEGORIES.keys(),
        help="Filter to specific category (dewannegara, dewanrakyat, kamarkhas)"
    )
    parser.add_argument(
        "--parliament",
        type=int,
        help="Filter to specific parliament number (e.g., 13 for P13)"
    )
    parser.add_argument(
        "--parliament-range",
        nargs=2,
        type=int,
        metavar=("START", "END"),
        help="Filter to parliament range (e.g., 10 15 for P10 to P15 inclusive)"
    )
    parser.add_argument(
        "--output",
        default="website_file_count.json",
        help="Output JSON file path (default: website_file_count.json)"
    )
    args = parser.parse_args()
    
    # Validate that both parliament and parliament-range are not specified
    if args.parliament and args.parliament_range:
        parser.error("Cannot specify both --parliament and --parliament-range")
    # Validate individual parliament value (if provided)
    if args.parliament is not None and args.parliament < 1:
        parser.error("--parliament must be a positive integer (>= 1)")
    # Validate parliament range values (if provided)
    if args.parliament_range:
        start, end = args.parliament_range
        if start < 1 or end < 1:
            parser.error("--parliament-range values must be positive integers (>= 1)")
        if start > end:
            parser.error("Invalid --parliament-range: START must be less than or equal to END")
    
    parliament_range = tuple(args.parliament_range) if args.parliament_range else None
    
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    
    run_scrape_structured(
        category=args.category,
        parliament=args.parliament,
        parliament_range=parliament_range,
        output_file=args.output,
    )
    
    logging.info("Done")


if __name__ == "__main__":
    main()
