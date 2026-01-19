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
finds into ``arkib/dewan-negara/`` (relative to the working directory).

Usage (from repository root):
	python -m hansards_pipelines.scrape_arkib
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Set
from urllib.parse import urljoin, urlparse

import boto3
import requests
import urllib3
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry

from hansards_pipelines.settings import S3_DATAPROC_BUCKET
from hansards_pipelines.utils.s3_utils import s3_object_exists, upload_stream_to_s3

# -------------------------
# CONFIG
# -------------------------
PDF_BASE_URL = "https://www.parlimen.gov.my"
ROOT_ID = "0"
REQUEST_DELAY = 0.2
LOG_LEVEL = logging.INFO

# -------------------------
# CATEGORY REGISTRY
# -------------------------
CATEGORIES = {
    "dewannegara": {
        "base_url": "https://www.parlimen.gov.my/hansard-dewan-negara.html",
        "uweb": "dn",
        "s3_prefix": "arkib/dewannegara/",
    },
    "dewanrakyat": {
        "base_url": "https://www.parlimen.gov.my/hansard-dewan-rakyat.html",
        "uweb": "dr",
        "s3_prefix": "arkib/dewanrakyat/",
    },
    "kamarkhas": {
        "base_url": "https://www.parlimen.gov.my/hansard-dewan-khas.html",
        "uweb": "dr",
        "s3_prefix": "arkib/kamarkhas/",
    },
}

# -------------------------
# HTTP
# -------------------------
def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {"User-Agent": "hansards-dataproc/arkib-scraper"}
    )

    retries = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # TLS OFF (known cert issues)
    logging.warning("TLS verification disabled")
    session.verify = False
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    return session


def fetch_html(
    session: requests.Session,
    base_url: str,
    uweb: str,
    node_id: str,
) -> str:
    resp = session.get(
        base_url,
        params={
            "uweb": uweb,
            "arkib": "yes",
            "ajx": "1",
            "id": node_id,
        },
        timeout=20,
    )
    resp.raise_for_status()

    if REQUEST_DELAY:
        time.sleep(REQUEST_DELAY)

    return resp.text


# -------------------------
# PARSING
# -------------------------
def extract_pdfs(html: str):
    soup = BeautifulSoup(html, "html.parser")

    # Normal <a href="...pdf">
    for a in soup.select("a[href$='.pdf'], a[href$='.PDF']"):
        url = urljoin(PDF_BASE_URL, a["href"])
        yield urlparse(url).path.split("/")[-1], url

    # JS-based links
    for u in soup.find_all("userdata"):
        m = re.search(
            r"loadResult\(['\"]([^'\"]+\.pdf)['\"],['\"]([^'\"]+)['\"]\)",
            u.text or "",
        )
        if m:
            path, name = m.groups()
            yield name, urljoin(PDF_BASE_URL, path)


def extract_child_ids(html: str) -> Set[str]:
    return set(re.findall(r"<item[^>]+id=['\"]([0-9_]+)['\"]", html))

# -------------------------
# S3 HELPERS
# -------------------------
def download_pdf_to_s3(
    session: requests.Session,
    s3,
    bucket: str,
    key: str,
    url: str,
):
    if s3_object_exists(s3, bucket, key):
        logging.info("Skip (exists): %s", key)
        return

    logging.info("Downloaded -> s3://%s/%s", bucket, key)

    with session.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        upload_stream_to_s3(
            s3_client=s3,
            bucket=bucket,
            key=key,
            stream=r.raw,
            content_type="application/pdf",
        )


# -------------------------
# CRAWLER
# -------------------------
def crawl(
    session: requests.Session,
    s3,
    base_url: str,
    uweb: str,
    s3_prefix: str,
    node_id: str,
    visited: Set[str],
):
    if node_id in visited:
        return
    visited.add(node_id)

    logging.info("Visiting %s | node %s", s3_prefix, node_id)
    html = fetch_html(session, base_url, uweb, node_id)

    for name, url in extract_pdfs(html):
        key = f"{s3_prefix}{name}"
        download_pdf_to_s3(
            session=session,
            s3=s3,
            bucket=S3_DATAPROC_BUCKET,
            key=key,
            url=url,
        )

    for child in sorted(
        extract_child_ids(html),
        key=lambda x: [int(p) for p in x.split("_")],
    ):
        if child.startswith(f"{node_id}_") or node_id == ROOT_ID:
            crawl(
                session,
                s3,
                base_url,
                uweb,
                s3_prefix,
                child,
                visited,
            )


# -------------------------
# MANIFEST
# -------------------------
def write_manifest_to_s3(s3, stats: dict):
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "categories": stats,
    }

    key = "arkib/manifest.json"

    s3.put_object(
        Bucket=S3_DATAPROC_BUCKET,
        Key=key,
        Body=json.dumps(manifest, indent=2).encode("utf-8"),
        ContentType="application/json",
    )

    logging.info(
        "Manifest uploaded → s3://%s/%s",
        S3_DATAPROC_BUCKET,
        key,
    )


# -------------------------
# ENTRYPOINT
# -------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--category",
        choices=CATEGORIES.keys(),
        help="Scrape only one category (default: all)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    session = make_session()
    s3 = boto3.client("s3")
    stats = {}

    categories = (
        {args.category: CATEGORIES[args.category]}
        if args.category
        else CATEGORIES
    )

    for category, cfg in categories.items():
        logging.info("=== START %s ===", category)

        crawl(
            session=session,
            s3=s3,
            base_url=cfg["base_url"],
            uweb=cfg["uweb"],
            s3_prefix=cfg["s3_prefix"],
            node_id=ROOT_ID,
            visited=set(),
        )

        stats[category] = {
            "s3_prefix": cfg["s3_prefix"],
        }

        logging.info("=== END %s ===", category)

    write_manifest_to_s3(s3, stats)
    logging.info("Done")


if __name__ == "__main__":
    main()
