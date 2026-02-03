"""
Scrape Dewan Negara hansard archive pages and upload into S3.

S3 layout:
s3://<S3_DATAPROC_BUCKET>/arkib/<house-folder>/<filename>.pdf

Example:
s3://my-bucket/arkib/dewannegara/dr_2025-01-01.pdf

The public site exposes a simple tree API, e.g.
* id=0                    -> list of parliaments
* id=0_15                 -> individual parliament (15th)
* id=0_15_3               -> session (penggal)
* id=0_15_3_2             -> meeting (mesyuarat) containing PDF links

This script walks that tree starting from id=0 and downloads every PDF it
finds into ``arkib/house-name/`` (relative to the working directory).

Usage (from repository root):
	python -m hansards_pipelines.scrape_arkib
    python -m hansards_pipelines.scrape_arkib --category dewannegara --limit 10
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Set, List, Dict
from urllib.parse import urljoin, urlparse

import boto3
import requests
import urllib3
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry

from hansards_pipelines.settings import S3_DATAPROC_BUCKET, AWS_REGION

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
    session = requests.Session()
    session.headers.update(
        {"User-Agent": "hansards-dataproc/arkib-scraper"}
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

    logging.warning("TLS verification disabled")
    session.verify = False
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    return session


def fetch_html(session, base_url, uweb, node_id) -> str:
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
                logging.warning(f"Timeout on attempt {attempt + 1}/{max_attempts}, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
            else:
                logging.error(f"Failed after {max_attempts} attempts: {e}")
                raise


def extract_pdfs(html: str):
    soup = BeautifulSoup(html, "html.parser")

    for a in soup.select("a[href$='.pdf'], a[href$='.PDF']"):
        url = urljoin(PDF_BASE_URL, a["href"])
        yield urlparse(url).path.split("/")[-1], url

    for u in soup.find_all("userdata"):
        m = re.search(
            r"loadResult\(['\"]([^'\"]+\.pdf)['\"],['\"]([^'\"]+)['\"]\)",
            u.text or "",
        )
        if m:
            path, name = m.groups()
            yield name, urljoin(PDF_BASE_URL, path)


def extract_child_ids(html: str) -> Set[str]:
    return set(re.findall(r"<item[^>]+id=['\"]([^'\"]+)['\"]", html))


def download_pdf_to_s3(session, s3, bucket, key, url):
    r = session.get(
        url,
        headers={
            "Accept": "application/pdf",
            "Accept-Encoding": "gzip, deflate",
            "Referer": PDF_BASE_URL,
        },
        timeout=60,
    )
    r.raise_for_status()

    data = r.content

    # Proper PDF validation:
    # Look for %PDF anywhere in the first 1KB
    if b"%PDF" not in data[:1024]:
        logging.warning("Skip non-PDF payload (%d bytes): %s", len(data), url)
        return

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType="application/pdf",
    )

    logging.info("Uploaded -> s3://%s/%s (%d bytes)", bucket, key, len(data),)


def crawl(
    session,
    s3,
    base_url,
    uweb,
    house_folder,
    node_id,
    visited,
    collected_items: List[Dict],
    counter: Dict[str, int],
    limit: int | None,
    seen_files: set[str],
):
    if limit is not None and counter["count"] >= limit:
        return

    if node_id in visited:
        return
    visited.add(node_id)

    logging.info("Visiting %s | node %s", house_folder, node_id)
    html = fetch_html(session, base_url, uweb, node_id)
    for filename, url in extract_pdfs(html):
        if limit is not None and counter["count"] >= limit:
            return

        key_id = f"{house_folder}/{filename}"
        if key_id in seen_files:
            continue

        seen_files.add(key_id)

        key = f"arkib/{house_folder}/{filename}"
        download_pdf_to_s3(
            session=session,
            s3=s3,
            bucket=S3_DATAPROC_BUCKET,
            key=key,
            url=url,
        )

        collected_items.append(
            {
                "house_folder": house_folder,
                "filename": filename,
            }
        )

        counter["count"] += 1

    for child in sorted(
        extract_child_ids(html),
        key=lambda x: [int(p) for p in x.split("_") if p.isdigit()]
    ):
        if limit is not None and counter["count"] >= limit:
            return

        crawl(
            session,
            s3,
            base_url,
            uweb,
            house_folder,
            child,
            visited,
            collected_items,
            counter,
            limit,
            seen_files=seen_files,
        )

def seed_kamarkhas_start_nodes(session) -> List[str]:
    """
    Kamar Khas does not list parliament nodes at the root (id=0),
    so need to try possible IDs and keep the ones that return data.
    """
    seeds = []

    # Parliament numbers; adjust if needed
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

        # If this node has children, it's real
        if extract_child_ids(html):
            seeds.append(node_id)

    return seeds


def write_manifest_to_s3(s3, items: List[Dict]):
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }

    key = "arkib/manifest.json"

    s3.put_object(
        Bucket=S3_DATAPROC_BUCKET,
        Key=key,
        Body=json.dumps(manifest, indent=2).encode("utf-8"),
        ContentType="application/json",
    )

    logging.info("Manifest written -> s3://%s/%s", S3_DATAPROC_BUCKET, key)

def run_scrape(
    *,
    category: str | None = None,
    limit: int | None = None,
):
    session = make_session()
    s3 = boto3.client("s3", region_name=AWS_REGION)

    collected_items: List[Dict] = []
    counter = {"count": 0}
    seen_files: set[str] = set()

    categories = (
        {category: CATEGORIES[category]}
        if category
        else CATEGORIES
    )

    for name, cfg in categories.items():
        logging.info("=== START %s ===", name)

        if name == "kamarkhas":
            start_nodes = seed_kamarkhas_start_nodes(session)
        else:
            start_nodes = [ROOT_ID]

        for start_id in start_nodes:
            crawl(
                session=session,
                s3=s3,
                base_url=cfg["base_url"],
                uweb=cfg["uweb"],
                house_folder=cfg["house_folder"],
                node_id=start_id,
                visited=set(),
                collected_items=collected_items,
                counter=counter,
                limit=limit,
                seen_files=seen_files,
            )

        logging.info("=== END %s ===", name)

    write_manifest_to_s3(s3, collected_items)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", choices=CATEGORIES.keys())
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(message)s")

    run_scrape(category=args.category, limit=args.limit)

    logging.info("Done")


if __name__ == "__main__":
    main()
