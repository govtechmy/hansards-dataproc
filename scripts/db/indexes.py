import psycopg
from psycopg import sql
from hansards_pipelines import settings
import argparse
import os

import logging
logger = logging.getLogger(__name__)


def add_index(conn, table_name, columns, index_name=None, unique=False, method="btree", concurrently=False):
    """
    Add an index to a table, creating it if it doesn't exist or recreating if it doesn't match.
    """
    if not index_name:
        col_str = "_".join([c.replace("(", "").replace(")", "") for c in columns])
        index_name = f"idx_{table_name}_{col_str}"

    original_autocommit = conn.autocommit
    if concurrently:
        conn.autocommit = True

    try:
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
                desired_column_defs = []
                for c in columns:
                    if isinstance(c, dict):
                        col_name, op_class = list(c.items())[0]
                        desired_column_defs.append(f"{col_name} {op_class}")
                    else:
                        desired_column_defs.append(c)
            else:
                desired_column_defs = [columns]

            if existing:
                existing_name, existing_method, existing_unique, existing_columns = existing

                normalized_existing = [col.strip() for col in existing_columns]
                normalized_desired = [col.strip() for col in desired_column_defs]

                if (existing_method == method and 
                    existing_unique == unique and 
                    normalized_existing == normalized_desired):
                    logger.info(f"[SKIP] {table_name}.{index_name} already matches")
                    return

                logger.warning(
                    f"[DROP] {table_name}.{index_name} - "
                    f"method={existing_method} (want {method}), "
                    f"unique={existing_unique} (want {unique}), "
                    f"columns={normalized_existing} (want {normalized_desired})"
                )
                
                if concurrently:
                    drop_sql = sql.SQL("DROP INDEX CONCURRENTLY IF EXISTS {}")
                else:
                    drop_sql = sql.SQL("DROP INDEX IF EXISTS {}")
                cur.execute(drop_sql.format(sql.Identifier(index_name)))

            allowed_methods = {"btree", "gin", "gist", "hash", "brin", "spgist"}
            if method not in allowed_methods:
                raise ValueError(f"Unsupported index method: {method}")
            
            column_sql_parts = []
            for col_def in desired_column_defs:
                parts = col_def.split(None, 1)  
                if len(parts) == 2:
                    col_name, op_class = parts
                    column_sql_parts.append(
                        sql.SQL(" ").join([sql.Identifier(col_name), sql.SQL(op_class)])
                    )
                else:
                    column_sql_parts.append(sql.Identifier(col_def))
            
            columns_sql = sql.SQL(", ").join(column_sql_parts)
            unique_sql = sql.SQL("UNIQUE ") if unique else sql.SQL("")
            concurrent_sql = sql.SQL("CONCURRENTLY ") if concurrently else sql.SQL("")
            
            create_sql = sql.SQL(
                "CREATE {unique}INDEX {concurrently}{index_name} "
                "ON {table_name} USING {method} ({columns})"
            ).format(
                unique=unique_sql,
                concurrently=concurrent_sql,
                index_name=sql.Identifier(index_name),
                table_name=sql.Identifier(table_name),
                method=sql.SQL(method),
                columns=columns_sql,
            )
            
            cur.execute(create_sql)
                
            logger.info(f"[CREATE] {table_name}.{index_name} created{' (concurrently)' if concurrently else ''}")
    finally:
        if concurrently:
            conn.autocommit = original_autocommit
def create_index_api_author(conn, concurrently=False):
    """
    Create indexes for api_author table.
    
    Table schema:
    - new_author_id INTEGER PRIMARY KEY 
    - name VARCHAR(255) NOT NULL
    """
    table = "api_author"

    add_index(conn, table, ["name"], index_name="idx_api_author_name", concurrently=concurrently)


def create_index_api_author_history(conn, concurrently=False):
    """
    Create indexes for api_author_history table.
    
    Args:
        conn: Database connection
        concurrently: If True, use CREATE INDEX CONCURRENTLY to avoid blocking writes
    """
    table = "api_author_history"
    
    add_index(conn, table, ["author_id"], index_name="idx_api_author_history_author_id", concurrently=concurrently)
    
    add_index(conn, table, ["party"], index_name="idx_api_author_history_party", concurrently=concurrently)
    
    add_index(conn, table, ["area_id"], index_name="idx_api_author_history_area_id", concurrently=concurrently)
    
    add_index(conn, table, ["start_date"], index_name="idx_api_author_history_start_date", concurrently=concurrently)
    add_index(conn, table, ["end_date"], index_name="idx_api_author_history_end_date", concurrently=concurrently)
    
    add_index(
        conn, 
        table, 
        ["author_id", "start_date", "end_date"], 
        index_name="idx_api_author_history_author_dates",
        concurrently=concurrently
    )


def create_index_api_area(conn, concurrently=False):
    """
    Create indexes for api_area table (constituencies).
    
    Args:
        conn: Database connection
        concurrently: If True, use CREATE INDEX CONCURRENTLY to avoid blocking writes
    """
    table = "api_area"
    
    add_index(conn, table, ["name"], index_name="idx_api_area_name", concurrently=concurrently)

    add_index(conn, table, ["state"], index_name="idx_api_area_state", concurrently=concurrently)
    
    add_index(conn, table, ["state", "name"], index_name="idx_api_area_state_name", concurrently=concurrently)


def create_index_api_parliamentary_cycle(conn, concurrently=False):
    """
    Create indexes for api_parliamentary_cycle table.
    """
    table = "api_parliamentary_cycle"
    
    add_index(conn, table, ["house"], index_name="idx_api_parliamentary_cycle_house", concurrently=concurrently)
    
    add_index(conn, table, ["term"], index_name="idx_api_parliamentary_cycle_term", concurrently=concurrently)
    
    add_index(conn, table, ["session"], index_name="idx_api_parliamentary_cycle_session", concurrently=concurrently)
    
    add_index(conn, table, ["meeting"], index_name="idx_api_parliamentary_cycle_meeting", concurrently=concurrently)
    
    add_index(
        conn, 
        table, 
        ["house", "term"], 
        index_name="idx_api_parliamentary_cycle_house_term",
        concurrently=concurrently
    )
    
    add_index(
        conn, 
        table, 
        ["house", "term", "session"], 
        index_name="idx_api_parliamentary_cycle_house_term_session",
        concurrently=concurrently
    )
    
    add_index(
        conn, 
        table, 
        ["house", "term", "session", "meeting"], 
        index_name="idx_api_parliamentary_cycle_full",
        concurrently=concurrently
    )

    add_index(
        conn,
        table,
        ["house", "start_date", "end_date"],
        index_name="idx_api_parliamentary_cycle_house_date_range",
        concurrently=concurrently
    )


def main(concurrently=None):
    """
    Main entry point for creating/updating database indexes.
    """
    if concurrently is None:
        env_value = os.getenv("INDEX_CONCURRENTLY", "false").lower()
        concurrently = env_value in ('true', '1', 'yes')
    
    db_url = settings.HANSARD_DB_URL
    
    if not db_url:
        logger.error("HANSARD_DB_URL not set in environment variables")
        return
    
    logger.info("Connecting to database...")
    
    if concurrently:
        logger.info("Mode: CONCURRENTLY (safe for production, will not block writes)")
    else:
        logger.info("Mode: STANDARD (faster but may briefly block writes on large tables)")
    
    try:
        with psycopg.connect(db_url) as conn:
            logger.info("Connected successfully\n")
            logger.info("Creating indexes for api_author")
            create_index_api_author(conn, concurrently=concurrently)
            
            logger.info("\n" + "="*60)
            logger.info("Creating indexes for api_author_history")
            create_index_api_author_history(conn, concurrently=concurrently)
            
            logger.info("\n" + "="*60)
            logger.info("Creating indexes for api_area")
            create_index_api_area(conn, concurrently=concurrently)
            
            logger.info("\n" + "="*60)
            logger.info("Creating indexes for api_parliamentary_cycle")
            create_index_api_parliamentary_cycle(conn, concurrently=concurrently)
            
            # Only commit if not using concurrently (CONCURRENTLY uses autocommit)
            if not concurrently:
                conn.commit()
            
            logger.info("\n" + "="*60)
            logger.info("All indexes created successfully")
            
    except Exception as e:
        logger.error(f"Failed to create indexes: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    parser = argparse.ArgumentParser(
        description="Create and manage database indexes for hansards tables",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--concurrently',
        action='store_true',
        help='Use CREATE INDEX CONCURRENTLY to avoid blocking writes (recommended for production)'
    )
    
    args = parser.parse_args()
    main(concurrently=args.concurrently if args.concurrently else None)
