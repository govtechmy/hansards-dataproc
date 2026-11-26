"""Source-layout evidence for notes, independent of font styling.

Only notes occupying whole source lines/blocks are candidates for separation.
The same reaction may be inline or standalone; missing layout is not evidence
that a reaction is a new paragraph.
"""

import re
import statistics
import warnings


class AnnotationLayoutWarning(UserWarning):
    """A source note needs review because paragraph evidence is unavailable."""


_REACTION = re.compile(r"^(?:(?:Dewan\s+)?(?:tepuk|ketawa|riuh)|applause|laughter|interruption)\b", re.I)
_EVENT = re.compile(
    # The verb is stable even when old OCR corrupts Mesyuarat/Jawatankuasa.
    r"(?:\bmempengerusikan\b|"
    r"\bin the Chair\b|^Doa\s+Selamat\s+dibacakan\b|"
    r"^(?:Dewan|Mesyuarat|Majlis)\s+(?:ditangguhkan|ditempohkan|disambung|tamat)\b|"
    r"\bberangkat\s+(?:meninggalkan|masuk)\b|^Upacara\b.*\b(?:tamat|selesai)\b)", re.I,
)
_ACTION = re.compile(
    r"^(?:Bangun|Masih berdiri|Menyampuk|Disampuk|Membaca|Meneguk|"
    r"Pembesar suara|Ahli-ahli|Beberapa Ahli|Yang Berbahagia|"
    r"Kebawah Duli|Seri Paduka|Tuan Yang di-Pertua|Timbalan Yang di-Pertua|"
    r"The Clerk|Mr President|Mr Speaker)\b", re.I,
)
_REFERENCE = re.compile(r"^(?:Akta|Act|Fasal|Clause|Seksyen|Section|Jadual|Schedule|\d)\b", re.I)
_NARRATION = re.compile(
    r"^(?:(?:Dewan|Mesyuarat)\s+(?:ditangguhkan|ditempohkan|disambung semula)\b|"
    r"(?:Whereupon|Thereupon)\b|(?:Mr\.?\s+(?:Speaker|President)|The\s+(?:Speaker|President))"
    r"\s+(?:sat down|took|subscribed)\b|(?:Senate|House)\s+adjourned\b|Adjourned\s+(?:accordingly|\d))", re.I,
)


def bracket_spans(text):
    """Yield balanced square/round spans, including nested speaker-name brackets."""
    stack = []
    start = None
    for index, char in enumerate(text):
        if char in "[(":
            if not stack:
                start = index
            stack.append("]" if char == "[" else ")")
        elif stack and char == stack[-1]:
            stack.pop()
            if not stack:
                yield start, index + 1


def note_kind(text):
    value = " ".join(text.strip().strip("[]()").split())
    if _REACTION.match(value):
        return "reaction"
    if _EVENT.search(value):
        return "event"
    if _ACTION.match(value):
        return "action"
    return None if _REFERENCE.match(value) else "unknown"


def is_event_narration(text):
    return bool(_NARRATION.match(" ".join(text.split())))


def is_note_only(text):
    """A complete note or sequence of notes, without a speaker label or prose."""
    text = text.strip()
    spans = list(bracket_spans(text))
    return bool(spans and spans[0][0] == 0
                and not text[spans[-1][1]:].strip(" .")
                and all(note_kind(text[start:stop]) for start, stop in spans)
                and all(not text[a[1]:b[0]].strip() for a, b in zip(spans, spans[1:])))


def paragraph_decision(kind, metadata=None):
    """Return standalone/inline/review, using explicit paragraph evidence first."""
    metadata = metadata or {}
    if kind == "unknown":
        return "review"
    if metadata.get("paragraph_start") is True:
        return "standalone"
    # A complete sitting event is independently meaningful even in old cached
    # output without coordinates. Reactions and personal actions are not.
    if kind == "event":
        return "standalone"
    if metadata.get("paragraph_start") is False:
        return "inline"
    return "review"


def warn_review(refs):
    if refs:
        warnings.warn(
            "Annotation paragraph placement needs review; kept with surrounding "
            f"content at {', '.join(map(str, refs[:12]))}"
            + (f" (and {len(refs) - 12} more)" if len(refs) > 12 else ""),
            AnnotationLayoutWarning, stacklevel=2,
        )


def pdf_line_metadata(page, extracted, pdf_page):
    """Keep line coordinates alongside the existing, unchanged extracted text.

    Only align when pdfplumber's line text matches exactly (ignoring spaces).
    A mismatch leaves paragraph placement unknown rather than guessing offsets.
    """
    raw = extracted.splitlines()
    output = [{"pdf_page": pdf_page, "source_page": None} for _ in raw]
    if hasattr(page, "extract_text_lines"):
        lines = page.extract_text_lines(return_chars=False)
    elif hasattr(page, "chars"):
        # The deployed project also supports pdfplumber 0.7.x. Use the same
        # character clustering as its extract_text(), not a second word order.
        from pdfplumber.utils import cluster_objects, collate_line
        lines = []
        for chars in cluster_objects(page.chars, lambda char: char["doctop"], 3):
            visible = [char for char in chars if char["text"].strip()]
            if not visible:
                visible = chars
            lines.append({"text": collate_line(chars, 3),
                          "x0": min(char["x0"] for char in visible),
                          "x1": max(char["x1"] for char in visible),
                          "top": min(char["top"] for char in visible),
                          "bottom": max(char["bottom"] for char in visible)})
    else:
        return output
    norm = lambda value: re.sub(r"\s+", "", value)
    if len(lines) != len(raw) or any(norm(a) != norm(b["text"]) for a, b in zip(raw, lines)):
        return output
    if not lines:
        return output
    body_lines = [line for line in lines if line["text"].strip()]
    if not body_lines:
        return output
    heights = [line["bottom"] - line["top"] for line in body_lines]
    height = statistics.median(heights)
    left = min(line["x0"] for line in body_lines)
    right = max(line["x1"] for line in body_lines)
    steps = [b["top"] - a["top"] for a, b in zip(body_lines, body_lines[1:])
             if height * .8 < b["top"] - a["top"] < height * 2.5]
    step = statistics.median(steps) if steps else height * 1.5
    for index, (line, meta) in enumerate(zip(lines, output)):
        if not line["text"].strip():
            continue
        meta.update({"line_x0": line["x0"], "line_x1": line["x1"],
                     "line_top": line["top"], "line_bottom": line["bottom"],
                     "body_left": left})
        if index:
            previous = lines[index - 1]
            # Indented first lines and additional paragraph spacing are both
            # evidence; a normally spaced line at the body margin is a wrap.
            meta["paragraph_start"] = bool(
                line["x0"] - left > height * 1.2
                or line["top"] - previous["top"] > step * 1.3
            )
            if not meta["paragraph_start"] and right - previous["x1"] > height * 2:
                # A short preceding line could end either a paragraph or a
                # speech. Its following marker is ambiguous without spacing.
                meta.pop("paragraph_start")
            # A page header's large gap is not paragraph evidence. A note at
            # the body margin may simply be wrapped from the previous page.
            previous_text = previous["text"].strip()
            if (re.search(r"\b(?:DR|DN|KKDR|MMS)[ .]*\d", previous_text)
                    or not previous_text) and line["x0"] - left <= height * 1.2:
                meta.pop("paragraph_start", None)
    return output


def annotation_line_groups(text, metadata):
    """Classify complete note-only spans without splitting inline source text."""
    result, review = {}, []
    index = 0
    while index < len(text):
        line = text[index].strip()
        if is_event_narration(line):
            result[index] = 1
            index += 1
            continue
        if not line.startswith(("[", "(")):
            index += 1
            continue
        # A bracket can wrap over lines, or even a physical page. Require that
        # the whole span contains notes only, never a name label or speech.
        candidate = ""
        for end in range(index, min(index + 20, len(text))):
            candidate += text[end]
            spans = list(bracket_spans(candidate))
            if not spans:
                continue
            tail = candidate[spans[-1][1]:].strip(" \t\r\n.")
            if tail:
                if tail.startswith(("[", "(")):
                    continue
                break  # The closing bracket is followed by speech: inline.
            cursor, kinds = 0, []
            for start, stop in spans:
                if candidate[cursor:start].strip():
                    break
                kinds.append(note_kind(candidate[start:stop]))
                cursor = stop
            else:
                if kinds and all(kinds):
                    kind = "event" if "event" in kinds else kinds[0]
                    decision = paragraph_decision(kind, metadata[index])
                    if decision == "standalone":
                        result[index] = end - index + 1
                    elif decision == "review":
                        review.append(index)
                    index = end
            break
        else:
            if note_kind(line):
                review.append(index)
        index += 1
    return result, review
