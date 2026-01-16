import json


def _normalize_house(house):
    """
    Accept house in the same shapes we produce elsewhere (int or code string)
    and normalize to the integer expected by the DB (0=DR, 1=DN, 2=KKDR).
    """

    if house in (0, 1, 2):
        return house

    # Allow short string codes used in payload preparation
    mapping = {"DR": 0, "DN": 1, "KKDR": 2, "DR " : 0, "DN ": 1, "KKDR ": 2}

    # Also allow full names just in case
    mapping.update(
        {
            "Dewan Rakyat": 0,
            "Dewan Negara": 1,
            "Kamar Khas Dewan Rakyat": 2,
            "Kamar Khas": 2,
        }
    )

    try:
        return mapping[str(house).strip()]
    except KeyError:
        raise ValueError(f"Unsupported house value for direct ingest: {house!r}")


def ingest_sitting_direct(payload: dict, conn):
    """
    Minimal, direct replacement for POST /api/sitting
    - Consumes payload EXACTLY as produced by prepare_db_payload
    - No Django
    - No API
    """

    # ------------------------------------------------------------------
    # 1. speech_data NORMALIZATION (MANDATORY)
    # payload["speech_data"] is a JSON STRING in your current pipeline
    # ------------------------------------------------------------------
    # Accept payload as dict or JSON string (in-memory only; no filesystem dependency).
    if isinstance(payload, str):
        payload = json.loads(payload)

    if isinstance(payload.get("speech_data"), str):
        speeches = json.loads(payload["speech_data"])
    else:
        speeches = payload["speech_data"]

    date = payload["date"]
    filename = payload["filename"]
    is_final = payload["is_final"]
    house = _normalize_house(payload["house"])  # int: 0 / 1 / 2

    with conn.cursor() as cur:

        # ------------------------------------------------------------------
        # 2. Resolve ParliamentaryCycle (same logic as backend)
        # ------------------------------------------------------------------
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

        # ------------------------------------------------------------------
        # 3. Upsert Sitting (idempotent by filename)
        # ------------------------------------------------------------------
        cur.execute(
            "SELECT sitting_id FROM api_sitting WHERE filename = %s",
            (filename,),
        )
        row = cur.fetchone()

        if row:
            sitting_id = row[0]
            cur.execute(
                """
                UPDATE api_sitting
                SET date = %s,
                    is_final = %s,
                    cycle_id = %s,
                    speech_data = %s
                WHERE sitting_id = %s
                """,
                (
                    date,
                    is_final,
                    cycle_id,
                    json.dumps(_build_nested_speech_json(speeches), ensure_ascii=False),
                    sitting_id,
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO api_sitting
                    (date, filename, is_final, cycle_id, speech_data)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING sitting_id
                """,
                (
                    date,
                    filename,
                    is_final,
                    cycle_id,
                    json.dumps(_build_nested_speech_json(speeches), ensure_ascii=False),
                ),
            )
            sitting_id = cur.fetchone()[0]

        # ------------------------------------------------------------------
        # 4. Resolve AuthorHistory (date-valid, same backend rules)
        # ------------------------------------------------------------------
        author_ids = {
            int(row["speaker"])
            for row in speeches
            if row.get("speaker") is not None
        }

        author_history_map = {}
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
                    # Prefer bounded record
                    author_history_map[author_id] = record_id

        # ------------------------------------------------------------------
        # 5. Replace speeches (DELETE + bulk INSERT)
        # ------------------------------------------------------------------
        cur.execute(
            "DELETE FROM api_speech WHERE sitting_id = %s",
            (sitting_id,),
        )

        rows = []
        for row in speeches:
            speaker = row.get("speaker")
            rows.append(
                (
                    sitting_id,
                    int(row["index"]),
                    author_history_map.get(int(speaker)) if speaker else None,
                    row["timestamp"],
                    row.get("speech"),
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


# ----------------------------------------------------------------------
# INTERNAL: exact logic moved from backend _speeches_to_json
# ----------------------------------------------------------------------
def _add_to_result(levels, data, result):
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
            new_entry = {level: []}
            current.append(new_entry)
            found = new_entry[level]
        current = found

    current.append(data)


def _build_nested_speech_json(speeches):
    result = []

    for row in speeches:
        data = {
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
        levels = [l for l in levels if l]

        _add_to_result(levels, data, result)

    return result
