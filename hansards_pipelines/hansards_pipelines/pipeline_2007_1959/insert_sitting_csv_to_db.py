"""
# example commands
# python prepare_payload.py --prefix dewannegara --start-year 1991 --end-year 1991
# python prepare_payload.py --prefix dewannegara --filename dn_1991-02-18.csv
"""

import argparse
import re
import boto3
import json
import logging
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime
from typing import Tuple, Dict, Any
import psycopg2
from psycopg2.extras import DictCursor
import warnings
from botocore.config import Config
from pandas.errors import SettingWithCopyWarning

from direct_sitting_ingest import ingest_sitting_to_db
from utils.text_utils import house_mapper, get_sitting_object, preprocess_malaya
from author_matching import perform_author_matching

from settings import S3_TEXTRACT_BUCKET, DEV_API_URL, AWS_REGION, HANSARD_DB_URL

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
ANNOTATION_KEYWORD = "ANNOTATION"
SKIPPED_NO_SPEECH_ERROR = "SKIPPED_NO_SPEECH"
REQUIRED_COLUMNS = ["speech", "author", "timestamp"]
DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")

# S3 configuration with retry logic
S3_CONFIG = Config(
    retries={'max_attempts': 3, 'mode': 'adaptive'},
    connect_timeout=10,
    read_timeout=60
)

session = boto3.Session()
warnings.filterwarnings("ignore", category=SettingWithCopyWarning)
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    module="malaya"
)


def get_db_connection():
    """Create and return a database connection."""
    if not HANSARD_DB_URL:
        raise ValueError("HANSARD_DB_URL environment variable not set")
    return psycopg2.connect(HANSARD_DB_URL)

def prepare_db_payload(df_speech: pd.DataFrame, prefix: str, date_str: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Prepares the payload for database insertion from the speech DataFrame.
    
    Args:
        df_speech: DataFrame containing speech data with columns: speech, author, timestamp, etc.
        prefix: House prefix (dewanrakyat, dewannegara, or kamarkhas)
        date_str: Date string in YYYY-MM-DD format
    
    Returns:
        Tuple of (processed DataFrame, payload dictionary)
    
    Raises:
        ValueError: If no valid speeches remain after processing
        KeyError: If required columns are missing from DataFrame
    """
    # Validate required columns
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df_speech.columns]
    if missing_cols:
        raise KeyError(f"Missing required columns: {missing_cols}")

    # ---- Sitting metadata ----
    pdf_key = f"{house_mapper.to_code(prefix).upper()}-{datetime.strptime(date_str, '%Y-%m-%d').strftime('%d%m%Y')}"
    sitting_obj = get_sitting_object(pdf_key)

    # ---- Metadata ----
    df_speech["index"] = df_speech.reset_index().index
    df_speech["sitting"] = sitting_obj["proper_date_str"]

    # ---- Core fields ----
    df_speech["author"] = df_speech["author"].where(pd.notna(df_speech["author"]), None)
    df_speech["timestamp"] = df_speech["timestamp"].fillna("")
    df_speech["author_id"] = df_speech.get("author_id") if "author_id" in df_speech.columns else None

    # ---- Annotation flag ----
    df_speech["is_annotation"] = (df_speech["author"].notna() & (df_speech["author"].str.upper() == ANNOTATION_KEYWORD))

    # ---- Speech processing (ALWAYS here) ----
    df_speech["proc_speech"] = df_speech["speech"].fillna("")
    df_speech["speech_tokens"] = df_speech["proc_speech"].apply(
        lambda x: preprocess_malaya(x) or []
    )

    # ---- Remove empty speeches ----
    df_speech = df_speech[df_speech["speech_tokens"].str.len() > 0]
    if df_speech.empty:
        raise ValueError(SKIPPED_NO_SPEECH_ERROR)

    # ---- Author matching ----
    r = requests.get(f"{DEV_API_URL}/api/author-history", timeout=30)
    r.raise_for_status()
    df_author_history = pd.DataFrame(r.json())
    if not df_author_history.empty:
        df_author_history["area"] = df_author_history.area_name.str[5:]

    r = requests.get(f"{DEV_API_URL}/api/author", timeout=30)
    r.raise_for_status()
    df_author = pd.DataFrame(r.json())

    df_speech = perform_author_matching(
        df_speech,
        df_author,
        df_author_history,
        logger,
    )

    # sanity check - proves matching ran
    assert "author_id" in df_speech.columns

    # ---- Token length ----
    df_speech["length"] = df_speech["speech_tokens"].apply(len)

    # ---- Level cleanup ----
    for col in ["level_1", "level_2", "level_3"]:
        if col not in df_speech.columns:
            df_speech[col] = None
        else:
            df_speech[col] = df_speech[col].apply(
                lambda x: x if pd.notna(x) and str(x).strip() else None
            )
    df_speech = df_speech.where(pd.notna(df_speech), None)

    speech_data = df_speech[
        [
            "index",
            "author",
            "author_id",
            "timestamp",
            "speech",
            "proc_speech",
            "speech_tokens",
            "length",
            "level_1",
            "level_2",
            "level_3",
            "is_annotation",
            "sitting",
        ]
    ].rename(columns={"author_id": "speaker"}).to_dict(orient="records")

    payload = {
        "date": sitting_obj["proper_date_str"],
        "filename": sitting_obj["renamed_filename"],
        "is_final": False,
        "house": sitting_obj["house_display"],
        "speech_data": json.dumps(speech_data),
    }

    return df_speech, payload


# def insert_to_db(payload: Dict[str, Any]) -> bool:
#     """
#     Insert payload to database via API.
    
#     Args:
#         payload: Dictionary containing sitting data and speeches
    
#     Returns:
#         True if insertion successful, False otherwise
#     """
#     logger.info("Sending request to backend...")
#     try:
#         response = requests.post(
#             f"{DEV_API_URL}/api/sitting/",
#             json=payload,
#             timeout=30
#         )

#         try:
#             response_data = response.json()
#         except json.JSONDecodeError:
#             logger.warning("Response was not valid JSON: %s", response.text)
#             response_data = {}

#         if response.status_code == 201:
#             if "warning" in response_data:
#                 logger.warning("Data integrity warning: %s", response_data['warning'])
#             elif "speech_errors" in response_data:
#                 logger.warning("Speech errors: %s", response_data['speech_errors'])
#             logger.info("✅ Inserted to DB")
#             return True
#         else:
#             response.raise_for_status()
#             return False

#     except requests.exceptions.Timeout:
#         logger.error("Request timeout when inserting to database")
#         return False
#     except requests.exceptions.HTTPError as e:
#         resp = e.response
#         if resp is not None:
#             logger.error("Failed to insert: %s - %s", resp.status_code, resp.text)
#         else:
#             logger.error("Failed to insert due to HTTP error: %s", str(e))
#         return False
#     except requests.exceptions.RequestException as e:
#         logger.error("Request error: %s", str(e))
#         return False

def insert_to_db(payload):
    logger.info("Inserting directly into database...")

    conn = None
    try:
        conn = get_db_connection()
        ingest_sitting_to_db(payload, conn)
        conn.commit()
        logger.info("✅ Inserted to DB")
        return True

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error("Failed to insert to DB: %s", str(e))
        raise

    finally:
        if conn:
            conn.close()

def process_and_insert(prefix: str, key: str, date_str: str) -> bool:
    """
    Process a single CSV file from S3 and insert to database.
    
    Args:
        prefix: House prefix (dewanrakyat, dewannegara, or kamarkhas)
        key: S3 object key for the CSV file
        date_str: Date string in YYYY-MM-DD format
    
    Returns:
        True if processing and insertion successful, False otherwise
    """
    s3 = session.client("s3", region_name=AWS_REGION, config=S3_CONFIG)

    logger.info("Processing: %s", key)
    try:
        obj = s3.get_object(Bucket=S3_TEXTRACT_BUCKET, Key=key)
        df_speech = pd.read_csv(BytesIO(obj["Body"].read()))
        df_speech, payload = prepare_db_payload(df_speech, prefix, date_str)
        
        return insert_to_db(payload)
    except Exception as e:
        logger.error("Error processing %s: %s", key, str(e))
        raise


def run_batch(prefix: str, start_year: int, end_year: int) -> Dict[str, int]:
    """
    Process multiple CSV files from S3 within a year range.
    
    Args:
        prefix: House prefix (dewanrakyat, dewannegara, or kamarkhas)
        start_year: Starting year (inclusive)
        end_year: Ending year (inclusive)
    
    Returns:
        Dictionary with counts of successful, skipped, and failed operations
    """
    s3 = session.client("s3", region_name=AWS_REGION, config=S3_CONFIG)
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=S3_TEXTRACT_BUCKET, Prefix=f"{prefix}/")

    all_files = []
    for page in pages:
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".csv"):
                continue

            match = DATE_PATTERN.search(key)
            if not match:
                continue

            date_str = match.group(1)
            year = int(date_str[:4])
            if start_year <= year <= end_year:
                all_files.append((key, date_str))

    logger.info("Running batch processing. Total CSVs: %d", len(all_files))

    success = failed = skipped = 0

    for key, date_str in all_files:
        try:
            process_and_insert(prefix, key, date_str)
            success += 1
        except ValueError as ve:
            if str(ve) == SKIPPED_NO_SPEECH_ERROR:
                skipped += 1
                logger.warning("SKIPPED (no speech): %s", key)
            else:
                failed += 1
                logger.error("Failed: %s - %s", key, str(ve))
        except KeyError as ke:
            failed += 1
            logger.error("Missing columns in %s: %s", key, str(ke))
        except Exception as e:
            failed += 1
            logger.error("Failed: %s - %s", key, str(e))

    logger.info("========== SUMMARY ==========")
    logger.info("Successful : %d", success)
    logger.info("Skipped    : %d", skipped)
    logger.info("Failed     : %d", failed)
    
    return {"success": success, "skipped": skipped, "failed": failed}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process Hansard speeches from S3 and insert to database"
    )
    parser.add_argument(
        "--prefix",
        required=True,
        choices=["dewanrakyat", "dewannegara", "kamarkhas"],
        help="House prefix for the Hansard documents"
    )
    parser.add_argument(
        "--filename",
        type=str,
        help="Process a single CSV file (e.g., dr_1987-10-29.csv)"
    )
    parser.add_argument(
        "--start-year",
        type=int,
        help="Batch mode start year (inclusive)"
    )
    parser.add_argument(
        "--end-year",
        type=int,
        help="Batch mode end year (inclusive)"
    )

    args = parser.parse_args()

    try:
        if args.filename:
            match = DATE_PATTERN.search(args.filename)
            if not match:
                raise ValueError("Filename must contain date YYYY-MM-DD")

            date_str = match.group(1)
            key = f"{args.prefix}/{args.filename}"
            success = process_and_insert(args.prefix, key, date_str)
            if not success:
                logger.error("Processing failed")
                exit(1)

        elif args.start_year and args.end_year:
            results = run_batch(args.prefix, args.start_year, args.end_year)
            if results["failed"] > 0:
                exit(1)

        else:
            parser.error("Provide --filename OR --start-year and --end-year")
    except Exception as e:
        logger.exception("Fatal error: %s", str(e))
        exit(1)
