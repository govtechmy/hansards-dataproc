"""Read-only source validation. Missing/conflicting evidence fails closed."""
from collections import Counter
from datetime import date
from io import BytesIO
import re

import pandas as pd
from botocore.exceptions import ClientError
from hansards_pipelines.legacy_pipeline.speech_blocks import split_speaker
from hansards_pipelines.tabulate_hansard import get_author_and_speech
from speech_context import SpeechContext, speaker_prefix, can_wrap_label

MONTHS = {}
for number, names in enumerate([
    'JANUARY JANUARI', 'FEBRUARY FEBRUARI', 'MARCH MAC', 'APRIL', 'MAY MEI',
    'JUNE JUN', 'JULY JULAI', 'AUGUST OGOS', 'SEPTEMBER', 'OCTOBER OKTOBER',
    'NOVEMBER', 'DECEMBER DISEMBER'], 1):
    for name in names.split():
        MONTHS[name] = number
WORD_DATE = re.compile(r'\b(\d{1,2})(?:ST|ND|RD|TH|HB)?\s+(' + '|'.join(MONTHS) + r')\s*[.,]?\s*((?:19|20)\d{2})\b', re.I)
NUMERIC_DATE = re.compile(r'\b(?:DR|DN)\s*\.?\s*(\d{1,2})\s*[./]\s*(\d{1,2})\s*[./]\s*((?:19|20)\d{2})\b', re.I)


def normalize(text):
    return ' '.join(str(text).replace('’', "'").split())


def modern_speaker(text, house):
    """Use the modern sitting parser, including its missing-colon repairs."""
    formatting = '0' * len(text)
    author, speech, *_ = get_author_and_speech(
        text, formatting, formatting, house, is_pipeline=True)
    if author and author != 'ANNOTATION':
        return author.strip(), speech
    return None


def header_dates(texts):
    found = Counter()
    for text in texts:
        for pattern in (WORD_DATE, NUMERIC_DATE):
            for m in pattern.finditer(text):
                try:
                    month = MONTHS[m[2].upper()] if pattern is WORD_DATE else int(m[2])
                    found[str(date(int(m[3]), month, int(m[1])))] += 1
                except ValueError:
                    pass
    return dict(found)


def layout_evidence(body, contexts=None, source=None):
    frame = pd.read_csv(BytesIO(body))
    frame.columns = [str(c).strip().strip("'") for c in frame.columns]
    required = {'Text', 'Layout', 'Page number'}
    if not required.issubset(frame.columns):
        raise ValueError('Layout missing required columns')
    frame['Text'] = frame.Text.fillna('').astype(str).str.strip("'")
    headers = frame.loc[frame.Layout.astype(str).str.contains('HEADER|TITLE', case=False), 'Text']
    speakers = []
    units = []
    consumed = set()
    for index, row in frame.iterrows():
        text = normalize(row.Text)
        parsed = None if index in consumed or 'LIST' in str(row.Layout).upper() else split_speaker(text)
        joined = False
        if index not in consumed and 'LIST' not in str(row.Layout).upper() and not parsed and ':' not in text and text.count('(') > text.count(')') and len(text) < 200 and index + 1 < len(frame):
            following = frame.iloc[index + 1]
            if row['Page number'] == following['Page number'] and 'LIST' not in str(following.Layout).upper():
                parsed = split_speaker(text + ' ' + normalize(following.Text))
                joined = bool(parsed)
                if joined:
                    consumed.add(index + 1)
        ref = dict(row=int(index), pdf_page=int(row['Page number']))
        boundary = parsed or (speaker_prefix(text, allow_unknown=True) if index not in consumed and 'LIST' not in str(row.Layout).upper() else None)
        units.append(dict(text=text, kind=str(row.Layout), ref=ref, label=normalize(boundary[0]) if boundary else None))
        if parsed:
            speakers.append({'label': normalize(parsed[0]), 'row': int(index),
                             'pdf_page': int(row['Page number']), 'joined_next_row': joined})
    if contexts is not None:
        contexts.append(SpeechContext(units, source))
    return header_dates(headers), speakers


class SourceValidator:
    def __init__(self, s3, dataproc_bucket, textract_bucket, expected_objects=None):
        self.s3 = s3
        self.dataproc_bucket = dataproc_bucket
        self.textract_bucket = textract_bucket
        self.cache = {}
        self.expected_objects = None if expected_objects is None else {(obj['bucket'], obj['key']) for obj in expected_objects.values()}

    def read(self, bucket, key):
        if self.expected_objects is not None and (bucket, key) not in self.expected_objects:
            return None  # Absent from the complete source inventory snapshot.
        try:
            obj = self.s3.get_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            if exc.response['Error']['Code'] in {'NoSuchKey', '404', 'NotFound'}:
                return None
            raise  # Auth/network failures must not look like absent evidence.
        return obj['Body'].read(), {'bucket': bucket, 'key': key, 'etag': obj['ETag']}

    def document(self, document):
        if document in self.cache:
            return self.cache[document]
        match = re.fullmatch(r'(dr|dn)_(\d{4}-\d{2}-\d{2})', document)
        if not match:
            return {'status': 'unsupported_document'}
        house = 'dewanrakyat' if match[1] == 'dr' else 'dewannegara'
        expected = date.fromisoformat(match[2])
        sources, dates, speakers, lines = [], set(), [], []
        contexts = []
        raw = self.read(self.textract_bucket, f'textracted/{house}/{document}_layout.csv')
        if raw:
            ds, speakers = layout_evidence(raw[0], contexts, raw[1])
            sources.append(dict(raw[1], header_dates=ds))
            dates.update(ds)
        raw = self.read(self.dataproc_bucket, f'parsed_pdf/{house}/{expected:%d%m%Y}/plaintext.txt')
        if raw and raw[0].strip():
            lines = raw[0].decode('utf-8-sig').splitlines()
            ds = header_dates(lines[:35])
            sources.append(dict(raw[1], header_dates=ds))
            dates.update(ds)
            units = []
            consumed = set()
            for index in range(len(lines)):
                parsed = None
                furniture = bool(NUMERIC_DATE.search(lines[index]) or re.fullmatch(r'\s*\d+\s*', lines[index]))
                if index not in consumed and not furniture and lines[index].strip():
                    for length in range(1, 6):
                        if length > 1 and not can_wrap_label(lines[index]):
                            break
                        text = normalize(' '.join(lines[index:index + length]))
                        parsed = modern_speaker(text, match[1].upper())
                        if parsed:
                            speakers.append(dict(label=normalize(parsed[0]), line=index + 1,
                                                 source_key=raw[1]['key']))
                            consumed.update(range(index + 1, min(index + length, len(lines))))
                            break
                        if ':' in text:
                            break
                furniture = bool(NUMERIC_DATE.search(lines[index]) or re.fullmatch(r'\s*\d+\s*', lines[index]))
                boundary = parsed or (speaker_prefix(lines[index], allow_unknown=True) if index not in consumed and not furniture else None)
                units.append(dict(text=lines[index], kind='HEADER' if furniture else 'TEXT',
                                  ref=dict(line=index + 1), label=normalize(boundary[0]) if boundary else None))
            contexts.append(SpeechContext(units, raw[1]))
        # Filename is the authoritative sitting date. OCR header observations
        # are diagnostics only and never veto or replace that date.
        warnings = ['header_date_conflict'] if dates and dates != {str(expected)} else []
        result = dict(status='verified', sitting_date=str(expected), warnings=warnings,
                      sources=sources, speakers=speakers, lines=lines, contexts=contexts,
                      speaker_index={speaker['label']: speaker for speaker in reversed(speakers)}, suppressed=set())
        self.cache[document] = result
        return result

    def verify(self, document, label):
        doc = self.document(document)
        result = dict(document=document, status=doc['status'], sources=doc.get('sources', []))
        if result['status'] != 'verified':
            return result
        result.update(sitting_date=doc['sitting_date'], warnings=doc['warnings'])
        target = normalize(label)
        speaker = doc['speaker_index'].get(target)
        if speaker is not None:
            return dict(result, speaker=speaker)
        for context in doc['contexts']:
            ref = context.prefixes.get(target)
            if ref is not None and (context.source['key'], tuple(sorted(ref.items()))) not in doc['suppressed']:
                return dict(result, speaker=dict(ref, label=target, source_key=context.source['key']))
        return dict(result, status='unverified_speaker')

    def register(self, document, label):
        doc = self.document(document)
        for context in doc['contexts']:
            ref = context.prefixes.get(normalize(label))
            if ref is None:
                continue
            for hidden in context.register(normalize(label), ref):
                doc['suppressed'].add((context.source['key'], tuple(sorted(hidden.items()))))
        def visible(speaker):
            ref = {key: speaker[key] for key in ('row', 'pdf_page', 'line') if key in speaker}
            source_key = speaker.get('source_key')
            if source_key is None and 'row' in ref:
                source_key = next((context.source['key'] for context in doc['contexts'] if context.source['key'].endswith('_layout.csv')), None)
            return (source_key, tuple(sorted(ref.items()))) not in doc['suppressed']
        doc['speakers'][:] = [speaker for speaker in doc['speakers'] if visible(speaker)]
        doc['speaker_index'] = {speaker['label']: speaker for speaker in reversed(doc['speakers'])}

    def classify(self, document, text):
        doc = self.document(document)
        matches = [context.classify(text) for context in doc.get('contexts', [])]
        matches = [match for match in matches if match is not None]
        if not matches:
            return None
        signatures = {(match['classification'], tuple(match['labels']), match.get('starts_in_label')) for match in matches}
        if len(signatures) != 1:
            return None
        return matches[0]
