"""One-time correction of two ambiguous active-date extensions via S3 -> DB.

Original bounds verified from dumps/hansards_202609141134.dump. This restores
previous ranges; it does not resolve duplicate identities or validate old data.
"""
import argparse
from io import BytesIO

import boto3
import pandas as pd
import psycopg2
from dotenv import dotenv_values

from s3_csv import put_csv

# record_id: (author_id, erroneous bounds, original bounds)
FIXES = {
    3181: (21365, ('1965-08-10', '1983-12-31'), ('1972-01-01', '1974-12-31')),
    3212: (21396, ('1963-01-01', '2011-11-01'), ('2004-01-01', '2007-12-31')),
}


def iso(value):
    raw = str(value)
    return pd.to_datetime(raw, dayfirst=not (len(raw) > 4 and raw[4] == '-'), errors='raise').date().isoformat()


def restore(frame):
    frame = frame.copy()
    for record_id, (author_id, changed, original) in FIXES.items():
        found = frame[frame.record_id == record_id]
        if len(found) != 1:
            raise ValueError(f'Expected exactly one source history {record_id}')
        row = found.iloc[0]
        bounds = (iso(row.start_date), iso(row.end_date))
        if int(row.author_id) != author_id or row.exec_posts != 'derived_years_mentioned' or bounds not in (changed, original):
            raise ValueError(f'Unexpected source values for history {record_id}')
        frame.loc[frame.record_id == record_id, ['start_date', 'end_date']] = [pd.Timestamp(v).strftime('%d/%m/%Y') for v in original]
    return frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bucket', required=True)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--env-file', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    s3 = boto3.Session(profile_name=args.profile).client('s3', region_name='ap-southeast-5')
    objects = {}
    frames = {}
    for key in ('canonical/master/author_history.csv', 'canonical/seed/author_history.csv'):
        obj = s3.get_object(Bucket=args.bucket, Key=key)
        frames[key] = restore(pd.read_csv(BytesIO(obj['Body'].read())))
        objects[key] = obj
    with psycopg2.connect(dotenv_values(args.env_file)['HANSARD_DB_URL'], connect_timeout=10) as conn:
        conn.set_session(readonly=not args.apply)
        with conn.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout='10s'")
            cur.execute("SET LOCAL statement_timeout='60s'")
            for record_id, (author_id, changed, original) in FIXES.items():
                cur.execute('SELECT author_id,exec_posts,start_date::text,end_date::text FROM api_author_history WHERE record_id=%s' + (' FOR UPDATE' if args.apply else ''), (record_id,))
                row = cur.fetchone()
                if row is None or row[:2] != (author_id, 'derived_years_mentioned') or row[2:] not in (changed, original):
                    raise ValueError(f'Unexpected DB values for history {record_id}')
                cur.execute('''SELECT count(*) FROM api_speech p JOIN api_sitting s ON s.sitting_id=p.sitting_id
                    WHERE p.speaker_id=%s AND (s.date<%s OR s.date>%s)''', (record_id, *original))
                if cur.fetchone()[0]:
                    raise ValueError(f'History {record_id} has speech links outside original dates; review first')
                print(f'History {record_id}, author {author_id}: restore {original[0]}..{original[1]}')
            if not args.apply:
                print('Preview only; no S3 or DB changes.')
                return
            for key, frame in frames.items():
                put_csv(s3, args.bucket, key, frame, objects[key]['ETag'])
            for record_id, (_, _, original) in FIXES.items():
                cur.execute('UPDATE api_author_history SET start_date=%s,end_date=%s WHERE record_id=%s', (*original, record_id))
    print('Restored both source files and DB rows. Author identities and speeches unchanged.')


if __name__ == '__main__':
    main()
