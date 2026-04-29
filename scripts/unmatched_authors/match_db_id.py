#!/usr/bin/env python3
"""Match unmatched authors to api_author table and add db_new_author_id.

Reads:
  scripts/unmatched_authors/raw/SSD-1299-TO-TAG-all_unmatched_authors (2).xlsx

Writes:
  output_test/SSD-1299-TO-TAG__matched_to_api_author.xlsx
  output_test/SSD-1299-TO-TAG__matched_to_api_author.csv

New columns added:
  - cleaned_author: author with titles/brackets stripped
  - db_new_author_id: matched id from api_author (or None)
  - db_author_name: matched name from api_author (or None)
  - match_score: fuzzy match score (0-100)

Usage:
  python scripts/unmatched_authors/match_to_api_author.py
  python scripts/unmatched_authors/match_to_api_author.py --min-score 85
  python scripts/unmatched_authors/match_to_api_author.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import pandas as pd
import psycopg2
from thefuzz import fuzz, process

# Add parent path to import from hansards_pipelines
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from hansards_pipelines.settings import HANSARD_DB_URL  # type: ignore


DEFAULT_INPUT = (
    Path(__file__).resolve().parent
    / "raw"
    / "SSD-1299-TO-TAG-all_unmatched_authors (2).xlsx"
)
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# Minimum score to accept a match (0-100)
DEFAULT_MIN_SCORE = 80


# ─────────────────────────────────────────────────────────────────────────────
# Title stripping for cleaning author names before matching
# ─────────────────────────────────────────────────────────────────────────────
_TITLES = [
    r"YAB", r"YB", r"YBM", r"YBhg",
    r"DATO'", r"DATO\b", r"DATUK", r"DATIN",
    r"TAN\s+SRI", r"PUAN\s+SRI", r"SRI", r"SERI",
    r"TUN", r"TAN", r"TUAN", r"PUAN",
    r"HAJI", r"HAJAH", r"HJ\.?", r"HJH\.?",
    r"DR\.?", r"PROF\.?", r"IR\.?", r"TS\.?",
    r"MENTERI", r"TIMBALAN", r"SETIAUSAHA", r"PARLIMEN",
    r"PENGERUSI", r"PENGHULU", r"SPEAKER",
    r"YANG", r"BERHORMAT", r"MULIA",
    r"UTAMA", r"DIRAJA", r"WIRA", r"PATINGGI", r"AMAR",
    r"PERDANA",
]
_TITLE_RE = re.compile(r"\b(?:" + "|".join(_TITLES) + r")\b", re.IGNORECASE)

# Roles that are not real people (should not match to anyone)
_ROLE_BLACKLIST = {
    "pengerusi", "tuan pengerusi", "puan pengerusi",
    "yang di-pertua", "timbalan yang di-pertua",
    "perdana menteri", "timbalan perdana menteri",
    "speaker", "deputy speaker",
}


def clean_author_name(raw: str | float | None) -> str:
    """Strip titles, brackets, normalize for matching."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return ""
    s = str(raw)

    # Check if it's a role, not a person
    if s.strip().lower() in _ROLE_BLACKLIST:
        return ""

    # Remove bracketed content: [Kepong], (DAP), etc.
    s = re.sub(r"[\[\(].*?[\]\)]", " ", s)

    # Normalize apostrophes
    s = s.replace("'", "'").replace("`", "'")

    # Strip titles
    s = _TITLE_RE.sub(" ", s)

    # Remove punctuation-only tokens
    s = " ".join(tok for tok in s.split() if re.search(r"[A-Za-z0-9]", tok))
    s = re.sub(r"\s+", " ", s).strip()

    return s.upper()  # api_author names are uppercase


def fetch_api_authors() -> pd.DataFrame:
    """Fetch all authors from api_author table."""
    if not HANSARD_DB_URL:
        print("Error: HANSARD_DB_URL environment variable is not set.")
        sys.exit(1)

    try:
        conn = psycopg2.connect(HANSARD_DB_URL)
        query = """
            SELECT new_author_id, name
            FROM api_author
            WHERE name IS NOT NULL
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        print(f"Loaded {len(df)} authors from api_author table")
        return df
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        sys.exit(1)


def find_best_match(
    cleaned_name: str,
    api_authors: pd.DataFrame,
    min_score: int,
) -> tuple[int | None, str | None, int]:
    """Find best fuzzy match for cleaned_name in api_authors.
    
    Returns: (new_author_id, matched_name, score)
    """
    if not cleaned_name:
        return None, None, 0

    # Get list of (name, new_author_id) for matching
    choices = api_authors["name"].tolist()
    
    # Use token_set_ratio for better matching with name variations
    result = process.extractOne(
        cleaned_name,
        choices,
        scorer=fuzz.token_set_ratio,
        score_cutoff=min_score,
    )

    if result is None:
        return None, None, 0

    matched_name, score = result[0], result[1]
    # Find the id for this name
    row = api_authors[api_authors["name"] == matched_name].iloc[0]
    return int(row["new_author_id"]), matched_name, score


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Match unmatched authors to api_author table."
    )
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
        help="Path to input XLSX file",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory to write output files",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=DEFAULT_MIN_SCORE,
        help=f"Minimum fuzzy match score to accept (default: {DEFAULT_MIN_SCORE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print results without saving files",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only process first N rows (for testing)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load input
    print(f"Loading {input_path}...")
    df = pd.read_excel(input_path)
    if "author" not in df.columns:
        print(f"Error: No 'author' column in {input_path}")
        sys.exit(1)
    
    # Apply limit if specified
    if args.limit:
        df = df.head(args.limit)
        print(f"  Limited to first {args.limit} rows")
    else:
        print(f"  {len(df)} rows loaded")

    # Fetch api_author
    api_authors = fetch_api_authors()

    # Clean author names
    print("Cleaning author names...")
    df["cleaned_author"] = df["author"].apply(clean_author_name)

    # Match each author
    print(f"Matching authors (min_score={args.min_score})...")
    results = []
    matched_count = 0

    for idx, row in df.iterrows():
        cleaned = row["cleaned_author"]
        author_id, matched_name, score = find_best_match(
            cleaned, api_authors, args.min_score
        )
        results.append({
            "db_new_author_id": author_id,
            "db_author_name": matched_name,
            "match_score": score,
        })
        if author_id is not None:
            matched_count += 1

        # Progress indicator
        if (idx + 1) % 1000 == 0:
            print(f"  Processed {idx + 1}/{len(df)} rows...")

    # Add result columns
    results_df = pd.DataFrame(results)
    df["db_new_author_id"] = results_df["db_new_author_id"]
    df["db_author_name"] = results_df["db_author_name"]
    df["match_score"] = results_df["match_score"]
    
    # Fill real_name with db_author_name where we found a match
    # Convert db_author_name to title case for real_name
    df["real_name"] = results_df["db_author_name"].apply(
        lambda x: x.title() if pd.notna(x) else None
    )

    print(f"\nMatched: {matched_count}/{len(df)} ({100*matched_count/len(df):.1f}%)")

    # Show some examples
    print("\nSample matches:")
    matched_sample = df[df["db_new_author_id"].notna()].head(10)
    for _, r in matched_sample.iterrows():
        print(f"  {r['author'][:40]:<40} -> {r['db_author_name']} (score={r['match_score']})")

    print("\nSample non-matches:")
    unmatched_sample = df[df["db_new_author_id"].isna() & (df["cleaned_author"] != "")].head(10)
    for _, r in unmatched_sample.iterrows():
        print(f"  {r['author'][:50]} (cleaned: {r['cleaned_author'][:30]})")

    if args.dry_run:
        print("\n[Dry run - no files saved]")
        return

    # Remove temporary columns before saving
    df = df.drop(columns=["cleaned_author", "db_author_name", "match_score"], errors="ignore")

    # Save outputs
    out_xlsx = output_dir / "details_author.xlsx"
    out_csv = output_dir / "details_author.csv"

    df.to_excel(out_xlsx, index=False)
    df.to_csv(out_csv, index=False)

    print(f"\nWrote: {out_xlsx}")
    print(f"Wrote: {out_csv}")


if __name__ == "__main__":
    main()
