from __future__ import annotations

import argparse
import json
import logging
from typing import List

import pandas as pd
import psycopg
from psycopg.rows import dict_row

from hansards_pipelines.settings import HANSARD_DB_URL
from hansards_pipelines.author_matching import perform_author_matching
from hansards_pipelines.utils.text_utils import house_mapper


class SimpleContext:
    def __init__(self, logger):
        self.log = logger

# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser("DB author matching (standalone)")
    p.add_argument("--sitting-ids", type=int, nargs="+", required=True)
    p.add_argument("--ensure-api-speech", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


# ---------------------------------------------------------------------
# DB LOADERS
# ---------------------------------------------------------------------

def load_authors(conn) -> pd.DataFrame:
    return pd.read_sql(
        "SELECT new_author_id, name, birth_year, ethnicity, sex FROM api_author",
        conn,
    )


def load_author_history(conn) -> pd.DataFrame:
    df = pd.read_sql(
        """
        SELECT ah.*, a.new_author_id, a.name
        FROM api_author_history ah
        JOIN api_author a ON a.new_author_id = ah.author_id
        """,
        conn,
    )
    df["area"] = ""
    return df


def load_sittings(conn, sitting_ids: List[int]) -> List[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT sitting_id, date, filename, speech_data
            FROM api_sitting
            WHERE sitting_id = ANY(%s)
            """,
            (sitting_ids,),
        )
        return list(cur.fetchall())


# ---------------------------------------------------------------------
# speech_data helpers
# ---------------------------------------------------------------------

def flatten_nested_speech(obj) -> List[dict]:
    rows = []

    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, dict) and "speech" in item:
                    rows.append(item)
                walk(item)

    walk(obj)
    return rows


# ---------------------------------------------------------------------
# api_speech rebuilder
# ---------------------------------------------------------------------

def rebuild_api_speech(conn, sitting: dict, logger):
    logger.info(f"api_speech missing in db -> rebuilding for sitting_id={sitting['sitting_id']}")

    speech_data = json.loads(sitting["speech_data"])
    flat = flatten_nested_speech(speech_data)

    if not flat:
        logger.warning("No speech rows found")
        return

    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM api_speech WHERE sitting_id = %s",
            (sitting["sitting_id"],),
        )

        rows = []
        for r in flat:
            speech = r.get("speech") or ""
            tokens = r.get("speech_tokens")

            # ✅ HARD GUARANTEES
            if not isinstance(tokens, list):
                tokens = []

            rows.append(
                (
                    sitting["sitting_id"],
                    int(r.get("index")),
                    r.get("author_id"),
                    r.get("timestamp") or "",
                    speech,
                    tokens,                 # ✅ NOT NULL
                    len(speech.split()),    # ✅ NOT NULL
                    None,
                    None,
                    None,
                    bool(r.get("is_annotation", False)),
                )
            )

        cur.executemany(
            """
            INSERT INTO api_speech (
                sitting_id,
                index,
                speaker_id,
                timestamp,
                speech,
                speech_tokens,
                length,
                level_1,
                level_2,
                level_3,
                is_annotation
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            rows,
        )


# ---------------------------------------------------------------------
# speech_data → DataFrame
# ---------------------------------------------------------------------

def speech_df_from_speech_data(sitting: dict) -> pd.DataFrame:
    nested = json.loads(sitting["speech_data"])
    flat = flatten_nested_speech(nested)

    rows = []
    for r in flat:
        rows.append(
            {
                "index": int(r.get("index")),
                "speech": r.get("speech"),
                "author": r.get("author"),
                "author_id": r.get("author_id"),
                "timestamp": r.get("timestamp"),
                "is_annotation": r.get("is_annotation", False),
                "date": sitting["date"],
                "house": house_mapper.to_canonical(
                    sitting["filename"].split("_")[0]
                ),
            }
        )

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():
    args = parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [db_author_matching] %(message)s",
    )
    logger = logging.getLogger("db_author_matching")

    with psycopg.connect(HANSARD_DB_URL) as conn:
        author_df = load_authors(conn)
        author_hist_df = load_author_history(conn)
        sittings = load_sittings(conn, args.sitting_ids)

        for sitting in sittings:
            logger.info(f"Processing sitting_id={sitting['sitting_id']}")

            if args.ensure_api_speech:
                with conn.transaction():
                    rebuild_api_speech(conn, sitting, logger)

            df_speech = speech_df_from_speech_data(sitting)

            context = SimpleContext(logger)

            matched = perform_author_matching(
                df_speech,
                author_df,
                author_hist_df,
                context,
            )

            # normalize author_id column WITHOUT touching perform_author_matching
            if "author_id_y" in matched.columns:
                matched["author_id"] = matched["author_id_y"]
            elif "author_id" not in matched.columns:
                raise RuntimeError(f"author_id not found, columns={list(matched.columns)}")

            match_rate = (~matched["author_id"].isna()).mean() * 100
            logger.info(f"Match rate: {match_rate:.2f}%")

            if args.dry_run:
                logger.info("Dry-run enabled → skipping update")
                continue

            updated = json.dumps(
                matched.to_dict(orient="records"),
                ensure_ascii=False,
                default=str,
            )

            with conn.transaction():
                conn.execute(
                    "UPDATE api_sitting SET speech_data = %s WHERE sitting_id = %s",
                    (updated, sitting["sitting_id"]),
                )

            logger.info("speech_data updated")


if __name__ == "__main__":
    main()
