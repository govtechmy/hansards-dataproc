"""Rebuild derived history periods from a versioned inventory of saved speeches.

Old ranges define the period being audited, never proof of an appearance.
Their original scope is persisted so reruns do not progressively narrow the scan.
The CLI uses confirmed appearances, retaining unresolved turns separately.
Missing sources and incomplete scans still prevent replacement.
"""
from collections import defaultdict
from datetime import date
from io import BytesIO
from functools import lru_cache
import re

import pandas as pd

from hansards_pipelines.author_matching import normalize_malaysian_name
from hansards_pipelines.utils.author_history_utils import UNVERIFIED_DERIVED
from source_evidence import normalize
from speech_context import non_individual, prose_label, ROLE

DERIVED = 'derived_years_mentioned'
SCOPE_START = 'derived_scope_start'
SCOPE_END = 'derived_scope_end'
DOCUMENT = re.compile(r'(dr|dn)_(\d{4}-\d{2}-\d{2})')


@lru_cache(maxsize=100000)
def name_key(label):
    value = normalize_malaysian_name(label)
    return ' '.join(token for token in re.findall(r'[^\W\d_]+', value)
                    if token not in {'BIN', 'BINTI', 'IBNI'})


def person_keys(label):
    # A personal label may end in a seat descriptor, e.g. Name [Pasir Salak].
    # A role label instead encloses the person's name, e.g. Minister [Name].
    # Strip descriptors; never use constituency data to decide identity.
    outer = re.sub(r'\([^()]*\)|\[[^\[\]]*\]', '', str(label)).strip()
    if ROLE.search(outer):
        return {name_key(part) for pair in re.findall(r'\(([^()]*)\)|\[([^\[\]]*)\]', str(label))
                for part in pair if part}
    return {name_key(outer)}


class IdentityIndex:
    def __init__(self, authors, other_authors=(), history=None):
        self.owners = defaultdict(set)
        self.births = {}
        self.tokens = defaultdict(set)
        self.abbreviations = defaultdict(list)
        self.prefixes = defaultdict(set)
        self.service_periods = defaultdict(list)
        for author_id, name, birth in [*authors, *other_authors]:
            self.owners[name_key(name)].add(int(author_id))
        for author_id, name, birth in authors:
            self.births[int(author_id)] = birth
        for key, owners in self.owners.items():
            parts = key.split()
            for length in range(2, len(parts)):
                self.prefixes[' '.join(parts[:length])].update(owners)
            for token in parts:
                self.tokens[token].update(owners)
            if parts and parts[0] in {'MOHD', 'MOHAMED', 'MOHAMAD', 'MOHAMMAD', 'MUHAMMAD', 'MUHAMAD'}:
                self.abbreviations[tuple(parts[1:])].append((parts[0], owners))
        if history is not None:
            for row in history.to_dict('records'):
                if row.get('exec_posts') in {DERIVED, UNVERIFIED_DERIVED}:
                    continue
                start, end = as_date(row.get('start_date')), as_date(row.get('end_date'))
                if start is None:
                    continue
                if end is not None and end < start:
                    raise ValueError(f'Invalid independent history period: {row["record_id"]}')
                self.service_periods[int(row['author_id'])].append(
                    (start, end or date.max, int(row['record_id'])))

    @lru_cache(maxsize=100000)
    def resolve(self, label, sitting=None):
        keys = person_keys(label)
        matches = set().union(*(self.owners.get(key, set()) for key in keys))
        # MOHD is an abbreviation, not permission to drop remaining tokens.
        variants = {'MOHD', 'MOHAMED', 'MOHAMAD', 'MOHAMMAD', 'MUHAMMAD', 'MUHAMAD'}
        for key in keys:
            parts = key.split()
            if len(parts) < 2 or parts[0] not in variants:
                continue
            alternatives = self.abbreviations.get(tuple(parts[1:]), [])
            if parts[0] == 'MOHD' or any(first == 'MOHD' for first, _ in alternatives):
                for _, ids in alternatives:
                    matches.update(ids)
        if sitting is None or len(matches) == 1:
            return matches
        # An omitted trailing name can be resolved by independent service
        # evidence. Anchor at the person's first name: a father's name inside
        # the son's patronymic is never an abbreviated name for the son.
        candidates = matches or set().union(*(self.prefixes.get(key, set()) for key in keys))
        active = {owner for owner in candidates
                  if any(start <= sitting <= end for start, end, _ in self.service_periods[owner])}
        return active or matches

    def history_support(self, label, sitting, owner):
        """Expose the independent records used for date-assisted resolution."""
        if len(self.resolve(label)) == 1:
            return []
        return [record for start, end, record in self.service_periods[owner]
                if start <= sitting <= end]

    @lru_cache(maxsize=100000)
    def possible(self, label):
        """Unresolved overlapping names block correction; they never assign it."""
        tokens = set().union(*(set(key.split()) for key in person_keys(label)))
        return set().union(*(self.tokens.get(token, set()) for token in tokens))


def as_date(value):
    if pd.isna(value) or not str(value).strip():
        return None
    value = str(value)
    return pd.to_datetime(value, dayfirst=not bool(re.match(r'^\d{4}-', value)), errors='raise').date()


def inventory(s3, speech_bucket, validator, extra_documents=()):
    """Union speech CSVs, raw sources, and known DB sittings; retain ETags."""
    docs = {}
    configs = [(speech_bucket, 'dewanrakyat/', 'speech'), (speech_bucket, 'dewannegara/', 'speech'),
               (validator.textract_bucket, 'textracted/', 'layout'),
               (validator.dataproc_bucket, 'parsed_pdf/', 'plaintext')]
    for bucket, prefix, kind in configs:
        for page in s3.get_paginator('list_objects_v2').paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get('Contents', []):
                key = obj['Key']
                match = re.fullmatch(r'(dewanrakyat|dewannegara)/(dr|dn)_(\d{4}-\d{2}-\d{2})\.csv', key) if kind == 'speech' else None
                if match:
                    doc = f'{match[2]}_{match[3]}'
                elif kind == 'layout':
                    m = re.fullmatch(r'textracted/(dewanrakyat|dewannegara)/((?:dr|dn)_\d{4}-\d{2}-\d{2})_layout\.csv', key)
                    if not m:
                        continue
                    doc = m[2]
                elif kind == 'plaintext':
                    m = re.fullmatch(r'parsed_pdf/(dewanrakyat|dewannegara)/(\d{2})(\d{2})(\d{4})/plaintext\.txt', key)
                    if not m:
                        continue
                    doc = f'{"dr" if m[1] == "dewanrakyat" else "dn"}_{m[4]}-{m[3]}-{m[2]}'
                else:
                    continue
                date.fromisoformat(doc.split('_', 1)[1])
                docs.setdefault(doc, {})[kind] = dict(bucket=bucket, key=key, etag=obj['ETag'])
    for doc in extra_documents:
        if DOCUMENT.fullmatch(doc):
            docs.setdefault(doc, {})
    return dict(sorted(docs.items()))


def scan_document(document, objects, validator, identities):
    """Return accepted appearances and blockers with source/row references."""
    appearances, issues = [], []
    sitting = date.fromisoformat(document.split('_', 1)[1])
    observed = validator.document(document)
    if not observed.get('sources'):
        return [], [dict(status='missing_raw_source', blocks_all=True)]
    for source in observed['sources']:
        kind = 'layout' if source['key'].endswith('_layout.csv') else 'plaintext'
        expected = objects.get(kind)
        if expected is None or source['etag'] != expected['etag']:
            raise ValueError(f'Source inventory changed while scanning {document}: {source["key"]}')
    speech = objects.get('speech')
    labels = {}

    def recover(text, row_ref, claimed_label=None):
        match = validator.classify(document, text)
        if match is None:
            return False
        classification = match['classification']
        if classification in {'non_speech', 'written_question'}:
            issues.append(dict(status=classification, informational=True, blocks_all=False,
                               source_match=match, **row_ref))
            return True
        if claimed_label is not None and not prose_label(claimed_label) and not match.get('starts_in_label'):
            return False  # A claimed new speaker cannot inherit the previous speaker.
        resolved = set()
        unresolved = []
        for label in match['labels']:
            owners = identities.resolve(label, sitting)
            if non_individual(label) and not owners:
                continue
            if len(owners) != 1:
                possible = owners | identities.possible(label)
                unresolved.append(dict(status='ambiguous_identity' if len(owners) > 1 else 'unresolved_identity',
                                       label=label, source_match=match, possible_author_ids=sorted(possible),
                                       blocks_all=not bool(possible), **row_ref))
            else:
                resolved.update(owners)
        if unresolved:
            issues.extend(unresolved)
            return True  # The source context, rather than a missing-row label, is the blocker.
        for author_id in sorted(resolved):
            birth = identities.births.get(author_id)
            if author_id not in identities.births or sitting > date.today() or (birth is not None and sitting.year <= birth):
                issues.append(dict(status='invalid_author_or_date', possible_author_ids=[author_id],
                                   blocks_all=False, source_match=match, **row_ref))
                continue
            appearances.append(dict(status='verified', verification='full_source_span', document=document,
                                    author_id=author_id, sitting_date=str(sitting), source_match=match,
                                    identity_history_ids=sorted({record for label in match['labels']
                                        if author_id in identities.resolve(label, sitting)
                                        for record in identities.history_support(label, sitting, author_id)}), **row_ref))
        issues.append(dict(status='source_continuation' if resolved else 'non_individual_speech',
                           informational=True, blocks_all=False, source_match=match, **row_ref))
        return True

    if speech:
        data, source = validator.read(speech['bucket'], speech['key'])
        if source['etag'] != speech['etag']:
            raise ValueError(f'Speech CSV changed while scanning {document}')
        frame = pd.read_csv(BytesIO(data))
        if not {'author', 'speech'}.issubset(frame.columns):
            return [], [dict(status='invalid_speech_csv', blocks_all=True)]
        if hasattr(identities, 'prime'):
            identities.prime(
                {label for label in frame.author.dropna().map(normalize)
                 if validator.verify(document, label)['status'] == 'verified'}
                | {speaker['label'] for speaker in observed.get('speakers', [])}, sitting)
        # Register independently verified complete prefixes before resolving
        # any blank rows. Longer full labels suppress wrapped suffix fragments.
        for label in sorted(set(frame.author.dropna().map(normalize)), key=len, reverse=True):
            if len(identities.resolve(label, sitting)) == 1 and validator.verify(document, label)['status'] == 'verified':
                validator.register(document, label)
        for index, row in frame.iterrows():
            if pd.isna(row.author):
                if pd.notna(row.speech) and str(row.speech).strip():
                    ref = dict(speech_row=int(index), speech_source=source)
                    if not recover(str(row.speech), ref):
                        issues.append(dict(status='missing_speaker', blocks_all=True, **ref))
                continue
            label = normalize(row.author)
            if label and label != 'ANNOTATION':
                ref = dict(speech_row=int(index), speech_source=source)
                verified = validator.verify(document, label)
                owners = identities.resolve(label, sitting) if verified['status'] == 'verified' else identities.resolve(label)
                if verified['status'] != 'verified' or not owners:
                    text = label + ': ' + ('' if pd.isna(row.speech) else str(row.speech))
                    if recover(text, ref, claimed_label=label):
                        continue
                labels.setdefault(label, ref)
    else:
        issues.append(dict(status='missing_speech_csv', blocks_all=True))
    # Recover full labels missed or truncated by the old parser too.
    for speaker in observed.get('speakers', []):
        labels.setdefault(speaker['label'], {})
    for label, row_ref in labels.items():
        decision = validator.verify(document, label)
        owners = identities.resolve(label, sitting) if decision['status'] == 'verified' else identities.resolve(label)
        decision.update(label=label, **row_ref)
        if decision['status'] != 'verified' or len(owners) != 1:
            possible = owners | identities.possible(label)
            # Chair labels alone do not identify a person; unresolved minister
            # roles or malformed labels may belong to anyone and block shrink.
            if non_individual(label) and not owners:
                continue
            decision.update(status='ambiguous_identity' if len(owners) > 1 else
                            ('unresolved_identity' if not owners else decision['status']),
                            possible_author_ids=sorted(possible), blocks_all=not bool(possible))
            issues.append(decision)
            continue
        author_id = next(iter(owners))
        birth = identities.births.get(author_id)
        if author_id not in identities.births or sitting > date.today() or (birth is not None and sitting.year <= birth):
            issues.append(dict(decision, status='invalid_author_or_date', possible_author_ids=[author_id], blocks_all=False))
            continue
        appearances.append(dict(decision, author_id=author_id, sitting_date=str(sitting),
                                identity_history_ids=identities.history_support(label, sitting, author_id)))
    return appearances, issues


def rebuild(history, documents, scans, author_ids=None, partial=False, observed_only=False):
    """Replace each audited period, preserving IDs and all researched roles.

    In observed-only mode zero appearances retain the existing row for review;
    unresolved turns are diagnostic, never assigned to a person. The strict
    mode additionally requires all identity uncertainty to be resolved.
    Scope columns keep the same audit on reruns.
    """
    result = history.copy()
    if result.record_id.isna().any() or result.record_id.duplicated().any():
        raise ValueError('Missing or duplicate history IDs')
    for column in (SCOPE_START, SCOPE_END):
        if column not in result:
            result[column] = None
    plans = []
    for index, row in result.iterrows():
        author_id = int(row.author_id)
        if row.exec_posts not in {DERIVED, UNVERIFIED_DERIVED} or (author_ids and author_id not in author_ids):
            continue
        start = as_date(row[SCOPE_START]) or as_date(row.start_date)
        end = as_date(row[SCOPE_END]) or as_date(row.end_date) or date.today()
        if start is None or end < start:
            raise ValueError(f'Invalid history scope: {row.record_id}')
        relevant = [doc for doc in documents if start <= date.fromisoformat(doc.split('_', 1)[1]) <= end]
        blockers, accepted = [], []
        if partial:
            blockers.append(dict(status='partial_preview'))
        if not relevant:
            blockers.append(dict(status='no_documents_in_scope'))
        for doc in relevant:
            if doc not in scans:
                blockers.append(dict(document=doc, status='not_scanned'))
                continue
            appearances, issues = scans[doc]
            accepted.extend(a for a in appearances if a['author_id'] == author_id)
            blockers.extend(dict(issue, document=doc) for issue in issues
                            if issue.get('blocks_all') or author_id in issue.get('possible_author_ids', []))
        dates = sorted({a['sitting_date'] for a in accepted})
        identity_issues = []
        if observed_only:
            coverage_statuses = {'not_scanned', 'missing_raw_source', 'missing_speech_csv',
                                 'invalid_speech_csv', 'partial_preview', 'no_documents_in_scope'}
            identity_issues = [b for b in blockers if b['status'] not in coverage_statuses]
            blockers = [b for b in blockers if b['status'] in coverage_statuses]
            if not dates:
                blockers.append(dict(status='no_confirmed_appearances'))
        # An unresolved turn inside already confirmed bounds cannot change
        # either endpoint. Keep it in the report, but do not require identity
        # resolution for every intervening speaker to derive first/last dates.
        interior_issues = []
        if dates:
            endpoint_blockers = []
            for issue in blockers:
                doc = issue.get('document')
                coverage_error = issue['status'] in {
                    'not_scanned', 'missing_raw_source', 'missing_speech_csv', 'invalid_speech_csv',
                }
                if not coverage_error and doc and dates[0] <= doc.split('_', 1)[1] <= dates[-1]:
                    interior_issues.append(issue)
                else:
                    endpoint_blockers.append(issue)
            blockers = endpoint_blockers
        proposed = dict(start_date=dates[0], end_date=dates[-1], exec_posts=DERIVED) if dates else dict(
            start_date=str(as_date(row.start_date)), end_date=str(as_date(row.end_date)) if as_date(row.end_date) else None,
            exec_posts=UNVERIFIED_DERIVED)
        old = dict(start_date=str(as_date(row.start_date)), end_date=str(as_date(row.end_date)) if as_date(row.end_date) else None,
                   exec_posts=row.exec_posts)
        if observed_only and not dates:
            proposed = dict(old)
        plan = dict(record_id=int(row.record_id), author_id=author_id, scope=[str(start), str(end)],
                    documents_checked=len(relevant), before=old, proposed=proposed,
                    evidence=accepted, blockers=blockers, interior_issues=interior_issues,
                    identity_issues=identity_issues,
                    action='review' if blockers else ('replace' if old != proposed else 'unchanged'))
        plans.append(plan)
        if not blockers:
            result.loc[index, SCOPE_START] = str(start)
            result.loc[index, SCOPE_END] = str(end)
            for column, value in proposed.items():
                result.loc[index, column] = (date.fromisoformat(value).strftime('%d/%m/%Y') if value and column != 'exec_posts' else value)
    return result, plans
