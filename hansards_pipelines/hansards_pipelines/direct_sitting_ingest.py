import json
from typing import Dict, List, Optional


# ---------------------------------------------------------------------
# House normalization (EXACT parity with ParliamentaryCycle.get_integer_value)
# ---------------------------------------------------------------------

def normalize_house(house: str) -> int:
    if not isinstance(house, str):
        raise ValueError(f"House must be string, got {type(house)}")

    mapping = {
        "dewan-rakyat": 0,
        "dewan-negara": 1,
        "kamar-khas": 2,
    }

    if house not in mapping:
        raise ValueError(f"Invalid house value: {house}")

    return mapping[house]


# ---------------------------------------------------------------------
# Nested speech JSON (EXACT backend parity)
# ---------------------------------------------------------------------

def _add_to_result(levels: List[str], data: Dict, result: List):
    if not levels:
        result.append(data)
        return

    current = result
    for level in levels:
        found = None
        for item in current:
            if level in item:
                found = item[level]
                break

        if not found:
            entry = {level: []}
            current.append(entry)
            found = entry[level]

        current = found

    current.append(data)


def build_nested_speech_json(flat_speeches: List[Dict]) -> List:
    result = []

    for row in flat_speeches:
        speech_obj = {
            "speech": row.get("proc_speech") or row.get("speech"),
            "author": row.get("author"),
            "author_id": row.get("speaker"),
            "timestamp": row["timestamp"],
            "is_annotation": row["is_annotation"],
            "index": row["index"],
        }

        levels = [
            row.get("level_1"),
            row.get("level_2"),
            row.get("level_3"),
        ]
        levels = [lvl for lvl in levels if lvl]

        _add_to_result(levels, speech_obj, result)

    return result


# ---------------------------------------------------------------------
# MAIN INGEST FUNCTION — DB ONLY (API PARITY)
# ---------------------------------------------------------------------

def ingest_sitting_to_db(payload: Dict, conn) -> None:
    """
    DB-only replacement for POST /api/sitting
    """

    date = payload["date"]
    filename = payload["filename"]
    is_final = payload["is_final"]
    house = normalize_house(payload["house"])

    speech_data_raw = payload["speech_data"]
    flat_speeches = (
        json.loads(speech_data_raw)
        if isinstance(speech_data_raw, str)
        else speech_data_raw
    )

    nested_speech_json = json.dumps(
        build_nested_speech_json(flat_speeches),
        ensure_ascii=False,
    )

    with conn.cursor() as cur:

        # --------------------------------------------------
        # Resolve ParliamentaryCycle
        # --------------------------------------------------
        cur.execute(
            """
            SELECT cycle_id
            FROM api_parliamentary_cycle
            WHERE house = %s
              AND start_date <= %s
              AND end_date >= %s
            """,
            (house, date, date),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(
                f"No ParliamentaryCycle found for house={house}, date={date}"
            )

        cycle_id = row[0]

        # --------------------------------------------------
        # Upsert Sitting (ALL NOT NULL FIELDS EXPLICIT)
        # --------------------------------------------------
        cur.execute(
            "SELECT sitting_id FROM api_sitting WHERE filename = %s",
            (filename,),
        )
        existing = cur.fetchone()

        if existing:
            sitting_id = existing[0]
            cur.execute(
                """
                UPDATE api_sitting
                SET date = %s,
                    is_final = %s,
                    has_dataset = %s,
                    summary_status = %s,
                    cycle_id = %s,
                    speech_data = %s
                WHERE sitting_id = %s
                """,
                (
                    date,
                    is_final,
                    False,          # has_dataset
                    "pending",      # summary_status
                    cycle_id,
                    nested_speech_json,
                    sitting_id,
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO api_sitting
                    (
                        date,
                        filename,
                        is_final,
                        has_dataset,
                        summary_status,
                        cycle_id,
                        speech_data
                    )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING sitting_id
                """,
                (
                    date,
                    filename,
                    is_final,
                    False,          # has_dataset
                    "pending",      # summary_status
                    cycle_id,
                    nested_speech_json,
                ),
            )
            sitting_id = cur.fetchone()[0]

        # --------------------------------------------------
        # Resolve AuthorHistory
        # --------------------------------------------------
        author_ids = {
            int(row["speaker"])
            for row in flat_speeches
            if row.get("speaker") is not None
        }

        author_history_map: Dict[int, Optional[int]] = {}

        if author_ids:
            cur.execute(
                """
                SELECT ah.record_id, a.new_author_id, ah.end_date
                FROM api_author_history ah
                JOIN api_author a ON a.id = ah.author_id
                WHERE a.new_author_id = ANY(%s)
                  AND ah.start_date <= %s
                  AND (ah.end_date >= %s OR ah.end_date IS NULL)
                """,
                (list(author_ids), date, date),
            )

            for record_id, author_id, end_date in cur.fetchall():
                if author_id not in author_history_map:
                    author_history_map[author_id] = record_id
                elif end_date is not None:
                    author_history_map[author_id] = record_id

        # --------------------------------------------------
        # Replace speeches
        # --------------------------------------------------
        cur.execute(
            "DELETE FROM api_speech WHERE sitting_id = %s",
            (sitting_id,),
        )

        rows = []
        for row in flat_speeches:
            speaker = row.get("speaker")
            rows.append(
                (
                    sitting_id,
                    int(row["index"]),
                    author_history_map.get(int(speaker)) if speaker else None,
                    row["timestamp"],
                    row.get("proc_speech") or row.get("speech"),
                    row.get("speech_tokens"),
                    int(row["length"]),
                    row.get("level_1"),
                    row.get("level_2"),
                    row.get("level_3"),
                    bool(row["is_annotation"]),
                )
            )

        cur.executemany(
            """
            INSERT INTO api_speech (
                sitting_id,
                index,
                speaker_id,
                timestamp,
                speech,
                speech_tokens,
                length,
                level_1,
                level_2,
                level_3,
                is_annotation
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            rows,
        )
