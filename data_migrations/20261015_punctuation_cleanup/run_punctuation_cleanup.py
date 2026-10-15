"""Remove punctuation-only speech tokens without creating report or backup files."""

import argparse
import json
import sys
from pathlib import Path

import psycopg
from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "hansards_pipelines"))
from hansards_pipelines.utils.token_utils import punctuation_only


def clean_tokens(tokens):
    return None if tokens is None else [token for token in tokens if not punctuation_only(token)]


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
                cur.execute("""SELECT speech_id,speech_tokens FROM api_speech
                    WHERE speech_id>%s AND speech_id<=%s ORDER BY speech_id LIMIT %s""",
                    (last_id, upper_id, args.batch_size))
                rows = cur.fetchall()
                if not rows:
                    break
                changes = []
                batch_removed = 0
                for speech_id, before in rows:
                    after = clean_tokens(before)
                    if after != before:
                        changes.append({"speech_id": speech_id, "old_tokens": before, "new_tokens": after})
                        batch_removed += len(before) - len(after)
                if args.apply and changes:
                    cur.execute("""UPDATE api_speech s SET speech_tokens=r.new_tokens
                        FROM jsonb_to_recordset(%s::jsonb) AS r(
                            speech_id bigint, old_tokens text[], new_tokens text[])
                        WHERE s.speech_id=r.speech_id
                          AND s.speech_tokens IS NOT DISTINCT FROM r.old_tokens""",
                        (json.dumps(changes),))
                    if cur.rowcount != len(changes):
                        raise RuntimeError("Concurrent token update detected; this batch was rolled back. Rerun to continue.")
            scanned += len(rows)
            changed += len(changes)
            removed += batch_removed
            last_id = rows[-1][0]
            if scanned % 200000 < len(rows):
                print(f"Scanned {scanned:,}; affected speeches {changed:,}; punctuation tokens {removed:,}", flush=True)
    action = "Cleaned" if args.apply else "Would clean"
    print(f"{action} {changed:,} speeches; removed tokens: {removed:,}. Length unchanged.", flush=True)


if __name__ == "__main__":
    main()
