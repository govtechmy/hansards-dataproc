"""
Merge author data from scraped CSV files with database CSV files.
Creates a master_author.csv with deduplicated data.
"""
import csv
import logging
import pandas as pd
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
import boto3

load_dotenv()
logger = logging.getLogger(__name__)


def get_db_connection():
    """Get PostgreSQL database connection using HANSARD_DB_URL from .env."""
    try:
        db_url = os.getenv("HANSARD_DB_URL")
        if not db_url:
            logger.warning("HANSARD_DB_URL not found in environment variables")
            return None
        
        conn = psycopg2.connect(db_url)
        return conn
    except Exception as e:
        logger.error(f"Could not connect to database: {e}")
        return None


def load_area_mapping():
    """Load area_id to area_name and area_state mapping from PostgreSQL."""
    logger.info("Loading area mapping from PostgreSQL...")
    
    conn = get_db_connection()
    if not conn:
        return {}
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT id, name, state
            FROM api_area
        """)
        
        rows = cursor.fetchall()
        area_map = {}
        
        for row in rows:
            area_map[row['id']] = {
                'name': row['name'],
                'state': row['state']
            }
        
        logger.info(f"  - Loaded {len(area_map)} area mappings from database")
        cursor.close()
        conn.close()
        
        return area_map
        
    except Exception as e:
        logger.error(f"ERROR loading area mapping: {e}")
        if conn:
            conn.close()
        return {}


def load_db_data_from_postgres():
    """Load existing database author and history data from PostgreSQL."""
    logger.info("Loading data from PostgreSQL database...")
    
    conn = get_db_connection()
    if not conn:
        logger.error("Could not connect to database")
        return None, None
    
    try:
        # Load authors from api_author table
        logger.info("  - Fetching api_author table...")
        db_authors = pd.read_sql_query("""
            SELECT new_author_id, name, birth_year, ethnicity, sex
            FROM api_author
        """, conn)
        # Add full_name column as None since it doesn't exist in the table
        db_authors['full_name'] = None
        logger.info(f"    Loaded {len(db_authors)} authors from database")
        
        # Load author history from api_author_history table
        logger.info("  - Fetching api_author_history table...")
        db_history = pd.read_sql_query("""
            SELECT record_id, author_id, party, area_id, exec_posts, service_posts, start_date, end_date
            FROM api_author_history
        """, conn)
        logger.info(f"    Loaded {len(db_history)} history records from database")
        
        conn.close()
        
        return db_authors, db_history
        
    except Exception as e:
        logger.error(f"ERROR loading data from PostgreSQL: {e}")
        if conn:
            conn.close()
        return None, None


def normalize_name(name):
    """Normalize name for comparison."""
    if pd.isna(name) or not name:
        return ""
    return str(name).strip().upper()


def normalize_date(date_str):
    """Normalize date to DD/MM/YYYY format."""
    if pd.isna(date_str) or not date_str:
        return None
    
    date_str = str(date_str).strip()
    
    if not date_str:
        return None
    
    # Already in DD/MM/YYYY or similar format with slashes
    if "/" in date_str:
        parts = date_str.split("/")
        if len(parts) == 3:
            day, month, year = parts[0], parts[1], parts[2]
            # Handle 2-digit years
            if len(year) == 2:
                year = f"19{year}" if int(year) > 50 else f"20{year}"
            return f"{day.zfill(2)}/{month.zfill(2)}/{year}"
    
    # Date with hyphens
    elif "-" in date_str:
        parts = date_str.split("-")
        if len(parts) == 3:
            # YYYY-MM-DD format
            return f"{parts[2].zfill(2)}/{parts[1].zfill(2)}/{parts[0]}"
        elif len(parts) == 2:
            # YYYY-MM format - use 01 as day for start dates, last day for end dates
            # We'll use 01 as default here
            return f"01/{parts[1].zfill(2)}/{parts[0]}"
    
    # Just a year (YYYY)
    else:
        if date_str.isdigit() and len(date_str) == 4:
            # Default to 01/01 for start dates, this can be adjusted if needed
            return f"01/01/{date_str}"
    
    return date_str  # Return as-is if format not recognized


def load_scraped_data(scraped_author_file, scraped_author_history_file):
    """Load scraped author and history data."""
    logger.info("Loading scraped files...")
    
    # Load scraped authors
    scraped_authors = pd.read_csv(scraped_author_file)
    logger.info(f"  - Loaded {len(scraped_authors)} authors from scrape")
    
    # Load scraped author history
    scraped_history = pd.read_csv(scraped_author_history_file)
    logger.info(f"  - Loaded {len(scraped_history)} history records from scrape")
    
    return scraped_authors, scraped_history


def build_name_to_author_map(db_authors):
    """Build a mapping from normalized names to author IDs from database."""
    name_map = {}
    
    for _, row in db_authors.iterrows():
        author_id = row.get('new_author_id') or row.get('author_id')
        
        # Try full_name first, then name
        full_name = normalize_name(row.get('full_name'))
        name = normalize_name(row.get('name'))
        
        if full_name:
            name_map[full_name] = author_id
        if name and name != full_name:
            name_map[name] = author_id
    
    logger.info(f"Built name mapping with {len(name_map)} entries")
    return name_map


def create_master_csv(db_authors, db_history, scraped_authors, scraped_history, area_map, output_file):
    """Create master CSV by merging database and scraped data."""
    
    logger.info("Building master author dataset...")
    
    # Build name mapping from database
    name_map = build_name_to_author_map(db_authors)
    
    # Build lookup key for db_history: (author_id, start_date, end_date) -> (area_id, record_id)
    db_history_lookup = {}
    for _, row in db_history.iterrows():
        record_id = row.get('record_id')
        author_id = row.get('author_id') or row.get('new_author_id')
        start_date = normalize_date(row.get('start_date'))
        end_date = normalize_date(row.get('end_date'))
        area_id = row.get('area_id')
        
        key = (author_id, start_date, end_date)
        db_history_lookup[key] = {'area_id': area_id, 'record_id': record_id}
    
    logger.info(f"Built db_history lookup with {len(db_history_lookup)} entries")
    
    master_rows = []
    used_db_authors = set()
    
    # First, process all database data
    logger.info("Processing database records...")
    for _, hist_row in db_history.iterrows():
        author_id = hist_row.get('author_id') or hist_row.get('new_author_id')
        
        # Find author details
        author_row = db_authors[
            (db_authors['new_author_id'] == author_id) | 
            (db_authors.get('author_id', pd.Series()) == author_id)
        ]
        
        if len(author_row) == 0:
            continue
            
        author_row = author_row.iloc[0]
        used_db_authors.add(author_id)
        
        # Get area_id, record_id and lookup area details
        record_id = hist_row.get('record_id')
        area_id = hist_row.get('area_id')
        area_info = area_map.get(area_id, {}) if area_id else {}
        exec_posts = hist_row.get('exec_posts')
        service_posts = hist_row.get('service_posts')
        
        start_date = normalize_date(hist_row.get('start_date'))
        end_date = normalize_date(hist_row.get('end_date'))
        
        master_rows.append({
            'record_id': record_id,
            'author_id': author_id,
            'author_name': author_row.get('name') or author_row.get('full_name'),
            'party': hist_row.get('party'),
            'area_id': area_id,
            'area_name': area_info.get('name'),
            'area_state': area_info.get('state'),
            'exec_posts': exec_posts,
            'service_posts': service_posts,
            'start_date': start_date,
            'end_date': end_date,
        })
    
    logger.info(f"  - Added {len(master_rows)} records from database")
    
    # Now process scraped data, checking for duplicates
    logger.info("Processing scraped records...")
    new_records = 0
    duplicate_records = 0
    
    for _, hist_row in scraped_history.iterrows():
        scraped_author_id = hist_row.get('author_id')
        
        # Find author details from scraped data
        author_row = scraped_authors[
            scraped_authors['new_author_id'] == scraped_author_id
        ]
        
        if len(author_row) == 0:
            continue
            
        author_row = author_row.iloc[0]
        
        # Check if this author already exists in database
        full_name = normalize_name(author_row.get('full_name'))
        name = normalize_name(author_row.get('name'))
        
        db_author_id = None
        if full_name in name_map:
            db_author_id = name_map[full_name]
        elif name in name_map:
            db_author_id = name_map[name]
        
        if db_author_id is not None:
            duplicate_records += 1
            continue
        
        # New author not in database
        new_records += 1
        
        start_date = normalize_date(hist_row.get('start_date'))
        end_date = normalize_date(hist_row.get('end_date'))
        
        # Try to find area_id and record_id from db_history by matching author_id, start_date, end_date
        lookup_key = (scraped_author_id, start_date, end_date)
        history_info = db_history_lookup.get(lookup_key, {})
        record_id = history_info.get('record_id')
        area_id = history_info.get('area_id')
        
        # Get area details and other fields from scraped history
        area_info = area_map.get(area_id, {}) if area_id else {}
        exec_posts = hist_row.get('exec_posts')
        service_posts = hist_row.get('service_posts')
        
        master_rows.append({
            'record_id': record_id,
            'author_id': scraped_author_id,
            'author_name': author_row.get('name') or author_row.get('full_name'),
            'party': hist_row.get('party'),
            'area_id': area_id,
            'area_name': area_info.get('name'),
            'area_state': area_info.get('state'),
            'exec_posts': exec_posts,
            'service_posts': service_posts,
            'start_date': start_date,
            'end_date': end_date,
        })
    
    logger.info(f"  - Added {new_records} new records from scrape")
    logger.info(f"  - Skipped {duplicate_records} duplicate records")
    
    # Write master CSV
    logger.info(f"Writing master CSV to {output_file}...")
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['record_id', 'author_id', 'author_name', 'party', 'area_id', 'area_name', 'area_state', 'exec_posts', 'service_posts', 'start_date', 'end_date']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(master_rows)
    
    logger.info(f"Master CSV created with {len(master_rows)} total records")
    
    return master_rows


def main():
    # Define file paths for scraped data
    SCRAPED_BASE_DIR = Path("scripts/ahli_parlimen")
    SCRAPED_OUTPUTS_DIR = SCRAPED_BASE_DIR / "outputs"
    
    # Scraped files
    SCRAPED_AUTHOR = SCRAPED_OUTPUTS_DIR / "author.csv"
    SCRAPED_HISTORY = SCRAPED_OUTPUTS_DIR / "author_history.csv"

    # Output directory for merged data (relative to script location)
    SCRIPT_DIR = Path(__file__).parent
    OUTPUT_DIR = SCRIPT_DIR / "outputs"
    OUTPUT_DIR.mkdir(exist_ok=True)  # Create outputs directory if it doesn't exist
    
    # Output file
    MASTER_CSV = OUTPUT_DIR / "author_history.csv"
    
    # Check if scraped files exist
    logger.info("Checking for required scraped files...")
    for file_path in [SCRAPED_AUTHOR, SCRAPED_HISTORY]:
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            logger.error("Please ensure all required files are present.")
            return
        logger.info(f"  {file_path}")
    
    # Load data from PostgreSQL database
    db_authors, db_history = load_db_data_from_postgres()
    if db_authors is None or db_history is None:
        logger.error("Failed to load data from PostgreSQL database")
        return
    
    # Load scraped data
    scraped_authors, scraped_history = load_scraped_data(SCRAPED_AUTHOR, SCRAPED_HISTORY)
    
    # Load area mapping from PostgreSQL
    area_map = load_area_mapping()
    
    # Create master CSV
    master_rows = create_master_csv(
        db_authors, 
        db_history, 
        scraped_authors, 
        scraped_history,
        area_map,
        MASTER_CSV
    )
    
    # Upload to S3
    logger.info("Uploading to S3...")
    
    try:
        s3_bucket = os.getenv("S3_DATAPROC_BUCKET")
        aws_region = os.getenv("AWS_REGION", "ap-southeast-5")
        s3_client = boto3.client("s3", region_name=aws_region)
        s3_key = "canonical/preprocessing/master/author_history.csv"
        
        logger.info(f"Uploading to s3://{s3_bucket}/{s3_key}...")
        s3_client.upload_file(
            str(MASTER_CSV),
            s3_bucket,
            s3_key
        )
        logger.info(f"Successfully uploaded to S3: s3://{s3_bucket}/{s3_key}")
    
    except Exception as e:
        logger.error(f"Uploading to S3: {e}")
        logger.warning("File saved locally but S3 upload failed")
    
    logger.info("MERGE COMPLETE!")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    main()

