"""Rebuild observed author-history periods from saved S3 speech evidence.

Preview by default. See README.md for coverage rules and invocation.
No OCR, DB updates, or direct speech relinking.
"""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict, Counter
from datetime import date
from io import BytesIO
from pathlib import Path
import re
import sys

import pandas as pd
import boto3
from botocore.config import Config
import psycopg2
from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'hansards_pipelines'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from s3_csv import put_csv
from source_evidence import SourceValidator
from hansards_pipelines.author_matching import normalize_malaysian_name

DERIVED = 'derived_years_mentioned'


def name_key(name):
    normalized = normalize_malaysian_name(name)
    return ' '.join(w for w in re.findall(r'[^\W\d_]+', normalized) if w not in {'BIN', 'BINTI', 'IBNI'})


def appearance_dates(documents):
    dates = set()
    for document in str(documents).split(','):
        match = re.fullmatch(r'(?:dr|dn|kkdr)_(\d{4}-\d{2}-\d{2})(?:\.json)?', document.strip())
        if match:
            dates.add(date.fromisoformat(match[1]))
    return dates


def derive_ranges(frame, authors, candidate_authors=(), validator=None, evidence=None):
    """Require an unambiguous normalized name; never use derived history dates."""
    if validator is None:
        raise ValueError('Source validation is required; filename dates alone are not evidence')
    evidence = evidence if evidence is not None else []
    lookup = defaultdict(set)
    birth_years = {}
    for author_id, name, birth_year in authors:
        lookup[name_key(name)].add(author_id)
        birth_years[author_id] = birth_year
    # DB can contain identities missing from the S3 master. Include those names
    # in ambiguity detection without silently adding DB-only authors to S3.
    for author_id, name, _ in candidate_authors:
        lookup[name_key(name)].add(author_id)
    observed = defaultdict(set)
    skipped = Counter()
    for row in frame.to_dict('records'):
        label = str(row.get('author', '')).strip()
        dates = appearance_dates(row.get('documents_list', ''))
        if not dates:
            skipped['no_valid_document_dates'] += 1
            continue
        # A role label may contain the actual person's name in parentheses.
        keys = [name_key(label)] + [name_key(s) for s in re.findall(r'\(([^()]*)\)', label)]
        candidates = set().union(*(lookup.get(k, set()) for k in keys))
        if len(candidates) != 1:
            skipped['ambiguous' if candidates else 'unmatched'] += 1
            continue
        author_id = next(iter(candidates))
        if author_id not in birth_years:
            skipped['missing_from_author_master'] += 1
            continue
        birth_year = birth_years[author_id]
        # Reject an entire label with impossible observations, not just its
        # inconvenient early dates. No guessed minimum speaking age.
        if any(d > date.today() or (birth_year is not None and d.year <= birth_year) for d in dates):
            skipped['impossible_dates'] += 1
            continue
        for document in str(row.get('documents_list', '')).split(','):
            document = document.strip().removesuffix('.json')
            if not re.fullmatch(r'(?:dr|dn|kkdr)_\d{4}-\d{2}-\d{2}', document):
                continue
            decision = validator.verify(document, label)
            decision.update(author_id=author_id, export_label=label)
            evidence.append(decision)
            if decision['status'] == 'verified':
                observed[author_id].add(date.fromisoformat(document.split('_', 1)[1]))
            else:
                skipped[decision['status']] += 1
    return {a: (min(ds), max(ds)) for a, ds in observed.items()}, skipped


def load_frame(source, profile, region='ap-southeast-5'):
    if source.startswith('s3://'):
        import boto3
        bucket, key = source[5:].split('/', 1)
        body = boto3.Session(profile_name=profile).client('s3', region_name=region).get_object(Bucket=bucket, Key=key)['Body'].read()
        stream = BytesIO(body)
    else:
        stream = source
    frame = pd.read_excel(stream) if source.lower().endswith('.xlsx') else pd.read_csv(stream)
    if not {'author', 'documents_list'}.issubset(frame.columns):
        raise ValueError('Input must contain author and documents_list columns; years_appeared alone is insufficient')
    return frame


def sitting_document(filename):
    """Recognise document prefixes without mistaking KKDR for DR."""
    value = str(filename).lower()
    match = re.search(r'(?<![a-z0-9])((?:kkdr|dr|dn)_\d{4}-\d{2}-\d{2})(?![\d])', value)
    if match:
        return match[1]
    old = re.search(r'(?<![a-z0-9])(kkdr|dr|dn)-(\d{2})(\d{2})(\d{4})(?!\d)', value)
    if old:
        return f'{old[1]}_{old[4]}-{old[3]}-{old[2]}'
    return None


def main():
    from rebuild_ranges import inventory, scan_document, rebuild, IdentityIndex, as_date
    from pipeline_identity import PipelineIdentityIndex
    parser = argparse.ArgumentParser(description=(
        'Rebuild existing derived author-history periods from saved speech CSVs '
        'and raw text. Preview by default; never writes the DB or runs OCR.'))
    parser.add_argument('--profile')
    parser.add_argument('--region', default='ap-southeast-5')
    parser.add_argument('--bucket', required=True, help='Canonical master and parsed-text bucket')
    parser.add_argument('--speech-bucket', required=True, help='Bucket containing saved sitting speech CSVs')
    parser.add_argument('--textract-bucket', required=True)
    parser.add_argument('--env-file', required=True, help='Read-only DB identity and sitting inventory checks')
    parser.add_argument('--report', required=True, help='Local JSON evidence and proposed-history report')
    parser.add_argument('--author-ids', nargs='+', type=int, help='Audit only these authors; otherwise all derived histories')
    parser.add_argument('--documents', nargs='+', help='Restricted preview only; blocks all corrections')
    parser.add_argument('--workers', type=int, default=8, help='Parallel document reads (1–16)')
    parser.add_argument('--apply', action='store_true', help='Write eligible S3 master corrections only')
    args = parser.parse_args()
    if not 1 <= args.workers <= 16:
        parser.error('--workers must be between 1 and 16')
    if args.apply and args.documents:
        parser.error('--documents is preview-only')
    s3 = boto3.Session(profile_name=args.profile).client(
        's3', region_name=args.region, config=Config(max_pool_connections=max(10, args.workers * 2)))
    author_obj = s3.get_object(Bucket=args.bucket, Key='canonical/master/author.csv')
    authors = pd.read_csv(BytesIO(author_obj['Body'].read()))
    history_obj = s3.get_object(Bucket=args.bucket, Key='canonical/master/author_history.csv')
    history = pd.read_csv(BytesIO(history_obj['Body'].read()))
    with psycopg2.connect(dotenv_values(args.env_file)['HANSARD_DB_URL'], connect_timeout=10) as conn:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            cur.execute('SELECT record_id,author_id FROM api_author_history')
            db_ids = dict(cur.fetchall())
            cur.execute('SELECT new_author_id,name,birth_year FROM api_author')
            db_authors = cur.fetchall()
            cur.execute('SELECT filename,date FROM api_sitting')
            db_sittings = cur.fetchall()
    for row in history.itertuples():
        if pd.isna(row.record_id) or pd.isna(row.author_id):
            raise ValueError('Resolve missing author/history IDs in the S3 master first')
        if int(row.record_id) in db_ids and db_ids[int(row.record_id)] != int(row.author_id):
            raise ValueError(f'S3 history ID {row.record_id} belongs to a different author in DB')
    records = [(int(r.new_author_id), r.name, None if pd.isna(r.birth_year) else int(r.birth_year)) for r in authors.itertuples()]
    selected = set(args.author_ids or [])
    if selected - {r[0] for r in records}:
        raise ValueError('Selected author missing from S3 author master')
    known_docs, unsupported_sittings = set(), []
    for filename, sitting_date in db_sittings:
        document = sitting_document(filename)
        if document and document.startswith('kkdr_'):
            continue  # Committee documents are outside this DR/DN inventory.
        if document:
            known_docs.add(document)
        else:
            unsupported_sittings.append(dict(filename=filename, date=str(sitting_date)))
    validator = SourceValidator(s3, args.bucket, args.textract_bucket)
    docs = inventory(s3, args.speech_bucket, validator, known_docs)
    target_history = history[history.exec_posts.isin([DERIVED, 'unverified_derived_years_mentioned'])]
    if selected:
        target_history = target_history[target_history.author_id.isin(selected)]
    scopes = [(as_date(getattr(r, 'derived_scope_start', None)) or as_date(r.start_date),
               as_date(getattr(r, 'derived_scope_end', None)) or as_date(r.end_date) or date.today())
              for r in target_history.itertuples()]
    wanted = [doc for doc in docs if any(start and start <= date.fromisoformat(doc.split('_', 1)[1]) <= end
                                         for start, end in scopes)]
    if args.documents:
        unknown = set(args.documents) - set(docs)
        if unknown:
            raise ValueError(f'Documents absent from source inventory: {sorted(unknown)}')
        wanted = [doc for doc in wanted if doc in set(args.documents)]
    identities = PipelineIdentityIndex(records, db_authors, history=history)
    scans = {}
    def scan_one(doc):
        # Boto3 clients may be shared across threads; document caches may not.
        reader = SourceValidator(s3, args.bucket, args.textract_bucket, expected_objects=docs[doc])
        appearances, issues = scan_document(doc, docs[doc], reader, identities)
        if selected:
            appearances = [a for a in appearances if a['author_id'] in selected]
            issues = [dict(issue, possible_author_ids=sorted(selected & set(issue.get('possible_author_ids', []))))
                      for issue in issues if issue.get('informational') or issue.get('blocks_all') or selected & set(issue.get('possible_author_ids', []))]
        return appearances, issues
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        pending = {executor.submit(scan_one, doc): doc for doc in wanted}
        try:
            for index, future in enumerate(as_completed(pending), 1):
                doc = pending[future]
                try:
                    scans[doc] = future.result()
                except Exception:
                    print(f'Scan failed for {doc}', flush=True)
                    raise
                if index == 1 or index % 25 == 0 or index == len(wanted):
                    print(f'Scanned {index}/{len(wanted)} documents', flush=True)
        except BaseException:
            for future in pending:
                future.cancel()
            raise
    # Unknown sitting filenames prevent a claim of complete source coverage.
    revised, plans = rebuild(history, docs, scans, selected,
                             partial=bool(args.documents or unsupported_sittings), observed_only=True)
    counts = Counter(plan['action'] for plan in plans)
    report = dict(mode='APPLY' if args.apply else 'PREVIEW', summary=dict(counts),
                  author_master_etag=author_obj['ETag'], history_master_etag=history_obj['ETag'],
                  source_inventory=docs, unsupported_db_sittings=unsupported_sittings,
                  documents_scanned=len(scans), plans=plans,
                  scan_summary=dict(Counter(issue['status'] for _, issues in scans.values() for issue in issues)),
                  scope_definition='Each original derived period; persisted audit bounds prevent progressive shrinking.',
                  proposed_history=json.loads(revised.to_json(orient='records')))
    Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print('SUMMARY:', dict(counts), 'REPORT:', args.report)
    if args.apply and any(plan['action'] != 'review' for plan in plans):
        # Fail if any input version or document inventory changed during the run.
        if s3.head_object(Bucket=args.bucket, Key='canonical/master/author.csv')['ETag'] != author_obj['ETag']:
            raise ValueError('Author master changed during scan; rerun preview')
        if inventory(s3, args.speech_bucket, validator, known_docs) != docs:
            raise ValueError('Source inventory changed during scan; rerun preview')
        if not history.equals(revised):
            put_csv(s3, args.bucket, 'canonical/master/author_history.csv', revised, history_obj['ETag'])
            print('Updated S3 master only. Prepare/load the author-history seed through the normal pipeline. DB unchanged.')


if __name__ == '__main__':
    main()
