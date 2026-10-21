"""Remove the 35 reviewed additional stopwords without creating report or backup files."""

import argparse
import sys
from pathlib import Path

import psycopg
from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "hansards_pipelines"))
from hansards_pipelines.utils.additional_stopwords import ADDITIONAL_STOPWORDS

STOPWORDS = frozenset(ADDITIONAL_STOPWORDS)


def clean_tokens(tokens):
    return None if tokens is None else [token for token in tokens if token not in STOPWORDS]


def run_batch(cur, last_id, upper_id, batch_size, apply):
    query = """
        WITH batch AS MATERIALIZED (
            SELECT speech_id, speech_tokens FROM api_speech
            WHERE speech_id>%s AND speech_id<=%s
            ORDER BY speech_id LIMIT %s
        ), cleaned AS MATERIALIZED (
            SELECT speech_id, speech_tokens AS old_tokens,
                ARRAY(SELECT token FROM unnest(speech_tokens) WITH ORDINALITY AS u(token, position)
                      WHERE token IS NULL OR NOT (token=ANY(%s::text[]))
                      ORDER BY position) AS new_tokens
            FROM batch WHERE speech_tokens && %s::text[]
        )
    """
    if apply:
        query += """, updated AS (
            UPDATE api_speech s SET speech_tokens=c.new_tokens FROM cleaned c
            WHERE s.speech_id=c.speech_id
              AND s.speech_tokens IS NOT DISTINCT FROM c.old_tokens
            RETURNING s.speech_id
        )"""
    query += """ SELECT (SELECT max(speech_id) FROM batch),
        (SELECT count(*) FROM batch), (SELECT count(*) FROM cleaned),
        coalesce((SELECT sum(cardinality(old_tokens)-cardinality(new_tokens)) FROM cleaned),0), """
    query += "(SELECT count(*) FROM updated)" if apply else "0"
    words = list(STOPWORDS)
    cur.execute(query, (last_id, upper_id, batch_size, words, words))
    next_id, scanned, changed, removed, updated = cur.fetchone()
    if apply and updated != changed:
        raise RuntimeError("Concurrent token update detected; this batch was rolled back. Rerun to continue.")
    return next_id, scanned, changed, removed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="Apply changes; otherwise preview counts only")
    parser.add_argument("--batch-size", type=int, default=2000)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("batch-size must be positive")
    cfg = dotenv_values(args.env_file)
    if not cfg.get("HANSARD_DB_URL"):
        parser.error("The environment file must contain HANSARD_DB_URL")
    scanned = changed = removed = last_id = 0
    with psycopg.connect(cfg["HANSARD_DB_URL"], connect_timeout=15, autocommit=True) as conn:
        conn.read_only = not args.apply
        with conn.cursor() as cur:
            cur.execute("SELECT coalesce(max(speech_id),0) FROM api_speech")
            upper_id = cur.fetchone()[0]
        while last_id < upper_id:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout = '10s'")
                cur.execute("SET LOCAL statement_timeout = '60s'")
                next_id, batch_scanned, batch_changed, batch_removed = run_batch(
                    cur, last_id, upper_id, args.batch_size, args.apply)
            if not batch_scanned:
                break
            scanned += batch_scanned
            changed += batch_changed
            removed += batch_removed
            last_id = next_id
            if scanned % 200000 < batch_scanned:
                print(f"Scanned {scanned:,}; affected speeches {changed:,}; stopword tokens {removed:,}", flush=True)
    action = "Cleaned" if args.apply else "Would clean"
    print(f"{action} {changed:,} speeches; removed tokens: {removed:,}. Length unchanged.", flush=True)


if __name__ == "__main__":
    main()
