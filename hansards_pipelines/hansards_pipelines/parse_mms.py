"""MMS proceedings rules, isolated from ordinary DR/DN/KKDR tabulation."""
import re

from hansards_pipelines.tabulate_hansard import (
    add_formatting, get_author_and_speech, standardise_timestamp,
)

_HEADING_START = re.compile(
    r"^(?:MENGANGKAT SUMPAH\b|LANTIKAN\b|PEMASYHURAN\b|UCAPAN\b|MENGALU-ALUKAN\b)"
)
_PAGE_HEADER = re.compile(r"^[ .\d]*MMS[ .\d]*$")


def heading_spans(lines):
    """Join wrapped uppercase titles; uppercase prose alone is not a title.

    Known ceremony title openings anchor detection. Subsequent uppercase lines
    continue a title unless they begin another title. Blank lines may separate
    distinct headings, so they are never crossed when joining.
    """
    result = []
    active = False
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if re.fullmatch(r"D\s*O\s*A", line):
            active = True
        if active and line.isupper() and _HEADING_START.match(line) and ":" not in line:
            end = index + 1
            parts = [line]
            while end < len(lines):
                candidate = lines[end].strip()
                if (not candidate or not candidate.isupper()
                        or _HEADING_START.match(candidate)
                        or _PAGE_HEADER.fullmatch(candidate)
                        or candidate.startswith(("[", "■"))
                        or ":" in candidate or candidate.endswith((".", ";", "!", "?"))):
                    break
                parts.append(candidate)
                end += 1
            result.append((index, end, " ".join(parts)))
            index = end
        else:
            index += 1
    return result


def extract_categories(text):
    categories = list(dict.fromkeys(title for _, _, title in heading_spans(text.splitlines())))
    if not categories:
        raise ValueError("No MMS proceedings headings found; review this PDF layout")
    return categories


def tabulate_mms(hansard_date, house, text, bold, italics, categories=None,
                 attendance_txt=None, page_metadata=None, is_pipeline=True):
    """Return the pipeline's ten-column transcript rows and empty attendance.

    Uses existing speaker recognition and formatting helpers, with MMS-specific
    title handling and standalone bracketed annotations. Page ranges come from
    the content lines rather than the title/cover. No backend or storage access.
    """
    if house.upper() != "MMS":
        raise ValueError("tabulate_mms only accepts MMS documents")
    if not (len(text) == len(bold) == len(italics)):
        raise ValueError("MMS text and formatting rows are misaligned")
    pages = page_metadata if page_metadata is not None else [None] * len(text)
    if len(pages) != len(text):
        raise ValueError("MMS text and page metadata are misaligned")
    headings = {start: (end, title) for start, end, title in heading_spans(text)}
    rows = []
    levels = ["", "", ""]
    speaker = ""
    timestamp = ""
    chunks, bold_chunks, italic_chunks, metadata = [], [], [], []
    row_author = ""

    def flush():
        if not chunks:
            return
        content = "".join(chunks).strip()
        if content:
            source = [p["source_page"] for p in metadata if p and p.get("source_page") is not None]
            physical = [p["pdf_page"] for p in metadata if p and p.get("pdf_page") is not None]
            if row_author != "ANNOTATION":
                content = add_formatting(content, "".join(bold_chunks).strip(), "".join(italic_chunks).strip())
            rows.append([*levels, timestamp, row_author, content,
                         min(source) if source else None, max(source) if source else None,
                         min(physical) if physical else None, max(physical) if physical else None])
        chunks.clear()
        bold_chunks.clear()
        italic_chunks.clear()
        metadata.clear()

    index = 0
    active = False
    while index < len(text):
        line = text[index].strip()
        if not active:
            if "Mesyuarat dimulakan pada pukul " in line:
                timestamp = standardise_timestamp(line.split("pukul ", 1)[1])
            if re.fullmatch(r"D\s*O\s*A", line):
                active = True
            index += 1
            continue
        if index in headings:
            flush()
            index, title = headings[index]
            if title.startswith(("MENGANGKAT SUMPAH", "PEMASYHURAN")) or not levels[0]:
                levels[:] = [title, "", ""]
            elif title.startswith("UCAPAN ") and levels[1] and title.startswith(levels[1] + " "):
                levels[2] = title
            else:
                levels[1:] = [title, ""]
            speaker = ""
            continue
        if not line or _PAGE_HEADER.fullmatch(line):
            index += 1
            continue
        if re.fullmatch(r"[■◼▪]\s*\d{4}\.?", line):
            flush()
            timestamp = standardise_timestamp(line)
            index += 1
            continue
        if line.startswith("["):
            flush()
            row_author = "ANNOTATION"
            while index < len(text):
                annotation = text[index].strip()
                chunks.append(annotation + "\n")
                metadata.append(pages[index])
                index += 1
                if "]" in annotation:
                    break
            else:
                raise ValueError("Unclosed MMS annotation; review this PDF layout")
            flush()
            continue

        # Preserve aligned masks for the existing speaker/markdown helpers.
        current_text = text[index]
        current_bold, current_italic = bold[index], italics[index]
        if re.match(r"^\s*Setiausaha\s*:", current_text):
            colon = current_text.index(":")
            author = current_text[:colon].strip()
            body, body_bold, body_italic = current_text[colon + 1:], current_bold[colon + 1:], current_italic[colon + 1:]
        else:
            author, body, body_bold, body_italic, _ = get_author_and_speech(
                current_text, current_bold, current_italic, "MMS", is_pipeline=True
            )
        if author:
            flush()
            speaker = author
        else:
            body, body_bold, body_italic = current_text, current_bold, current_italic
        # Match the existing transcript convention of splitting physical pages.
        if metadata and pages[index] and metadata[-1] and pages[index].get("pdf_page") != metadata[-1].get("pdf_page"):
            flush()
        row_author = speaker or "ANNOTATION"
        chunks.append(body)
        bold_chunks.append(body_bold)
        italic_chunks.append(body_italic)
        metadata.append(pages[index])
        index += 1
    flush()
    if not rows:
        raise ValueError("No MMS transcript rows found; review this PDF layout")
    return rows, None, None
