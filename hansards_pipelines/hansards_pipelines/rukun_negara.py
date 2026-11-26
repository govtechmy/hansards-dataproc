"""Bounded formatting for the modern Rukun Negara section."""

import re
import statistics


TITLE = "LAFAZ IKRAR RUKUN NEGARA"


def normalized_title(value):
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def match_title(text, start, titles):
    """Match complete source lines, preferring the longest recognised title."""
    targets = {normalized_title(title): title for title in titles if title.strip()}
    value = ""
    best = None
    for end in range(start, min(start + 8, len(text))):
        value += normalized_title(text[end])
        if not value or not any(title.startswith(value) for title in targets):
            break
        if value in targets:
            best = (end + 1, targets[value])
    return best


def section_spans(text, bold, categories):
    """Only enable special handling when a later TOC boundary is confirmed."""
    result = {}
    next_titles = [title for title in categories
                   if normalized_title(title) != normalized_title(TITLE)]
    index = 0
    while index < len(text):
        start = match_title(text, index, [TITLE])
        if start is None:
            index += 1
            continue
        for end in range(start[0], len(text)):
            # A title quoted in ordinary prose must not end the section.
            visible = [char for char in bold[end] if not char.isspace()]
            heading_style = text[end].strip().isupper() or (
                bool(visible) and visible.count("1") / len(visible) > .8
            )
            boundary = match_title(text, end, next_titles) if heading_style else None
            if boundary:
                result[index] = (start[0], end, boundary)
                index = end
                break
        else:
            index = start[0]
    return result


def formatted_lines(text, bold, italics, metadata, formatter):
    """Keep paragraph gaps and principle lines, joining ordinary PDF wraps.

    Blank-line evidence is retained by preprocessing. Coordinates support old
    pretabulation caches which do not yet contain that flag.
    """
    steps = []
    for a, b in zip(metadata, metadata[1:]):
        a, b = a or {}, b or {}
        if a.get("pdf_page") == b.get("pdf_page") and "line_top" in a and "line_top" in b:
            delta = b["line_top"] - a["line_top"]
            if 0 < delta < 25:
                steps.append(delta)
    step = statistics.median(steps) if steps else None
    output = []
    label_open = False
    previous_label_end = False
    for index, line in enumerate(text):
        value = line.strip()
        if not value:
            continue
        meta = metadata[index] or {}
        previous_meta = (metadata[index - 1] or {}) if index else {}
        gap = bool(meta.get("source_blank_before"))
        if (step and index and "line_top" in meta and "line_top" in previous_meta
                and meta.get("pdf_page") == previous_meta.get("pdf_page")):
            gap |= meta["line_top"] - previous_meta["line_top"] > step * 1.6
        label = bool(re.match(r"\[Dilafazkan\b", value, re.I))
        previous = text[index - 1].strip() if index else ""
        if not output:
            separator = ""
        elif label_open:
            separator = " "
        elif gap or label or previous_label_end or (value.isupper() and not previous.isupper()):
            separator = "\n\n"
        elif value.isupper() or previous.isupper():
            separator = "  \n"  # Markdown hard break, not a PDF soft wrap.
        else:
            separator = " "
        # Format each line separately so an italic label cannot swallow its
        # colon/newline and produce invalid Markdown around paragraph breaks.
        output.append(separator + formatter(value, bold[index].strip(), italics[index].strip()))
        in_label = label or label_open
        label_open = in_label and "]" not in value
        previous_label_end = in_label and not label_open
    return "".join(output)
