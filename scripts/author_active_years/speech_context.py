"""Attribute saved CSV text only when its complete span agrees with raw source.

CSV row order is never evidence of a continuing speaker. Unknown speaker/section
boundaries reset context. Text normalization is for alignment, not name matching.
"""
from bisect import bisect_left, bisect_right
import re

from hansards_pipelines.legacy_pipeline.speech_blocks import split_speaker


CHAIR = re.compile(r'(?:The )?(?:Mr\.? )?(?:Speaker|President|Chairman)|(?:Tuan |Puan )?(?:Yang di-Pertua|Pengerusi)|Timbalan Yang di-Pertua', re.I)
GROUP = re.compile(r'(?:Some |Several )?Hon(?:ou?rable|\.)? Members|Beberapa (?:orang )?Ahli|Ahli-ahli(?: Yang Berhormat)?|Members|Voices', re.I)
HEADINGS = re.compile(r'(?:PRAYERS(?: MR SPEAKER IN THE CHAIR)?|DOA|ORAL ANSWERS TO QUESTIONS|JAWAPAN JAWAPAN LISAN BAGI PERTANYAAN PERTANYAAN|PERTANYAAN PERTANYAAN BAGI JAWAB LISAN|PERTANYAAN BAGI JAWAB LISAN|WRITTEN ANSWERS TO QUESTIONS|JAWAPAN JAWAPAN BERTULIS|BILLS|RANG UNDANG UNDANG|USUL USUL|MOTIONS)', re.I)
QUESTION = re.compile(r'^\d+\s+(?:TUAN|PUAN|DATUK|DATO|DR|ENCHE|ENCIK|MR|MRS|SIR|TAN|RAJA|TENGKU|HAJI)\b.{1,350}?\b(?:MINTA|MEMINTA|BERTANYA|ASKS|ASKED|TO ASK)\b', re.I)
CEREMONY = re.compile(r'(?:TUAN |PUAN )?YANG DIPERTUA MEM PENGERUSIKAN MESYUARAT|(?:TUAN |PUAN )?YANG DIPERTUA MEMPENGERUSIKAN MESYUARAT|MR SPEAKER IN THE CHAIR|MR PRESIDENT IN THE CHAIR|MESYUARAT DITANGGUHKAN.*', re.I)
ROLE = re.compile(r'\b(?:Minister|Menteri|Setiausaha|Secretary|Speaker|President|Chairman|Pengerusi|Pertua|Clerk)\b', re.I)


def words(text):
    # OCR and CSV differ in wrapping, Markdown and word-breaking hyphens.
    # Require the entire resulting token sequence, never just start/end anchors.
    text = re.sub(r'(?<=\w)-\s*(?=\w)', '', str(text))
    return ' '.join(re.findall(r'\w+', text.casefold()))


def non_individual(label):
    # Printed optional titles do not identify an individual speaker.
    label = re.sub(r'\((Timbalan|Deputy)\)', r'\1', str(label), flags=re.I).strip()
    label = re.sub(r'^Tuan Timbalan ', 'Timbalan ', label, flags=re.I)
    return bool(CHAIR.fullmatch(label) or GROUP.fullmatch(label))


def written_question(text):
    return bool(QUESTION.search(words(text)))


def non_speech_text(text):
    token_text = words(text)
    # Hyphen joining is solely an alignment operation. Account for joined
    # tokens in explicit fixed headings as well as their spaced form.
    return bool(HEADINGS.fullmatch(token_text) or CEREMONY.fullmatch(token_text)
                or HEADINGS.fullmatch(re.sub(r'(?<=\w)-\s*(?=\w)', ' ', str(text)).strip()))


def prose_label(label):
    """Reject obvious sentence prefixes, never a short/incomplete name or role."""
    if ROLE.search(label) or non_individual(label):
        return False
    if split_speaker(str(label) + ': content'):
        return False
    tokens = re.findall(r"[\w']+", str(label))
    connectors = {'bin', 'binti', 'ibni', 'a', 'l', 'p', 'de', 'van', 'von', 'of', 'the', 'and', 'di', 'yang'}
    cues = {'is', 'are', 'was', 'were', 'has', 'have', 'will', 'would', 'should', 'must', 'begs',
            'adalah', 'ialah', 'akan', 'telah', 'boleh', 'perlu', 'hendak', 'merupakan', 'kerana', 'bahawa'}
    return len(tokens) >= 4 and any(t in cues for t in tokens) and sum(
        t.islower() and t not in connectors for t in tokens) >= 2



def speaker_prefix(text, allow_unknown=False):
    parsed = split_speaker(text)
    if parsed:
        return parsed
    label, colon, body = str(text).partition(':')
    label = ' '.join(label.split())
    if not colon or len(label) > 200:
        return None
    if non_individual(label):
        return label, body
    outer = re.sub(r'\([^)]*\)|\[[^]]*\]', '', label).strip()
    tokens = outer.split()
    # Bare full names may lack a parliamentary title. Record their boundary
    # conservatively; identity assignment still requires the canonical index.
    connectors = {'bin', 'binti', 'ibni', 'a/l', 'a/p', 'de', 'van', 'von', 'dan', 'di', 'yang', 'of', 'the', 'and', 'for', 'in', 'to'}
    significant = [token for token in tokens if token.casefold() not in connectors]
    if 2 <= len(significant) <= 8 and all(token[0].isupper() and any(c.isalpha() for c in token) for token in significant):
        return label, body
    # An unrecognised short prefix may be a lowercase/OCR-damaged name. It is
    # a boundary, not permission to carry the previous speaker through it.
    if allow_unknown and (1 <= len(tokens) <= 8 or ROLE.search(label)) and not prose_label(label):
        return label, body
    return None


def can_wrap_label(text):
    text = str(text).strip()
    if not text or len(text) > 200 or ':' in text or non_speech_text(text) or written_question(text) or text.isupper():
        return False
    if text.count('(') > text.count(')') or text.count('[') > text.count(']'):
        return True
    if split_speaker(text + ':'):
        return True
    tokens = text.split()
    connectors = {'bin', 'binti', 'ibni', 'a/l', 'a/p', 'de', 'van', 'von', 'dan', 'di', 'yang', 'of', 'the', 'and', 'for', 'in', 'to'}
    return bool(tokens) and all(t.casefold() in connectors or (t[0].isupper() and any(c.isalpha() for c in t)) for t in tokens)


class SpeechContext:
    def __init__(self, units, source):
        self.source = source
        self.units = []
        self.events = []
        pieces = []
        position = 1  # Leading space permits token-boundary searches.
        for unit in units:
            text = unit['text']
            normalized = words(text)
            kind = unit.get('kind', '').upper()
            label = unit.get('label')
            ref = unit['ref']
            if any(value in kind for value in ('HEADER', 'FOOTER', 'PAGE_NUMBER')) and 'SECTION' not in kind:
                continue  # Page furniture must not interrupt a continuing speech.
            if 'LIST' in kind:
                self.events.append((position, None, ref))
                continue
            if label:
                self.events.append((position, label, ref))
            elif any(value in kind for value in ('TITLE', 'SECTION')) or written_question(text) or non_speech_text(text) or (text.isupper() and 2 <= len(text.split()) <= 20):
                self.events.append((position, None, ref))
            if normalized:
                end = position + len(normalized)
                self.units.append(dict(start=position, end=end, text=normalized, kind=kind,
                                       label=label, ref=ref, original=text))
                pieces.append(normalized)
                position = end + 1
        self.text = ' ' + ' '.join(pieces) + ' '
        self.positions = [event[0] for event in self.events]
        self.unit_positions = [unit['start'] for unit in self.units]
        self.unit_refs = {tuple(sorted(unit['ref'].items())): unit for unit in self.units}
        self.prefixes = {}
        for index, unit in enumerate(self.units):
            previous = bisect_right(self.positions, unit['start']) - 1
            if previous >= 0:
                position, label, _ = self.events[previous]
                if label and position < unit['start'] < position + len(words(label)):
                    continue  # Inside a wrapped full name, not a second speaker.
            pieces = []
            last_ref = None
            for following in self.units[index:index + 5]:
                ref = following['ref']
                if last_ref is not None and (
                    ('pdf_page' in ref and ref['pdf_page'] != last_ref.get('pdf_page')) or
                    ('line' in ref and ref['line'] != last_ref.get('line', -2) + 1) or
                    ('row' in ref and ref['row'] != last_ref.get('row', -2) + 1)):
                    break
                pieces.append(following['original'])
                joined = ' '.join(' '.join(pieces).replace('’', "'").split())
                label, colon, _ = joined.partition(':')
                if colon:
                    if label and len(label) <= 200:
                        self.prefixes.setdefault(label, unit['ref'])
                    break
                if len(joined) > 200:
                    break
                last_ref = ref

    def register(self, label, ref):
        """A canonical CSV name was independently verified as a raw prefix."""
        unit = self.unit_refs.get(tuple(sorted(ref.items())))
        if unit is None:
            return []
        start = unit['start']
        prefix = words(label)
        if not self.text.startswith(prefix + ' ', start):
            return []
        end = start + len(prefix)
        hidden = [other['ref'] for other in self.units[
            bisect_right(self.unit_positions, start):bisect_left(self.unit_positions, end)]]
        left, right = bisect_left(self.positions, start), bisect_left(self.positions, end)
        self.events[left:right] = [(start, label, ref)]
        self.positions[left:right] = [start]
        return hidden

    def classify(self, text):
        normalized = words(text)
        if not normalized:
            return None
        needle = ' ' + normalized + ' '
        matches = []
        offset = 0
        while True:
            match = self.text.find(needle, offset)
            if match < 0:
                break
            start, end = match + 1, match + 1 + len(normalized)
            offset = match + 1
            left = max(0, bisect_right(self.unit_positions, start) - 1)
            if left < len(self.units) and self.units[left]['end'] <= start:
                left += 1
            units = self.units[left:bisect_left(self.unit_positions, end)]
            # Classify a heading only when the entire CSV row is a source
            # heading/ceremony, not because a heading occurs somewhere in it.
            exact_units = units and all(not unit['label'] for unit in units) and all(
                any(kind in unit['kind'] for kind in ('TITLE', 'SECTION')) or non_speech_text(unit['original'])
                for unit in units)
            exact_span = units and start == units[0]['start'] and end == units[-1]['end']
            if exact_units and exact_span:
                matches.append(dict(classification='non_speech', refs=[unit['ref'] for unit in units], labels=[]))
                continue
            event_index = bisect_right(self.positions, start) - 1
            if event_index < 0:
                events = []
            else:
                events = self.events[event_index:bisect_left(self.positions, end)]
            # Written questions are not a named speaker turn. Do not exclude
            # a row that also contains a subsequent explicit speaking turn.
            if written_question(text) and ':' not in str(text) and not any(start < position < end and label for position, label, _ in events):
                matches.append(dict(classification='written_question', refs=[unit['ref'] for unit in units], labels=[]))
                continue
            if len(normalized.split()) < 8 or not events or any(label is None for _, label, _ in events):
                matches.append(None)
                continue
            labels = list(dict.fromkeys(label for _, label, _ in events))
            first_position, first_label, _ = events[0]
            matches.append(dict(classification='source_context', labels=labels,
                                starts_in_label=first_position <= start < first_position + len(words(first_label)),
                                refs=[ref for _, _, ref in events]))
        if not matches or any(match is None for match in matches):
            return None
        signatures = {(match['classification'], tuple(match['labels']), match.get('starts_in_label')) for match in matches}
        if len(signatures) != 1:
            return None  # Repeated text with different speakers is ambiguous.
        return dict(matches[0], source=self.source, matched_occurrences=len(matches))
