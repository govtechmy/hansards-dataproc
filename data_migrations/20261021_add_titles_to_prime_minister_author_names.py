"""One-time PM name formatting: S3 author master -> seed -> api_author.name.

Preview by default. Author IDs, other attributes, histories and speeches stay
unchanged. S3 and PostgreSQL are not one transaction; rerun after partial failure.
"""
import argparse
from io import BytesIO
from pathlib import Path
import sys

import boto3
import pandas as pd
import psycopg2
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'hansards_pipelines'), str(ROOT / 'scripts/author_active_years')]
from hansards_pipelines.author_matching import normalize_malaysian_name
from hansards_pipelines.seed_data.author.handle_duplicate_author import (
    check_duplicate_ids, normalize_names, deduplicate,
)
from s3_csv import put_csv

MASTER = 'canonical/master/author.csv'
SEED = 'canonical/seed/author.csv'
# Preserve the existing spellings. Only add honorifics discarded by matching.
CHANGES = {
    21304: ('HUSSEIN ONN', 'TUN HUSSEIN ONN', 1922),
    375: ('MAHATHIR BIN MOHAMAD', 'TUN DR. MAHATHIR BIN MOHAMAD', 1925),
    2655: ('ABDULLAH BIN HAJI AHMAD BADAWI', 'TUN ABDULLAH BIN HAJI AHMAD BADAWI', 1939),
    1216: ('MOHD. NAJIB BIN TUN HAJI ABDUL RAZAK', "DATO' SRI MOHD. NAJIB BIN TUN HAJI ABDUL RAZAK", 1953),
    2797: ('MUHYIDDIN BIN MOHD. YASSIN', 'TAN SRI MUHYIDDIN BIN MOHD. YASSIN', 1947),
    3061: ('ISMAIL SABRI BIN YAAKOB', "DATO' SRI ISMAIL SABRI BIN YAAKOB", 1960),
    1426: ('ANWAR BIN IBRAHIM', "DATO' SERI ANWAR BIN IBRAHIM", 1947),
}


def validate(author_id, name, birth_year):
    old, new, birth = CHANGES[author_id]
    if name not in (old, new) or birth_year != birth:
        raise ValueError(f'Unexpected identity or attributes for author {author_id}')
    if normalize_malaysian_name(old) != normalize_malaysian_name(new):
        raise ValueError(f'Name change affects matching for author {author_id}')


def corrected_master(frame):
    check_duplicate_ids(frame)
    revised = frame.copy()
    for author_id in CHANGES:
        rows = revised[revised.new_author_id == author_id]
        if len(rows) != 1:
            raise ValueError(f'Expected exactly one author {author_id}')
        row = rows.iloc[0]
        validate(author_id, row['name'], row.birth_year)
        revised.loc[revised.new_author_id == author_id, 'name'] = CHANGES[author_id][1]
    return revised


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bucket', required=True)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--env-file', required=True)
    parser.add_argument('--region', default='ap-southeast-5')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--s3-only', action='store_true',
                        help='Update master and seed only; do not connect to the DB')
    args = parser.parse_args()
    s3 = boto3.Session(profile_name=args.profile).client('s3', region_name=args.region)
    originals, etags = {}, {}
    for key in (MASTER, SEED):
        obj = s3.get_object(Bucket=args.bucket, Key=key)
        etags[key] = obj['ETag']
        originals[key] = pd.read_csv(BytesIO(obj['Body'].read()))
    master = corrected_master(originals[MASTER])
    seed = master.copy()
    seed['_normalized_name'] = normalize_names(seed)
    seed = deduplicate(seed).drop(columns='_normalized_name')
    check_duplicate_ids(seed)
    if set(seed.new_author_id) != set(originals[SEED].new_author_id):
        raise ValueError('Seed regeneration changes author IDs; review before proceeding')
    for author_id, (_, new, _) in CHANGES.items():
        rows = seed[seed.new_author_id == author_id]
        if len(rows) != 1 or rows.iloc[0]['name'] != new:
            raise ValueError(f'Seed deduplication changed author {author_id}')
    print('MODE:', 'APPLY' if args.apply else 'PREVIEW', 'BUCKET:', args.bucket,
          'ENV FILE:', args.env_file)
    def apply_sources():
        for key, frame in ((MASTER, master), (SEED, seed)):
            if not frame.equals(originals[key]):
                put_csv(s3, args.bucket, key, frame, etags[key])
            readback = pd.read_csv(BytesIO(s3.get_object(Bucket=args.bucket, Key=key)['Body'].read()))
            pd.testing.assert_frame_equal(readback, frame)

    if args.s3_only:
        for author_id, (_, new, _) in CHANGES.items():
            old = originals[MASTER].loc[originals[MASTER].new_author_id == author_id, 'name'].iloc[0]
            print(author_id, old, '->', new)
        if args.apply:
            apply_sources()
            print('Verified S3 master and seed. No DB connection or DB changes.')
        else:
            print('Preview complete. No S3 writes or DB connection.')
        return
    url = dotenv_values(args.env_file).get('HANSARD_DB_URL')
    if not url:
        raise ValueError('HANSARD_DB_URL missing from the selected env file')
    with psycopg2.connect(url, connect_timeout=10) as conn:
        conn.set_session(readonly=not args.apply)
        with conn.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout='10s'")
            cur.execute("SET LOCAL statement_timeout='60s'")
            cur.execute('SELECT new_author_id,name,birth_year FROM api_author '
                        'WHERE new_author_id = ANY(%s)' + (' FOR UPDATE' if args.apply else ''),
                        (list(CHANGES),))
            rows = cur.fetchall()
            if {r[0] for r in rows} != set(CHANGES):
                raise ValueError('Expected all seven authors to exist in DB')
            for author_id, name, birth in rows:
                validate(author_id, name, birth)
                print(author_id, name, '->', CHANGES[author_id][1])
            if not args.apply:
                print('Preview complete. No S3 or DB writes.')
                return
            apply_sources()
            cur.executemany('UPDATE api_author SET name=%s WHERE new_author_id=%s',
                            [(change[1], author_id) for author_id, change in CHANGES.items()])
            cur.execute('SELECT new_author_id,name FROM api_author WHERE new_author_id = ANY(%s)',
                        (list(CHANGES),))
            if dict(cur.fetchall()) != {aid: change[1] for aid, change in CHANGES.items()}:
                raise ValueError('DB readback differs from the reviewed names')
    print('Verified S3 master, seed and seven DB names. Histories and speeches unchanged.')


if __name__ == '__main__':
    main()
