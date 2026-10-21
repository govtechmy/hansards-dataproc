"""One-time data migration: reviewed Tunku and Lipis author corrections via S3.

Updates master, regenerates seed with existing deduplication, then upserts only
the two reviewed IDs into the selected DB. Rerunnable after a partial failure.
"""
import argparse
from io import BytesIO
from pathlib import Path
import sys

import boto3
import pandas as pd
import psycopg2
from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'hansards_pipelines'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from s3_csv import put_csv
from hansards_pipelines.seed_data.author.handle_duplicate_author import check_duplicate_ids, normalize_names, deduplicate

FIELDS = ['new_author_id', 'name', 'birth_year', 'ethnicity', 'sex']
CORRECTIONS = [
    (1, 'TUNKU ABDUL RAHMAN PUTRA AL-HAJ', 1903, 'bumiputera', 'm'),
    (21690, 'ABDUL RAZAK BIN HAJI HUSSIN', 1923, 'bumiputera', 'm'),
]
MASTER = 'canonical/master/author.csv'
SEED = 'canonical/seed/author.csv'


def corrected_master(frame):
    frame = frame.copy()
    check_duplicate_ids(frame)
    for author_id, name, birth, ethnicity, sex in CORRECTIONS:
        found = frame[frame.new_author_id == author_id]
        if author_id == 1:
            possible = frame[frame.name.str.contains(r'ABDUL.*RAHMAN', case=False, na=False)
                             & (frame.name.str.contains('TUNKU|PUTRA', case=False, na=False) | (frame.birth_year == 1903))]
            if any(possible.new_author_id != 1):
                raise ValueError('Tunku may already exist under another ID; review source before applying')
        if len(found):
            old = found.iloc[0]
            allowed = {name} | ({'ABDUL RAZAK HAJI HUSSAIN'} if author_id == 21690 else set())
            if old['name'] not in allowed or int(old.birth_year) not in ({1922, 1923} if author_id == 21690 else {1903}):
                raise ValueError(f'Unexpected source identity for author {author_id}')
            if old.ethnicity != ethnicity or old.sex != sex:
                raise ValueError(f'Unexpected source attributes for author {author_id}')
            frame.loc[frame.new_author_id == author_id, FIELDS] = [author_id, name, birth, ethnicity, sex]
        elif author_id == 1:
            frame = pd.concat([frame, pd.DataFrame([[author_id, name, birth, ethnicity, sex]], columns=FIELDS)], ignore_index=True)
        else:
            raise ValueError(f'Expected source author {author_id} is missing')
    return frame


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bucket', required=True)
    p.add_argument('--profile', required=True)
    p.add_argument('--env-file', required=True)
    p.add_argument('--region', default='ap-southeast-5')
    p.add_argument('--apply', action='store_true')
    args = p.parse_args()
    s3 = boto3.Session(profile_name=args.profile).client('s3', region_name=args.region)
    objects = {key: s3.get_object(Bucket=args.bucket, Key=key) for key in (MASTER, SEED)}
    original = pd.read_csv(BytesIO(objects[MASTER]['Body'].read()))
    objects[SEED]['Body'].close()
    master = corrected_master(original)
    seed = master.copy()
    seed['_normalized_name'] = normalize_names(seed)
    seed = deduplicate(seed).drop(columns='_normalized_name')
    if not set(r[0] for r in CORRECTIONS).issubset(set(seed.new_author_id)):
        raise ValueError('Seed deduplication removed a reviewed author ID')
    print('BUCKET:', args.bucket, 'ENV FILE:', args.env_file, 'MODE:', 'APPLY' if args.apply else 'PREVIEW')
    print(seed[seed.new_author_id.isin([1, 21690])][FIELDS].to_string(index=False))
    cfg = dotenv_values(args.env_file)
    with psycopg2.connect(cfg['HANSARD_DB_URL'], connect_timeout=10) as conn:
        conn.set_session(readonly=not args.apply)
        with conn.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout='10s'")
            cur.execute("SET LOCAL statement_timeout='60s'")
            cur.execute('SELECT new_author_id,name,birth_year FROM api_author WHERE new_author_id IN (1,21690)' + (' FOR UPDATE' if args.apply else ''))
            for author_id, name, birth in cur.fetchall():
                expected = next(r for r in CORRECTIONS if r[0] == author_id)
                allowed = {expected[1]} | ({'ABDUL RAZAK HAJI HUSSAIN'} if author_id == 21690 else set())
                if name not in allowed or birth not in ({1922,1923} if author_id == 21690 else {1903}):
                    raise ValueError(f'DB author {author_id} differs from reviewed identity')
            if not args.apply:
                print('Preview only: no S3 or DB writes.')
                return
            for key, frame in ((MASTER, master), (SEED, seed)):
                put_csv(s3, args.bucket, key, frame, objects[key]['ETag'])
                print('UPDATED S3:', key)
            # Do not reload unrelated stale source rows over newer DB corrections.
            cur.executemany('''INSERT INTO api_author (new_author_id,name,birth_year,ethnicity,sex)
                OVERRIDING SYSTEM VALUE VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (new_author_id) DO UPDATE SET name=EXCLUDED.name,
                birth_year=EXCLUDED.birth_year,ethnicity=EXCLUDED.ethnicity,sex=EXCLUDED.sex''', CORRECTIONS)
            cur.execute('SELECT new_author_id,name,birth_year FROM api_author WHERE new_author_id IN (1,21690) ORDER BY new_author_id')
            print('VERIFIED DB:', cur.fetchall())
    print('Complete. Histories and speeches were not changed.')


if __name__ == '__main__':
    main()
