"""MMS proceedings rules, isolated from ordinary DR/DN/KKDR tabulation."""
import re

from hansards_pipelines.tabulate_hansard import (
    add_formatting, get_author_and_speech, standardise_timestamp,
)

_HEADING_START = re.compile(
    r"^(?:MENGANGKAT SUMPAH\b|LANTIKAN\b|PEMASYHURAN\b|PENGUMUMAN\b|"
    r"PELANTIKAN\b|USUL\b|PEMILIHAN\b|TUAN YANG DI-PERTUA MENGANGKAT SUMPAH\b|"
    r"UCAPAN\b|MENGALU-ALUKAN\b)"
)
_PAGE_HEADER = re.compile(r"^[ .\d]*(?:MMS|DN)[ .\d]*$")
_OPENING = re.compile(r"Mesyuarat dimulakan pada pukul\s+", re.I)
_CLOCK = re.compile(r"(?:[■◼▪]\s*\d{4}\.?|\d{1,2}[.:]\d{2}\s*(?:pg|ptg|pagi|petang|malam|tgh)\.?)", re.I)
_SPEAKER_START = re.compile(
    r"^(?:(?:Yang Berhormat\s+)?(?:Tuan|Puan|Datuk|Dato[’']?|Datin|Tan Sri|Tun|Dr\.|"
    r"Tengku|Raja|Haji|Hajah|Ustaz|Prof\.)\b|(?:Timbalan\s+)?(?:Perdana\s+)?Menteri\b|"
    r"(?:Timbalan\s+)?(?:Tuan\s+)?Yang di-Pertua\b|Setiausaha\b)", re.I)


def proceedings_opening(line):
    """A timed meeting opening distinguishes proceedings from covers and contents."""
    return bool(_OPENING.search(line))


def _speaker_label(candidate):
    candidate = " ".join(candidate.split())
    if not _SPEAKER_START.match(candidate):
        return False
    # Introductions and narrative addressed to members are not speaker labels.
    if re.search(r"\b(?:yang tersebut|telah mengangkat|saya|ingin|menjemput|berikut|ialah)\b", candidate, re.I):
        return False
    return candidate.count("[") == candidate.count("]")


def heading_spans(lines):
    """Join wrapped uppercase titles after DOA or a timed proceedings opening.

    Known ceremony title openings anchor detection. Subsequent uppercase lines
    continue a title unless they begin another title. Blank lines may separate
    distinct headings, so they are never crossed when joining.
    """
    result = []
    active = False
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if re.fullmatch(r"D\s*O\s*A", line) or proceedings_opening(line):
            active = True
        if active and line.isupper() and _HEADING_START.match(line) and ":" not in line.rstrip(":").rstrip():
            end = index + 1
            parts = [line.rstrip(":").rstrip()]
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
            opening = _OPENING.search(line)
            if opening:
                timestamp = standardise_timestamp(line[opening.end():])
            if re.fullmatch(r"D\s*O\s*A", line) or proceedings_opening(line):
                active = True
            index += 1
            continue
        if index in headings:
            flush()
            index, title = headings[index]
            if (title.startswith("MENGANGKAT SUMPAH") and levels[0]
                    and title != levels[0]
                    and levels[0].startswith(("PENGUMUMAN", "PELANTIKAN", "MENGANGKAT SUMPAH"))):
                levels[1:] = [title, ""]
            elif title.startswith("LANTIKAN") and levels[1].startswith("MENGANGKAT SUMPAH"):
                levels[2] = title
            elif title.startswith(("MENGANGKAT SUMPAH", "PEMASYHURAN", "PENGUMUMAN", "PELANTIKAN", "USUL")) or not levels[0]:
                levels[:] = [title, "", ""]
            elif title.startswith("UCAPAN ") and levels[1] and title.startswith(levels[1] + " "):
                levels[2] = title
            else:
                levels[1:] = [title, ""]
            if title.startswith(("MENGANGKAT SUMPAH", "LANTIKAN", "PELANTIKAN")):
                speaker = ""
            continue
        if not line or _PAGE_HEADER.fullmatch(line) or re.fullmatch(r"D\s*O\s*A", line):
            index += 1
            continue
        if _CLOCK.fullmatch(line):
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
        consumed = 1
        # Only join a wrapped label when it begins like a speaker and reaches a
        # valid colon on the same physical page. Formatting masks stay aligned.
        if (":" not in current_text and _SPEAKER_START.match(line)
                and not line.endswith((".", ";", "!", "?"))):
            pieces = [current_text]
            for offset in range(1, 4):
                pos = index + offset
                if pos >= len(text) or pos in headings or not text[pos].strip():
                    break
                if pages[index] and pages[pos] and pages[index].get("pdf_page") != pages[pos].get("pdf_page"):
                    break
                # Never absorb the next speaker or a completed prose sentence.
                if (_SPEAKER_START.match(text[pos].strip())
                        and ":" in text[pos]
                        and _speaker_label(text[pos].split(":", 1)[0])):
                    break
                if text[pos].strip().endswith((".", ";", "!", "?")) and ":" not in text[pos]:
                    break
                pieces.append(text[pos])
                combined = "".join(pieces)
                if ":" in combined:
                    if _speaker_label(combined.split(":", 1)[0]):
                        consumed = offset + 1
                        current_text = combined
                        current_bold = "".join(bold[index:index + consumed])
                        current_italic = "".join(italics[index:index + consumed])
                    break
        candidate = current_text.split(":", 1)[0] if ":" in current_text else ""
        author = ""
        if candidate and _speaker_label(candidate):
            author, body, body_bold, body_italic, _ = get_author_and_speech(
                current_text, current_bold, current_italic, "MMS", is_pipeline=True
            )
            if candidate.strip().lower() == "setiausaha":
                colon = current_text.index(":")
                author = candidate.strip()
                body, body_bold, body_italic = current_text[colon + 1:], current_bold[colon + 1:], current_italic[colon + 1:]
            author = " ".join(author.split())
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
        metadata.extend(pages[index:index + consumed])
        index += consumed
    flush()
    if not rows:
        raise ValueError("No MMS transcript rows found; review this PDF layout")
    return rows, None, None
