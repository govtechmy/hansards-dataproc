"""Interpret existing OCR blocks without performing OCR or accessing services."""

import re


_TRANSLATION = re.compile(
    r"\s*\((?:translated\s+from\s+[^)]+|terjemahan[^)]*)\)", re.I
)
_CONNECTORS = {"the", "of", "for", "and", "di", "yang", "bin", "binti", "a/l", "a/p"}
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

    for _, row in post.iterrows():
        text = row["clean"].strip()
        if not text:
            continue
        speaker = split_speaker(text)
        heading = (row["is_upper"] or "SECTION_HEADER" in str(row.get("layout", "")).upper()) and speaker is None
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
            # Preserve the heading itself as unattributed content too.
        elif speaker:
            flush()
            author, text = speaker
        elif is_question_line(text):
            flush()
            author = None
        # A procedural OCR list is not part of the preceding speaker's speech.
        elif "LIST" in str(row.get("layout", "")).upper() or re.match(
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
    return segments
