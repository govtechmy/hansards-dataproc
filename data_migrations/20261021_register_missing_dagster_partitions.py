"""One-time additive transfer of sitting partition keys between Dagster DBs.

Preview is read-only. --apply uses Dagster's API to add only missing keys with
existing target S3 PDFs. Never restores a DB, starts runs, changes sensor state,
deletes partitions, copies run history, or connects to HANSARD_DB_URL.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory

DEFINITIONS = ('house_sittings', 'house_sittings_legacy')
FOLDERS = {'DR': 'dewanrakyat', 'DN': 'dewannegara', 'KKDR': 'kamarkhas'}


def pdf_key(partition):
    match = re.fullmatch(r'(DR|DN|KKDR)-(\d{8})', partition)
    if not match:
        raise ValueError('Expected DR/DN/KKDR-DDMMYYYY')
    house, raw_date = match.groups()
    day = datetime.strptime(raw_date, '%d%m%Y')
    return f'{FOLDERS[house]}/{house.lower()}_{day:%Y-%m-%d}.pdf'


def plan_partitions(source, target, available_pdfs):
    plans = {}
    for name in DEFINITIONS:
        source_keys, target_keys = set(source.get(name, [])), set(target.get(name, []))
        ready, missing_pdf, invalid = [], [], []
        for partition in sorted(source_keys - target_keys):
            try:
                key = pdf_key(partition)
            except ValueError:
                invalid.append(partition)
                continue
            (ready if key in available_pdfs else missing_pdf).append(partition)
        plans[name] = dict(source_count=len(source_keys), target_count=len(target_keys),
                           add=ready, missing_pdf=missing_pdf, invalid=invalid,
                           target_only=sorted(target_keys-source_keys))
    return plans


def read_partitions(url):
    import psycopg2
    with psycopg2.connect(url.replace('postgresql+psycopg2://', 'postgresql://'),
                          connect_timeout=10) as conn:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout='60s'")
            cur.execute('SELECT current_database(),inet_server_addr()::text,inet_server_port()')
            identity = cur.fetchone()
            cur.execute('SELECT partitions_def_name,partition FROM dynamic_partitions '
                        'WHERE partitions_def_name = ANY(%s)', (list(DEFINITIONS),))
            groups = {name: [] for name in DEFINITIONS}
            for name, key in cur.fetchall():
                groups[name].append(key)
    return identity, groups


def register(instance, plans):
    results = {}
    for name in DEFINITIONS:
        before = set(instance.get_dynamic_partitions(name))
        additions = sorted(set(plans[name]['add']) - before)
        if additions:
            instance.add_dynamic_partitions(name, additions)
        after = set(instance.get_dynamic_partitions(name))
        if not before.issubset(after) or not set(plans[name]['add']).issubset(after):
            raise RuntimeError(f'Partition verification failed: {name}')
        results[name] = dict(added=len(additions), total=len(after))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-env-file', required=True)
    parser.add_argument('--target-env-file', required=True)
    parser.add_argument('--target-bucket', required=True, help='Target public PDF bucket')
    parser.add_argument('--profile', required=True)
    parser.add_argument('--region', default='ap-southeast-5')
    parser.add_argument('--report', type=Path, help='Optional local JSON plan')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    # Keep imports inside main so offline tests never load AWS or DB settings.
    import boto3
    from dotenv import dotenv_values
    source_config, target_config = map(dotenv_values, (args.source_env_file, args.target_env_file))
    source_url, target_url = (cfg.get('DAGSTER_DB_URL') for cfg in (source_config, target_config))
    if not source_url or not target_url:
        raise ValueError('DAGSTER_DB_URL required in both selected env files')
    if source_url == target_url:
        raise ValueError('Source and target Dagster DB URLs must differ')
    if args.target_bucket != target_config.get('S3_PUBLIC_BUCKET'):
        raise ValueError('Target PDF bucket must match target env S3_PUBLIC_BUCKET')
    source_identity, source = read_partitions(source_url)
    target_identity, target = read_partitions(target_url)
    if source_identity == target_identity:
        raise ValueError('Source and target resolve to the same Dagster DB')
    s3 = boto3.Session(profile_name=args.profile).client('s3', region_name=args.region)
    available = set()
    for folder in FOLDERS.values():
        for page in s3.get_paginator('list_objects_v2').paginate(
                Bucket=args.target_bucket, Prefix=folder + '/'):
            available.update(obj['Key'] for obj in page.get('Contents', [])
                             if obj['Key'].endswith('.pdf'))
    plans = plan_partitions(source, target, available)
    report = dict(mode='APPLY' if args.apply else 'PREVIEW', target_bucket=args.target_bucket,
                  partitions=plans)
    for name, plan in plans.items():
        print(name, 'source:', plan['source_count'], 'target:', plan['target_count'],
              'add:', len(plan['add']), 'missing PDFs:', len(plan['missing_pdf']),
              'invalid keys:', len(plan['invalid']), 'preserve target-only:', len(plan['target_only']))
    if args.apply:
        from dagster import DagsterInstance
        old_url = os.environ.get('DAGSTER_DB_URL')
        try:
            os.environ['DAGSTER_DB_URL'] = target_url
            with TemporaryDirectory(prefix='dagster-partition-migration-') as directory:
                Path(directory, 'dagster.yaml').write_text(
                    'storage:\n  postgres:\n    postgres_url:\n      env: DAGSTER_DB_URL\n'
                    'telemetry:\n  enabled: false\n')
                with DagsterInstance.from_config(directory) as instance:
                    report['results'] = register(instance, plans)
            print('Registered and verified:', report['results'])
        finally:
            if old_url is None:
                os.environ.pop('DAGSTER_DB_URL', None)
            else:
                os.environ['DAGSTER_DB_URL'] = old_url
    else:
        print('PREVIEW ONLY. No remote writes.')
    if args.report:
        args.report.write_text(json.dumps(report, indent=2))
    print('No ingestion jobs launched. No Hansard DB changes.')


if __name__ == '__main__':
    main()
