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

from hansards_pipelines.settings import S3_DATAPROC_BUCKET
from hansards_pipelines.utils.s3_utils import upload_stream_to_s3


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
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    logging.warning("TLS verification disabled")
    session.verify = False
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    return session


def fetch_html(session, base_url, uweb, node_id) -> str:
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
    return set(re.findall(r"<item[^>]+id=['\"]([0-9_]+)['\"]", html))


def download_pdf_to_s3(session, s3, bucket, key, url):
    logging.info("Uploading -> s3://%s/%s", bucket, key)
    with session.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        upload_stream_to_s3(
            s3_client=s3,
            bucket=bucket,
            key=key,
            stream=r.raw,
            content_type="application/pdf",
        )


def crawl(
    session,
    s3,
    base_url,
    uweb,
    house_folder,
    node_id,
    visited,
    collected_items: List[Dict],
):
    if node_id in visited:
        return
    visited.add(node_id)

    logging.info("Visiting %s | node %s", house_folder, node_id)
    html = fetch_html(session, base_url, uweb, node_id)

    for filename, url in extract_pdfs(html):
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
                house_folder,
                child,
                visited,
                collected_items,
            )


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", choices=CATEGORIES.keys())
    args = parser.parse_args()

    logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(message)s")

    session = make_session()
    s3 = boto3.client("s3")
    s3.head_bucket(Bucket=S3_DATAPROC_BUCKET)

    collected_items: List[Dict] = []

    categories = (
        {args.category: CATEGORIES[args.category]}
        if args.category
        else CATEGORIES
    )

    for name, cfg in categories.items():
        logging.info("=== START %s ===", name)
        crawl(
            session=session,
            s3=s3,
            base_url=cfg["base_url"],
            uweb=cfg["uweb"],
            house_folder=cfg["house_folder"],
            node_id=ROOT_ID,
            visited=set(),
            collected_items=collected_items,
        )
        logging.info("=== END %s ===", name)

    write_manifest_to_s3(s3, collected_items)
    logging.info("Done")


if __name__ == "__main__":
    main()
