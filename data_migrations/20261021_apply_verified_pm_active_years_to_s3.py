"""Apply the reviewed 15 PM speaking-date corrections to S3 history files.

Production's old S3 master omits these records, although they exist in its DB.
Read existing IDs/attributes from that DB and add only the reviewed records to
S3, using bounds from the complete evidence report. Never writes to the DB.
Preview by default; safe to rerun after a partial S3 write.
"""
import argparse
from io import BytesIO
import json
from pathlib import Path
import sys

import boto3
import pandas as pd
import psycopg2
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'hansards_pipelines'), str(ROOT / 'scripts/author_active_years')]
from rebuild_ranges import as_date
from s3_csv import put_csv

IDS = {3120, 4468, 4496, 4521, 4609, 4618, 4854, 4885,
       6342, 6368, 6451, 6464, 6475, 7267, 7326}
MASTER = 'canonical/master/author_history.csv'
SEED = 'canonical/seed/author_history.csv'
DB_FIELDS = ['record_id', 'author_id', 'party', 'area_id', 'exec_posts',
             'service_posts', 'start_date', 'end_date']


def prepare(original, records, plans, master=False):
    if original.record_id.duplicated().any():
        raise ValueError('Duplicate S3 history IDs')
    frame = original.copy()
    if master:
        for column in ('derived_scope_start', 'derived_scope_end'):
            if column not in frame:
                frame[column] = pd.Series(None, index=frame.index, dtype=object)
    for rid, plan in plans.items():
        target = plan['proposed']
        rows = frame[frame.record_id == rid]
        if len(rows):
            row = rows.iloc[0]
            if int(row.author_id) != plan['author_id'] or row.exec_posts != 'derived_years_mentioned':
                raise ValueError(f'S3 ownership/status mismatch: {rid}')
            # Reruns accept only the previously inspected DB or target bounds.
            before = records[rid]
            bounds = (as_date(row.start_date), as_date(row.end_date))
            if bounds not in ((as_date(before['start_date']), as_date(before['end_date'])),
                              (as_date(target['start_date']), as_date(target['end_date']))):
                raise ValueError(f'Unexpected S3 bounds: {rid}')
        else:
            added = {c: records[rid].get(c) for c in frame.columns}
            frame = pd.concat([frame, pd.DataFrame([added])], ignore_index=True)
        mask = frame.record_id == rid
        frame.loc[mask, ['start_date', 'end_date']] = [target['start_date'], target['end_date']]
        if master:
            frame.loc[mask, ['derived_scope_start', 'derived_scope_end']] = plan['scope']
    # Unrelated records must survive byte-value-equivalent dataframe content.
    pd.testing.assert_frame_equal(
        frame.loc[~frame.record_id.isin(IDS), original.columns].reset_index(drop=True),
        original.loc[~original.record_id.isin(IDS)].reset_index(drop=True), check_dtype=False)
    return frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('bucket', 'profile', 'env-file', 'report'):
        parser.add_argument('--' + flag, required=True)
    parser.add_argument('--region', default='ap-southeast-5')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    evidence = json.loads(Path(args.report).read_text())
    if evidence['mode'] != 'PREVIEW' or evidence['documents_scanned'] != 5600 or evidence['unsupported_db_sittings']:
        raise ValueError('Expected the complete verified 5,600-document preview')
    plans = {p['record_id']: p for p in evidence['plans'] if p['record_id'] in IDS}
    if set(plans) != IDS or any(p['action'] not in ('replace', 'unchanged') or p['blockers'] for p in plans.values()):
        raise ValueError('Incomplete or blocked reviewed corrections')
    for rid, plan in plans.items():
        dates = {x['sitting_date'] for x in plan['evidence'] if x.get('status') == 'verified'}
        if not dates or (min(dates), max(dates)) != (plan['proposed']['start_date'], plan['proposed']['end_date']):
            raise ValueError(f'Missing verified endpoint evidence for {rid}')
    with psycopg2.connect(dotenv_values(args.env_file)['HANSARD_DB_URL'], connect_timeout=10) as conn:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            cur.execute('SELECT ' + ','.join('h.' + c for c in DB_FIELDS) +
                        ',a.name AS author_name FROM api_author_history h '
                        'JOIN api_author a ON a.new_author_id=h.author_id '
                        'WHERE h.record_id = ANY(%s)', (sorted(IDS),))
            names = [c[0] for c in cur.description]
            records = {r[0]: dict(zip(names, r)) for r in cur.fetchall()}
    if set(records) != IDS:
        raise ValueError('Reviewed history IDs missing from the selected DB')
    for rid, row in records.items():
        if row['author_id'] != plans[rid]['author_id'] or row['exec_posts'] != 'derived_years_mentioned':
            raise ValueError(f'DB identity/status mismatch: {rid}')
    s3 = boto3.Session(profile_name=args.profile).client('s3', region_name=args.region)
    objects, originals, outputs = {}, {}, {}
    for key in (MASTER, SEED):
        obj = s3.get_object(Bucket=args.bucket, Key=key)
        objects[key] = obj['ETag']
        originals[key] = pd.read_csv(BytesIO(obj['Body'].read()))
        outputs[key] = prepare(originals[key], records, plans, master=key == MASTER)
        print(key, len(originals[key]), '->', len(outputs[key]), 'rows', flush=True)
    for rid in sorted(IDS):
        for field in ('author_id', 'exec_posts', 'start_date', 'end_date'):
            a, b = (outputs[k].loc[outputs[k].record_id == rid, field].iloc[0] for k in (MASTER, SEED))
            if a != b:
                raise ValueError(f'Master/seed mismatch: {rid} {field}')
        print(rid, records[rid]['author_id'], '->', plans[rid]['proposed'], flush=True)
    if not args.apply:
        print('PREVIEW ONLY. No S3 or DB changes.')
        return
    for key in (MASTER, SEED):
        if not outputs[key].equals(originals[key]):
            put_csv(s3, args.bucket, key, outputs[key], objects[key])
        saved = pd.read_csv(BytesIO(s3.get_object(Bucket=args.bucket, Key=key)['Body'].read()))
        pd.testing.assert_frame_equal(saved, outputs[key], check_dtype=False)
    print('APPLIED AND VERIFIED: 15 reviewed history records in S3 master and seed. DB unchanged.')


if __name__ == '__main__':
    main()
