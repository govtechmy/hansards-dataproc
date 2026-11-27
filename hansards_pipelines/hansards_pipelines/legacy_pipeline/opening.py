"""Locate actual proceedings and retain body events mislabelled as headers."""
import re

from ..annotation_layout import bracket_spans, note_kind, is_note_only


_OPENING = re.compile(r"Mesyuarat\s+dimulakan\b|The\s+[^\n]{0,50}\bmet\s+at\b", re.I)
_MALAY_OPENING = re.compile(
    r".*?Mesyuarat\s+dimulakan\s+pada\s+puku[li]\s+\d{1,2}[.:]\d{2}"
    r"\s*(?:tengah\s+hari|pagi|petang|malam|ptg|mlm)\.?\s*", re.I | re.S,
)
_PRAYER = re.compile(
    r"^\s*(?:DOA PENDAHULUAN|DOA|DO'A|D OA|D0A|D O A|DO A)"
    r"\s*(?:\n|$)", re.I,
)


def find_proceedings_start(df, keywords):
    """Reject contents-page matches when an explicit opening is available.

    Opening headings can precede the actual 'met at' statement, so compare
    physical pages as well as reading order. Without that context retain the
    existing keyword fallback used for old English records.
    """
    opening = next((index for index, row in df.iterrows()
                    if _OPENING.search(str(row['text']))), None)
    opening_page = str(df.loc[opening, 'page']) if opening is not None else None
    for keyword in keywords:
        matches = df[df['text'].str.contains(fr'\b{re.escape(keyword)}\b', case=True, na=False)]
        if opening is not None:
            contextual = matches[(matches.index >= opening) | (matches['page'].astype(str) == opening_page)]
            # Without a repeated match in opening context, retain the old
            # fallback rather than reject a genuine heading on a prior page.
            if not contextual.empty:
                matches = contextual
        if not matches.empty:
            index = matches.index[0]
            # Old English records put 'The House met...' before attendance
            # lists. Keep their later opening/prayer heading as the boundary.
            if opening is not None and _MALAY_OPENING.search(str(df.loc[opening, 'text'])):
                index = min(index, opening)
            return index
    return None


def body_blocks(post):
    """Remove opening mastheads, not the chair events embedded within them."""
    result = post.copy()
    opening_row = True
    masthead_rows = []
    for index, row in result.iterrows():
        raw = str(row['text']).replace('\r\n', '\n').replace('\r', '\n')
        trimmed = _MALAY_OPENING.sub('', raw, count=1) if index == post.index[0] else raw
        trimmed = _PRAYER.sub('', trimmed, count=1)
        is_header = 'HEADER' in str(row['layout']).upper() and 'SECTION_HEADER' not in str(row['layout']).upper()
        if is_header:
            # Ordinary running headers stay excluded; complete procedural
            # events are body content even when Textract labels them HEADER.
            events = [(a, b) for a, b in bracket_spans(trimmed)
                      if note_kind(trimmed[a:b]) == 'event']
            if not events:
                continue
            # Keep any following speech too; only the masthead before the
            # first event is known to be header material.
            trimmed = trimmed[events[0][0]:]
            result.at[index, 'layout'] = 'LAYOUT_TEXT'
        elif trimmed != raw:
            result.at[index, 'layout'] = 'LAYOUT_TEXT'
        # OCR can put the chamber masthead after DOA. Ignore only the
        # opening standalone label, allowing a chair annotation before it.
        if opening_row and trimmed.strip() and not is_note_only(trimmed):
            opening_row = False
            if ' '.join(trimmed.split()).upper() in {'DEWAN RAKYAT', 'DEWAN NEGARA'}:
                masthead_rows.append(index)
        result.at[index, 'text'] = trimmed
        result.at[index, 'clean'] = ' '.join(trimmed.split())
    return result.drop(index=masthead_rows)
