import psycopg
import logging
from hansards_pipelines import settings

logger = logging.getLogger(__name__)


QUERIES = [
    # api_area
    "CREATE UNIQUE INDEX IF NOT EXISTS api_area_pkey ON api_area(id)",

    # api_attendance
    "CREATE INDEX IF NOT EXISTS api_attendance_author_id_a6bb5f1a ON api_attendance(author_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS api_attendance_author_id_sitting_id_153d7ce1_uniq ON api_attendance(author_id, sitting_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS api_attendance_pkey ON api_attendance(id)",
    "CREATE INDEX IF NOT EXISTS api_attendance_sitting_id_5042d7b6 ON api_attendance(sitting_id)",

    # api_author
    "CREATE UNIQUE INDEX IF NOT EXISTS api_author_pkey ON api_author(new_author_id)",
    "CREATE INDEX IF NOT EXISTS idx_api_author_name ON api_author(name)",

    # api_author_history
    "CREATE UNIQUE INDEX IF NOT EXISTS author_history_pkey ON api_author_history(record_id)",

    # api_parliamentary_cycle
    "CREATE UNIQUE INDEX IF NOT EXISTS parliamentary_cycle_pkey ON api_parliamentary_cycle(cycle_id)",

    # api_sitting
    "CREATE UNIQUE INDEX IF NOT EXISTS sitting_filename_fec75e75_uniq ON api_sitting(filename)",
    "CREATE UNIQUE INDEX IF NOT EXISTS sitting_pkey ON api_sitting(sitting_id)",

    # api_speech
    "CREATE INDEX IF NOT EXISTS api_speech_sitting_id_4dc75622 ON api_speech(sitting_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS api_speech_sitting_id_index_23fbb42b_uniq ON api_speech(sitting_id, index)",
    "CREATE INDEX IF NOT EXISTS api_speech_speaker_id_8b151e1f ON api_speech(speaker_id)",
    "CREATE INDEX IF NOT EXISTS api_speech_speech__c0087e_gin ON api_speech USING gin(speech_vector)",
    "CREATE UNIQUE INDEX IF NOT EXISTS speech_pkey ON api_speech(speech_id)",
]


def main():
    db_url = settings.HANSARD_DB_URL

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            for q in QUERIES:
                logger.info(q)
                cur.execute(q)

        conn.commit()

    logger.info("Indexes ensured successfully.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()