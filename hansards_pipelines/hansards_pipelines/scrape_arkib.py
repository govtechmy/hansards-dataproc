"""
Scrape Dewan Negara hansard archive pages and download all linked PDF files.

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

import logging
import re
import time
from pathlib import Path
from typing import Set
from urllib.parse import urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry


# -------------------------
# CATEGORY REGISTRY
# -------------------------
CATEGORIES = {
    "dewannegara": {
        "base_url": "https://www.parlimen.gov.my/hansard-dewan-negara.html",
        "output_dir": Path("arkib/dewannegara"),
    },
    "dewanrakyat": {
        "base_url": "https://www.parlimen.gov.my/hansard-dewan-rakyat.html",
        "output_dir": Path("arkib/dewanrakyat"),
    },
    "kamarkhas": {
        "base_url": "https://www.parlimen.gov.my/hansard-dewan-khas.html",
        "output_dir": Path("arkib/kamarkhas"),
    },
}

PDF_BASE_URL = "https://www.parlimen.gov.my"
ROOT_ID = "0"
REQUEST_DELAY = 0.2
LOG_LEVEL = logging.INFO


# -------------------------
# HTTP
# -------------------------
def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "hansards-dataproc/arkib-scraper",
    })

    retries = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # TLS OFF by default (known cert issues)
    logging.warning("TLS verification disabled (default)")
    session.verify = False
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    return session


def fetch_html(session: requests.Session, base_url: str, node_id: str) -> str:
    resp = session.get(
        base_url,
        params={"uweb": "dn", "arkib": "yes", "ajx": "1", "id": node_id},
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

    for a in soup.select("a[href$='.pdf'], a[href$='.PDF']"):
        url = urljoin(PDF_BASE_URL, a["href"])
        yield Path(urlparse(url).path).name, url

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
# DOWNLOAD
# -------------------------
def download_pdf(session: requests.Session, url: str, dest: Path):
    if dest.exists():
        logging.info("Skip %s", dest.name)
        return

    logging.info("Download %s", dest.name)
    dest.parent.mkdir(parents=True, exist_ok=True)

    with session.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)


# -------------------------
# CRAWLER
# -------------------------
def crawl(
    session: requests.Session,
    base_url: str,
    output_dir: Path,
    node_id: str,
    visited: Set[str],
):
    if node_id in visited:
        return
    visited.add(node_id)

    logging.info("Visiting %s | node %s", output_dir.name, node_id)
    html = fetch_html(session, base_url, node_id)

    for name, url in extract_pdfs(html):
        download_pdf(session, url, output_dir / name)

    for child in sorted(
        extract_child_ids(html),
        key=lambda x: [int(p) for p in x.split("_")],
    ):
        if child.startswith(f"{node_id}_") or node_id == ROOT_ID:
            crawl(session, base_url, output_dir, child, visited)


def main():
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    session = make_session()

    for category, cfg in CATEGORIES.items():
        logging.info("=== START %s ===", category)
        crawl(
            session=session,
            base_url=cfg["base_url"],
            output_dir=cfg["output_dir"],
            node_id=ROOT_ID,
            visited=set(),
        )
        logging.info("=== END %s ===", category)

    logging.info("All categories completed")


if __name__ == "__main__":
    main()
