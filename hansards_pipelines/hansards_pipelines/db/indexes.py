"""
python -m hansards_pipelines.db.indexes
"""

import psycopg
from psycopg import sql
from hansards_pipelines import settings

import logging
logger = logging.getLogger(__name__)


def add_index(conn, table_name, columns, index_name=None, unique=False, method="btree"):
    if not index_name:
        col_str = "_".join([c.replace("(", "").replace(")", "") for c in columns])
        index_name = f"idx_{table_name}_{col_str}"

    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                i.relname as index_name,
                am.amname as index_method,
                ix.indisunique as is_unique,
                ARRAY(
                    SELECT pg_get_indexdef(ix.indexrelid, k + 1, true)
                    FROM generate_subscripts(ix.indkey, 1) as k
                    ORDER BY k
                ) as column_names
            FROM pg_class t
            JOIN pg_index ix ON t.oid = ix.indrelid
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_am am ON i.relam = am.oid
            WHERE t.relname = %s AND i.relname = %s
        """, (table_name, index_name))

        existing = cur.fetchone()

        if isinstance(columns, list):
            if all(isinstance(c, str) for c in columns):
                desired_columns = columns
            else:
                desired_columns = [list(c.keys())[0] if isinstance(c, dict) else c for c in columns]
        else:
            desired_columns = [columns]

        if existing:
            existing_name, existing_method, existing_unique, existing_columns = existing

            # Check if everything matches
            if (existing_method == method and 
                existing_unique == unique and 
                existing_columns == desired_columns):
                logger.info(f"[SKIP] {table_name}.{index_name} already matches")
                return

            # Index exists but doesn't match -> drop it
            logger.warning(
                f"[DROP] {table_name}.{index_name} - "
                f"method={existing_method} (want {method}), "
                f"unique={existing_unique} (want {unique}), "
                f"columns={existing_columns} (want {desired_columns})"
            )
            cur.execute(sql.SQL("DROP INDEX IF EXISTS {}").format(sql.Identifier(index_name)))

        # Create the index
        unique_clause = "UNIQUE" if unique else ""
        
        # Build column list with optional operators
        if isinstance(columns, list) and any(isinstance(c, dict) for c in columns):
            col_parts = []
            for c in columns:
                if isinstance(c, dict):
                    col_name, op_class = list(c.items())[0]
                    col_parts.append(f"{col_name} {op_class}")
                else:
                    col_parts.append(c)
            col_str = ", ".join(col_parts)
        else:
            col_str = ", ".join(desired_columns)

        create_sql = f"""
            CREATE {unique_clause} INDEX {index_name}
            ON {table_name} USING {method} ({col_str})
        """
        
        cur.execute(create_sql)
        conn.commit()
        logger.info(f"[CREATE] {table_name}.{index_name} created")


def create_index_api_author(conn):
    """
    Create indexes for api_author table.
    
    Table schema:
    - new_author_id INTEGER PRIMARY KEY 
    - name VARCHAR(255) NOT NULL
    """
    table = "api_author"


    add_index(conn, table, ["name"], index_name="idx_api_author_name")


def create_index_api_author_history(conn):
    """
    Create indexes for api_author_history table.
    """
    table = "api_author_history"
    
    add_index(conn, table, ["author_id"], index_name="idx_api_author_history_author_id")
    
    add_index(conn, table, ["party"], index_name="idx_api_author_history_party")
    
    add_index(conn, table, ["area_id"], index_name="idx_api_author_history_area_id")
    
    add_index(conn, table, ["start_date"], index_name="idx_api_author_history_start_date")
    add_index(conn, table, ["end_date"], index_name="idx_api_author_history_end_date")
    
    add_index(
        conn, 
        table, 
        ["author_id", "start_date", "end_date"], 
        index_name="idx_api_author_history_author_dates"
    )


def create_index_api_area(conn):
    """
    Create indexes for api_area table (constituencies).
    """
    table = "api_area"
    
    add_index(conn, table, ["name"], index_name="idx_api_area_name")

    add_index(conn, table, ["state"], index_name="idx_api_area_state")
    
    add_index(conn, table, ["state", "name"], index_name="idx_api_area_state_name")


def create_index_api_parliamentary_cycle(conn):
    """
    Create indexes for api_parliamentary_cycle table.
    """
    table = "api_parliamentary_cycle"
    
    add_index(conn, table, ["house"], index_name="idx_api_parliamentary_cycle_house")
    
    add_index(conn, table, ["term"], index_name="idx_api_parliamentary_cycle_term")
    
    add_index(conn, table, ["session"], index_name="idx_api_parliamentary_cycle_session")
    
    add_index(conn, table, ["meeting"], index_name="idx_api_parliamentary_cycle_meeting")
    
    add_index(
        conn, 
        table, 
        ["house", "term"], 
        index_name="idx_api_parliamentary_cycle_house_term"
    )
    
    add_index(
        conn, 
        table, 
        ["house", "term", "session"], 
        index_name="idx_api_parliamentary_cycle_house_term_session"
    )
    
    add_index(
        conn, 
        table, 
        ["house", "term", "session", "meeting"], 
        index_name="idx_api_parliamentary_cycle_full"
    )


def main():
    """
    Main entry point for creating/updating database indexes.
    """
    db_url = settings.HANSARD_DB_URL
    
    if not db_url:
        logger.error("HANSARD_DB_URL not set in environment variables")
        return
    
    logger.info("Connecting to database...")
    
    try:
        with psycopg.connect(db_url) as conn:
            logger.info("Connected successfully\n")
            logger.info("Creating indexes for api_author")
            create_index_api_author(conn)
            
            logger.info("\n" + "="*60)
            logger.info("Creating indexes for api_author_history")
            create_index_api_author_history(conn)
            
            logger.info("\n" + "="*60)
            logger.info("Creating indexes for api_area")
            create_index_api_area(conn)
            
            logger.info("\n" + "="*60)
            logger.info("Creating indexes for api_parliamentary_cycle")
            create_index_api_parliamentary_cycle(conn)
            
    except Exception as e:
        logger.error(f"Failed to create indexes: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
