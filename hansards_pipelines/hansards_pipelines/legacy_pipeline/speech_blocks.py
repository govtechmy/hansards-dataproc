"""Interpret existing OCR blocks without performing OCR or accessing services."""

import re
import math
from ..annotation_layout import (
    bracket_spans, note_kind, is_note_only, is_event_narration, paragraph_decision, warn_review,
)


_TRANSLATION = re.compile(
    r"\s*\((?:translated\s+from\s+[^)]+|terjemahan[^)]*)\)", re.I
)
_CONNECTORS = {"the", "of", "for", "and", "dan", "di", "yang", "bin", "binti", "a/l", "a/p"}
_LIST_ITEM = re.compile(
    r"^\s*(?:\((?:\d+|[a-z]|[ivxlcdm]+)\)|\d+[.)]|[a-z][.)])\s+", re.I,
)


def _speech_text(row):
    """Keep source list boundaries while joining ordinary wrapped lines."""
    raw = str(row.get("text", row["clean"]))
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if sum(bool(_LIST_ITEM.match(line)) for line in lines) < 2:
        return row["clean"].strip()
    items = []
    for line in lines:
        line = " ".join(line.split())
        if not items or _LIST_ITEM.match(line):
            items.append(line)
        else:
            items[-1] += " " + line
    return "\n".join(items)


_LABEL_START = re.compile(
    r"^(?:(?:Mr|Mrs|Ms|Dr|Sir|Lord|Dato|Datuk|Datin|Tun|Tunku|Tengku|Raja|Nik|"
    r"Tan|Sri|Tuan|Puan|Encik|Enche|Haji|Hajah|Lt|Kol|Y\.B|Yang|Timbalan|"
    r"Menteri|Perdana|Setiausaha|Pengerusi|Speaker|President)\b|"
    r"(?:The\s+)?(?:Prime Minister|Deputy|Minister|Parliamentary Secretary|"
    r"Speaker|President|Chairman|Clerk)\b)"
)


def split_speaker(text):
    """Return (author, speech) only when the prefix resembles a name or role.

    Parentheses may contain constituencies, names, or translation notes. Validate
    the outer label structurally, rather than searching for substrings in names.
    """
    label, colon, speech = text.partition(":")
    if not colon or len(label) > 200:
        return None
    label = " ".join(label.split())
    outer = re.sub(r"\([^)]*\)|\[[^]]*\]", "", label).strip()
    tokens = outer.split()
    if not tokens or len(tokens) > 18:
        return None
    if not _LABEL_START.match(outer) and not _TRANSLATION.search(label):
        # Bare title-case prose can resemble a name. Keep it as content unless
        # a parliamentary title or translation descriptor supplies evidence.
        return None
    significant = [t for t in tokens if t.lower() not in _CONNECTORS]
    if not significant or not all(
        (t[0].isupper() or t.startswith("di-")) and any(c.isalpha() for c in t)
        for t in significant
    ):
        return None
    # A single word such as "Note:" or "Price:" is insufficient evidence.
    if len(significant) < 2 and outer.lower() not in {
        "speaker", "president", "pengerusi", "tuan pengerusi", "the president", "the speaker"
    }:
        return None
    notes = _TRANSLATION.findall(label)
    author = _TRANSLATION.sub("", label).strip()
    # Keep translation information in the content, away from author matching.
    return author, " ".join([*(n.strip() for n in notes), speech.strip()]).strip()


def attach_source_pages(df):
    """Retain observed printed-number ranges before layout headers are removed.

    Old scans can contain two printed columns/pages. The CSV has no bounding
    boxes, so the range applies to the whole scan, not an individual column.
    Do not interpret numbers in body text or invent missing page numbers.
    """
    df = df.copy()
    markers = {}
    for _, row in df.iterrows():
        layout = str(row.get("layout", "")).upper()
        if not any(kind in layout for kind in ("PAGE_NUMBER", "HEADER", "FOOTER")):
            continue
        if "SECTION" in layout:
            continue
        text = str(row.get("text", "")).strip()
        if re.fullmatch(r"[0-9]+", text) and int(text) > 0:
            markers.setdefault(str(row["page"]), []).append(int(text))
    df["source_page_start"] = df["page"].map(
        lambda page: markers.get(str(page), [None])[0]
    )
    df["source_page_end"] = df["page"].map(
        lambda page: markers.get(str(page), [None])[-1]
    )
    return df


def _block_paragraph(row, previous):
    """Use optional OCR geometry; older layout CSVs remain readable."""
    if previous is None or str(row.get("page")) != str(previous.get("page")):
        return {}
    try:
        left, top, height = (float(row[key]) for key in ("Left", "Top", "Height"))
        prev_left, prev_top, prev_height = (
            float(previous[key]) for key in ("Left", "Top", "Height")
        )
        if not all(math.isfinite(value) for value in (left, top, height, prev_left, prev_top, prev_height)):
            return {}
        if height <= 0 or prev_height <= 0:
            return {}
        line_height = prev_height / max(1, len(str(previous.get("text", "")).splitlines()))
        # Do not infer paragraphs across columns or in reverse reading order.
        if abs(left - prev_left) > max(height, line_height) * 8 or top < prev_top:
            return {}
        new_paragraph = bool(
            left - prev_left > line_height * 1.2
            or top - (prev_top + prev_height) > line_height * .8
        )
        return {"paragraph_start": True} if new_paragraph else {}
    except (KeyError, TypeError, ValueError):
        return {}


def split_ocr_speaker_blocks(post):
    """Split validated speaker turns on raw OCR lines before flattening text.

    A label can wrap across up to four source lines. Colons inside ordinary
    prose or quoted labels do not qualify as a source-line speaker prefix.
    """
    records = []
    for _, row in post.iterrows():
        raw = str(row.get('text', row['clean']))
        lines = raw.splitlines(keepends=True)
        starts = [0]
        label_end = 0
        for index, line in enumerate(lines):
            if index < label_end:
                continue
            if not _LABEL_START.match(line.strip()):
                continue
            for end in range(index + 1, min(index + 4, len(lines)) + 1):
                candidate = ' '.join(''.join(lines[index:end]).split())
                if ':' not in candidate:
                    continue
                if split_speaker(candidate):
                    starts.append(index)
                    label_end = end
                break
        starts = sorted(set(starts))
        if len(starts) == 1:
            records.append(row.to_dict())
            continue
        for start, end in zip(starts, starts[1:] + [len(lines)]):
            part = row.to_dict()
            part['text'] = ''.join(lines[start:end])
            part['clean'] = ' '.join(part['text'].split())
            part['is_upper'] = sum(c.isupper() for c in part['clean']) > sum(c.islower() for c in part['clean'])
            records.append(part)
    return post.__class__(records, columns=post.columns).reset_index(drop=True)


def _note_units(post):
    """Separate source note paragraphs before interpreting speaker labels.

    OCR sometimes joins a chairing note and the next speaker into one block.
    Split only a whole note/block or an event on its own original source line.
    Never detach a reaction from text on the same source line.
    """
    post = split_ocr_speaker_blocks(post)
    previous = None
    for index, row in post.iterrows():
        raw = str(row.get("text", row["clean"]))
        # Named speakers can have annotation-only turns, such as [Bangun].
        speaker = split_speaker(row["clean"])
        body = speaker[1].strip() if speaker else ""
        annotation_only_turn = is_note_only(body)
        if speaker and annotation_only_turn and not raw.lstrip().startswith(("[", "(")):
            yield row, False, None
            previous = row
            continue
        if is_event_narration(raw):
            yield row, True, None
            previous = row
            continue
        cuts = []
        review = bool(raw.lstrip().startswith(("[", "("))
                      and not list(bracket_spans(raw)) and note_kind(raw))
        for start, stop in bracket_spans(raw):
            kind = note_kind(raw[start:stop])
            if not kind:
                continue
            prefix, suffix = raw[:start], raw[stop:]
            line_prefix = prefix.rsplit("\n", 1)[-1]
            line_suffix = suffix.split("\n", 1)[0]
            # A following speaker can be glued to the note by OCR.
            following_speaker = not prefix.strip() and split_speaker(" ".join(suffix.split()))
            alone = not prefix.strip() and not suffix.strip()
            own_line = not line_prefix.strip() and not line_suffix.strip(" \t\r.")
            if not (alone or own_line or following_speaker):
                continue
            decision = paragraph_decision(kind, _block_paragraph(row, previous) if alone else {})
            if decision == "standalone":
                if not line_suffix.strip(" \t\r."):
                    # Keep punctuation with its note instead of creating a
                    # new speech fragment containing only a full stop.
                    stop += len(line_suffix)
                cuts.append((start, stop))
            elif decision == "review":
                review = True
        if not cuts:
            yield row, False, index if review else None
        else:
            cursor = 0
            for start, stop in cuts:
                for value, annotation in ((raw[cursor:start], False), (raw[start:stop], True)):
                    if value.strip():
                        part = row.copy()
                        part["text"] = value
                        part["clean"] = " ".join(value.split())
                        yield part, annotation, index if review else None
                cursor = stop
            if raw[cursor:].strip():
                part = row.copy()
                part["text"] = raw[cursor:]
                part["clean"] = " ".join(raw[cursor:].split())
                yield part, False, index if review else None
        previous = row


def _remove_repeated_headings(segments, heading_prefixes):
    """Keep recognised headings in metadata rather than duplicate speech text.

    A heading without any body in its section remains untouched: the current
    database format cannot represent a section without a speech row.
    """
    candidates = {}
    body_contexts = set()
    for index, segment in enumerate(segments):
        context = (segment['level_1'], segment['level_2'])
        first, separator, rest = segment['speech'].partition('\n')
        body = segment['speech']
        if segment['author'] is None and (*context, first) in heading_prefixes:
            candidates[index] = rest if separator else ''
            body = candidates[index]
        if body.strip():
            body_contexts.add(context)
            # A parent heading is still displayed above its child sections.
            body_contexts.add((context[0], ''))

    result = []
    for index, segment in enumerate(segments):
        context = (segment['level_1'], segment['level_2'])
        if index in candidates and context in body_contexts:
            segment = dict(segment, speech=candidates[index])
            if not segment['speech'].strip():
                continue
        result.append(segment)
    return result


def segment_blocks(post, initial_timestamp, parse_timestamp, is_question_line):
    """Preserve every body block, with explicit speaker and heading boundaries."""
    segments = []
    author = None
    content = []
    pages = []
    source_starts = []
    source_ends = []
    level1 = level2 = ""
    timestamp = initial_timestamp
    review_refs = []
    heading_prefixes = set()

    def flush():
        if content:
            segments.append({
                "level_1": level1, "level_2": level2, "level_3": "",
                "timestamp": timestamp.strftime("%H%M") if timestamp else "",
                "author": author, "speech": "\n".join(content),
                "source_page_start": source_starts[0] if source_starts else None,
                "source_page_end": source_ends[-1] if source_ends else None,
                "pdf_page_start": min(pages) if pages else None,
                "pdf_page_end": max(pages) if pages else None,
            })
        content.clear()
        pages.clear()
        source_starts.clear()
        source_ends.clear()

    for row, annotation, review_ref in _note_units(post):
        text = _speech_text(row)
        if not text:
            continue
        if review_ref is not None:
            review_refs.append(f"OCR row {review_ref}, PDF page {row.get('page')}")
        if annotation:
            flush()
            saved_author = author
            author = "ANNOTATION"
            content.append(text)
            for field, values in (("source_page_start", source_starts), ("source_page_end", source_ends)):
                try:
                    values.append(int(float(row.get(field))))
                except (TypeError, ValueError, OverflowError):
                    values.append(None)
            try:
                pages.append(int(float(row.get("page"))))
            except (TypeError, ValueError, OverflowError):
                pass
            flush()
            author = saved_author
            continue
        speaker = split_speaker(text)
        heading = ((row["is_upper"] or "SECTION_HEADER" in str(row.get("layout", "")).upper())
                   and speaker is None and not is_note_only(text))
        if row["is_timestamp"]:
            new_timestamp = parse_timestamp(text)
            if new_timestamp:
                flush()
                timestamp = new_timestamp
            continue
        if heading:
            flush()
            author = None
            level1, level2 = row["level_1"], row["level_2"]
            # Defer deduplication until we know this section has body content.
            # Some OCR time markers pass the uppercase/heading heuristic;
            # they must not be removed by heading cleanup.
            if text in (level1, level2) and parse_timestamp(text) is None:
                heading_prefixes.add((level1, level2, text))
        elif speaker:
            flush()
            author, text = speaker
        elif is_question_line(text):
            flush()
            author = None
        # A procedural OCR list is not part of the preceding speaker's speech.
        elif (review_ref is None and "LIST" in str(row.get("layout", "")).upper()) or re.match(
            r"^(?:(?:Whereupon|Thereupon)\b|The following Members\b|"
            r"(?:The (?:President|Speaker|Members|House)\b).*?"
            r"\b(?:took|subscribed|adjourned|sat down)\b|(?:Senate|House) adjourned\b)",
            text, re.I,
        ):
            flush()
            author = None
        content.append(text)
        # Preserve unknown boundaries as NULL rather than substituting a marker
        # from a later/earlier scan in the same speech.
        for field, values in (("source_page_start", source_starts), ("source_page_end", source_ends)):
            try:
                values.append(int(float(row.get(field))))
            except (TypeError, ValueError, OverflowError):
                values.append(None)
        try:
            pages.append(int(float(row.get("page"))))
        except (TypeError, ValueError, OverflowError):
            pass
    flush()
    warn_review(list(dict.fromkeys(review_refs)))
    return _remove_repeated_headings(segments, heading_prefixes)
