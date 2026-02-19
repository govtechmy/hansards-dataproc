def normalize_meeting_value(meeting: str) -> str:
    """
    Normalize meeting identifiers so source and DB align.
 
    Issues observed:
    - The Portal Parlimen (source) uses "11" to denote the mesyuarat khas, while the DB uses "0" for the same meeting.
    For info our db schema defines the following mapping for:
        0 - Mesyuarat Khas
        1 - Mesyuarat Pertama
        2 - Mesyuarat Kedua
        3 - Mesyuarat Ketiga
        -1 - Hidden (not displayed in the front end)

    So the normalization rule needs to account for this discrepancy.

    Rule:
    - Source meeting 11 == DB meeting 0
    """

    if meeting == "11":
        return "0"

    return meeting