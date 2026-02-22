"""
This module processes textracted CSV files of parliamentary sittings, extracts table of contents (TOC),
timestamps, speakers, and speeches, and prepares the data for insertion into a database.

Example usage:
# python process_textracted.py --prefix dewannegara --start-year 1991 --end-year 1991
# python process_textracted.py --prefix dewannegara --filename dn_1991-02-18_layout.csv
# python process_textracted.py --prefix dewannegara --processed-date 1991-02-18 --insert

"""
import argparse
import re
import boto3
import json
import pandas as pd
import requests
import os
from io import BytesIO
from datetime import datetime, time
from difflib import SequenceMatcher
from ..author_matching import perform_author_matching
from ..utils.text_utils import house_mapper, preprocess_malaya, get_sitting_object, is_number_only
import warnings
import psycopg2
from botocore import UNSIGNED
from botocore.config import Config
from ..settings import S3_TEXTRACT_BUCKET, DEV_API_URL, HANSARD_DB_URL, S3_PUBLIC_BUCKET
from ..direct_sitting_ingest import ingest_sitting_to_db

import boto3
import botocore
session = boto3.Session()
credentials = session.get_credentials().get_frozen_credentials()


warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message="This pattern is interpreted as a regular expression, and has match groups.*")

ts_full = re.compile(r'^\d{1,2}\.\d{2}\s*(ptg|petang|pagi|tgh|tengah hari|mlm)?\.?$', re.IGNORECASE)
ts_search = re.compile(r'(\d{1,2})\.(\d{2})', re.IGNORECASE)

period = re.compile(r'\b(ptg|petang|pagi|tgh|tengah hari|mlm|a\.?m\.?|p\.?m\.?)\b', re.IGNORECASE)

TOC_KEYWORDS = ['KANDUNGAN', 'CONTENTS', 'KANDONGAN']
DOA_KEYWORDS = ['DOA', 'DOA PENDAHULUAN', 'DUA', "DO'A", "PRAYERS", "PRAYER", "D OA", "D0A"]

# Override for problematic files. Map -  filename : custom DOA keyword
DOA_KEYWORDS_OVERRIDE = {
    "dr_1959-09-11_layout.csv": "OPENING OF PARLIA",
    "dn_1959-09-11_layout.csv": "OPENING OF THE",
    "dn_1959-12-05_layout.csv": "ADMINISTRATION OF",
    "dn_1961-01-07_layout.csv" :"Bukit Bintang",
    "dn_1988-03-30_layout.csv": "JAWAPAN-JAWAPAN MULUT BAGI PERTANYAAN-PERTANYAAN",
    "dn_1983-08-10_layout.csv": "JAWAPAN-JAWAPAN MULUT BAGI PERTANYAAN-PERTANYAAN",
    "dr_1990-06-15_layout.csv": "DO A",
    "dn_1963-12-28_layout.csv" :"BILL",
    "dr_1974-11-20_layout.csv" :"PEMASYHURAN YANG DI-PERTUA",
    "dn_1966-06-14_layout.csv" :"PRESENTATION OF MACE TO THE SENATE",
    "dr_1964-05-18_layout.csv" :"OPENING OF PARLIAMENT",
    "dr_1964-12-15_layout.csv" :"ORAL ANSWERS TO QUESTIONS",
    "dn_1996-12-11_layout.csv" : "MENGANGKAT SUMPAH",
    "dn_1992-08-12_layout.csv" : "JAWAPAN-JAWAPAN MULUT BAGI PERTANYAAN-PERTANYAAN",
    "dn_1992-06-04_layout.csv" : "JAWAPAN-JAWAPAN MULUT BAGI PERTANYAAN-PERTANYAAN",
    "dn_1991-08-05_layout.csv" : "MENGANGKAT SUMPAH",
    "dn_1991-08-06_layout.csv" : "JAWAPAN-JAWAPAN MULUT BAGI PERTANYAAN-PERTANYAAN",
    "dr_2004-05-24_layout.csv" : "MENGANGKAT SUMPAH",
    "dr_2004-07-19_layout.csv" : "JAWAPAN-JAWAPAN LISAN BAGI PERTANYAAN-PERTANYAAN",
    "dr_2003-10-23_layout.csv" : "JAWAPAN-JAWAPAN LISAN BAGI PERTANYAAN-PERTANYAAN",
    "dr_2002-09-20_layout.csv" : "RANG UNDANG-UNDANG",
    "dr_2001-04-11_layout.csv" : "JAWAPAN-JAWAPAN LISAN BAGI PERTANYAAN-PERTANYAAN",
    "dr_2001-05-08_layout.csv" : "mempengerusikan Mesyuarat",
    "dr_2001-05-02_layout.csv" : "JAWAPAN-JAWAPAN LISAN BAGI PERTANYAAN-PERTANYAAN",
    "dr_2000-04-12_layout.csv" : "JAWAPAN-JAWAPAN LISAN BAGI PERTANYAAN-PERTANYAAN",
    "dr_2000-03-06_layout.csv" : "JAWAPAN-JAWAPAN LISAN BAGI PERTANYAAN-PERTANYAAN",
    "dr_2000-11-07_layout.csv" : "mempengerusikan Mesyuarat",
    "dr_1993-10-18_layout.csv" : "BENTARA MESYUARAT",
    "dr_1993-07-29_layout.csv" : "BENTARA MESYUARAT",
    "dr_1994-11-23_layout.csv" : "BENTARA MESYUARAT",
}

class SimpleLogger:
    class Log:
        def info(self, msg):
            print(f"[INFO] {msg}")
        def warning(self, msg):
            print(f"[WARN] {msg}")
        def error(self, msg):
            print(f"[ERROR] {msg}")
    log = Log()

def get_db_connection():
    """Create and return a database connection."""
    if not HANSARD_DB_URL:
        raise ValueError("HANSARD_DB_URL environment variable not set")
    return psycopg2.connect(HANSARD_DB_URL)

def build_textracted_key(prefix: str, filename: str) -> str:
    return f"textracted/{prefix}/{filename}"

def parse_timestamp(txt):

    if txt.startswith(("DN.", "DR.")):  # DN.28.11.2002
        return None
    
    m = ts_search.search(txt)
    if not m:
        return None
    h, mnt = int(m.group(1)), int(m.group(2))
    p = period.search(txt)
    per = p.group(1).lower() if p else ''

    # Interpret time
    if per in ['ptg', 'petang', 'mlm', 'tgh', 'tengah hari', 'p.m.', 'pm', 'p.m']:
        if h != 12:
            h += 12
    elif per in ['a.m.', 'am', 'a.m', 'pagi']:
        if h == 12:
            h = 0
    else:
        # Fallback to afternoon if hour < 8 (likely typo/missing) bcs sittings dont usually happen before office hour.
        if h < 8:
            h += 12

    if not (0 <= h <= 23 and 0 <= mnt <= 59):
        print(f"❌ Invalid time parsed from text: '{txt}' -> hour: {h}, minute: {mnt}")
        return None

    print(f"Found timestamp: {txt} - hour: {h}, minute: {mnt}")
    return time(h, mnt)

def extract_toc_block(df, filename=None, fallback_max_lines=30):
    toc_df = df[~df['layout'].isin(['Header', 'Footer'])].copy()
    toc_df['txt'] = toc_df['text'].fillna('').astype(str)

    # Get index of first 'DOA'
    doa_idx = pd.NA
    doa_keywords = DOA_KEYWORDS.copy()

    if filename and filename in DOA_KEYWORDS_OVERRIDE:
        doa_keywords.insert(0, DOA_KEYWORDS_OVERRIDE[filename])
        print(f"⚠️ Overriding DOA keywords for {filename}: using '{DOA_KEYWORDS_OVERRIDE[filename]}'")

    for keyword in doa_keywords:
        match = df[df['text'].str.contains(fr'\b{re.escape(keyword)}\b', case=True, na=False)]
        if not match.empty:
            doa_idx = match.index.min()
            print(f"✅ Found DOA keyword: '{keyword}' at line {doa_idx}")
            break

    if pd.isna(doa_idx):
        print("⚠️ No DOA-like keyword found for TOC extraction. Skipping processing.")
        return pd.DataFrame()

    # Limit TOC search to before DOA
    pre_doa_df = toc_df.loc[:doa_idx] if not pd.isna(doa_idx) else toc_df

    kandungan_idx = pd.NA
    for keyword in TOC_KEYWORDS:
        match_idx = pre_doa_df[pre_doa_df['txt'].str.contains(fr'\b{keyword}\b', case=True, na=False)].index.min()
        if not pd.isna(match_idx):
            print(f"✅ Found TOC keyword: '{keyword}' at line {match_idx}")
            kandungan_idx = match_idx
            break

    if pd.isna(kandungan_idx):
        print(f"⚠️ No keyword from {TOC_KEYWORDS} found in TOC. Skipping processing for this csv.")
        return pd.DataFrame(columns=['level_1', 'level_2', 'norm_l1', 'norm_l2'])


    ruang_indices = toc_df[toc_df['txt'].str.contains(r'\[Ruangan.*?\]', regex=True)].index.tolist()
    ahli_indices = toc_df[toc_df['txt'].str.upper().str.contains('AHLI-AHLI DEWAN')].index.tolist()

    # Look for end within fallback limit
    valid_ruang = [idx for idx in ruang_indices if kandungan_idx < idx <= kandungan_idx + fallback_max_lines]
    valid_ahli = [idx for idx in ahli_indices if kandungan_idx < idx <= kandungan_idx + fallback_max_lines]

    if valid_ruang or valid_ahli:
        end = max(valid_ruang + valid_ahli)
    else:
        end = min(kandungan_idx + fallback_max_lines, toc_df.index.max())

    print(f"\n[TOC] Extracting block from line {kandungan_idx} to {end} ...")
    block = toc_df.loc[kandungan_idx:end]

    lines = block['txt'].str.replace(r"\[.*?\]", '', regex=True)
    split_lines = []
    for line in lines:
        chunks = re.split(r'\s{2,}|(?<=\))\s+', line)
        split_lines.extend([chunk.strip(' :"\'') for chunk in chunks if chunk.strip()])

    toc = []
    current_l1 = ''
    for ln in split_lines:
        line = ln.strip()
        if not line or any(keyword in line.upper() for keyword in TOC_KEYWORDS):
            continue
        # Skip number-only lines (e.g., "1.", "2.", "3.")
        if is_number_only(line):
            print(f"[TOC] Skipping number-only line: '{line}'")
            continue
        
        up_count = sum(1 for c in line if c.isupper())
        low_count = sum(1 for c in line if c.islower())
        if up_count > low_count:
            current_l1 = line
            toc.append({'level_1': current_l1, 'level_2': ''})
        else:
            if current_l1:
                toc.append({'level_1': current_l1, 'level_2': line})

    toc_out = pd.DataFrame(toc)
    toc_out['norm_l1'] = toc_out['level_1'].str.replace(r"[^\w\s]", '', regex=True).str.upper().str.strip()
    toc_out['norm_l2'] = toc_out['level_2'].str.replace(r"[^\w\s]", '', regex=True).str.upper().str.strip()

    print("\nExtracted TOC:")
    print(toc_out[['level_1', 'level_2']].to_string(index=False))

    return toc_out

def process_layout(df, toc_df, filename=None):
    df['is_timestamp'] = df['clean'].str.match(ts_full)
    df['is_speaker'] = df['clean'].str.match(r'^(?!\d+\.)[^:]{3,}?:')

    doa_keywords = DOA_KEYWORDS.copy()
    if filename and filename in DOA_KEYWORDS_OVERRIDE:
        doa_keywords.insert(0, DOA_KEYWORDS_OVERRIDE[filename])
        print(f"⚠️ Overriding DOA keywords for {filename}: using '{DOA_KEYWORDS_OVERRIDE[filename]}'")

    doai = pd.NA
    for keyword in doa_keywords:
        match = df[df['text'].str.contains(fr'\b{re.escape(keyword)}\b', case=True, na=False)]
        if not match.empty:
            doai = match.index.min()
            print(f"✅ Found DOA keyword: '{keyword}' at line {doai}")
            break

    if pd.isna(doai):
        print("⚠️ No DOA-like keyword found to start speech processing. Skipping processing.")
        return pd.DataFrame()  # 🔥 IMPORTANT: exit here to avoid slicing with pd.NA

    # Detect timestamp BEFORE DOA
    pre = df.loc[:doai] if not pd.isna(doai) else df

    # Filter all rows that actually parse into a valid time
    valid_ts_rows = pre[pre['clean'].apply(lambda x: parse_timestamp(x) is not None)]
    init_ts_row = valid_ts_rows.head(1)

    ts_init = None
    if not init_ts_row.empty:
        init_text = init_ts_row.iloc[0]['clean']
        ts_init = parse_timestamp(init_text)
        if ts_init:
            print(f"✅ Found an initial timestamp before DOA: {init_text} -> {ts_init.strftime('%H%M')}")
    else:
        print("⚠️ No initial timestamp found before DOA keyword.")

    post = df.loc[doai+1:].copy()
    exclude = (
        (post['layout'].str.contains('Footer', case=False) |
         (post['layout'].str.contains('Header', case=False) &
          ~post['layout'].str.contains('SECTION_HEADER|Section header', case=False)))
        & ~post['is_timestamp']
    )
    post = post[~exclude].reset_index(drop=True)
    post['is_upper'] = post['clean'].apply(
        lambda x: sum(1 for c in x if c.isupper()) > sum(1 for c in x if c.islower())
    )

    l1 = ''
    l2 = ''
    exp1 = True
    post['level_1'] = ''
    post['level_2'] = ''
    for idx, row in post.iterrows():
        text = row['clean']
        # Skip numbering-only rows before ANY logic runs
        if is_number_only(text):
            print(f"Skipping numbering line: '{text}'")
            post.at[idx, 'level_1'] = l1
            post.at[idx, 'level_2'] = l2
            continue
        
        norm = re.sub(r"[^\w\s]", '', text).upper().strip()
        if row['is_upper']:
            print(f"\nProcessing line [{idx}]: {text}")
            print(f"   Normalized: {norm}")

            best_l2_score = 0
            best_l2_l1 = None
            for _, toc in toc_df.iterrows():
                score = SequenceMatcher(None, norm, toc['norm_l2']).ratio()
                if score > best_l2_score:
                    best_l2_score = score
                    best_l2_l1 = toc['level_1']
            print(f"    Best L2 match score: {best_l2_score:.2f} (matched to: {best_l2_l1})")

            if best_l2_score >= 0.6:
                l1, l2 = best_l2_l1, text
                print(f" ✅ Assigned as level_2 under: {l1}")
            else:
                best_l1_score = 0
                best_l1_match = None
                for _, toc in toc_df.iterrows():
                    score = SequenceMatcher(None, norm, toc['norm_l1']).ratio()
                    if score > best_l1_score:
                        best_l1_score = score
                        best_l1_match = toc['level_1']
                print(f"    Best L1 match score: {best_l1_score:.2f} (matched to: {best_l1_match})")

                if best_l1_score >= 0.6:
                    l1, l2 = text, ''
                    print(f" ✅ Assigned as level_1: {l1}")
                else:
                    if exp1:
                        l1, l2 = text, ''
                        print(f" ⚠️ Fallback: treated as level_1 via exp1")
                    else:
                        l2 = text
                        print(f" ⚠️ Fallback: treated as level_2 via exp1")
                    exp1 = not exp1
        else:
            exp1 = True
        post.at[idx, 'level_1'] = l1
        post.at[idx, 'level_2'] = l2

    # To capture headings with speaker
    segments = []
    current_author = None
    current_speech = ''
    current_level1 = ''
    current_level2 = ''
    ts_cur = ts_init
    for idx, row in post.iterrows():
        if row['is_timestamp']:
            t = parse_timestamp(row['clean'])
            if t:
                ts_cur = t
        if row['is_speaker']:
            # save previous speaker block
            if current_author:
                segments.append({
                    'level_1': current_level1,
                    'level_2': current_level2,
                    'level_3': '',
                    'timestamp': ts_cur.strftime('%H%M') if ts_cur else '',
                    'author': current_author,
                    'speech': current_speech.strip()
                })

            # start new speaker
            parts = row['clean'].split(':', 1)
            current_author = parts[0].strip()
            current_speech = parts[1].strip() if len(parts) > 1 else ''
            current_level1 = row['level_1']
            current_level2 = row['level_2']
        elif row['is_upper'] and not row['is_speaker']:
            # heading without speaker
            segments.append({
                'level_1': row['level_1'],
                'level_2': row['level_2'],
                'level_3': '',
                'timestamp': ts_cur.strftime('%H%M') if ts_cur else '',
                'author': None,
                'speech': ''
            })
        elif not row['is_upper'] and not row['is_timestamp']:
            if current_author:
                current_speech += '\n' + row['clean']
            else:
                # orphaned paragraph — no speaker
                segments.append({
                    'level_1': row['level_1'],
                    'level_2': row['level_2'],
                    'level_3': '',
                    'timestamp': ts_cur.strftime('%H%M') if ts_cur else '',
                    'author': None,
                    'speech': row['clean'].strip()
                })

    if current_author:
        segments.append({
            'level_1': current_level1,
            'level_2': current_level2,
            'level_3': '',
            'timestamp': ts_cur.strftime('%H%M') if ts_cur else '',
            'author': current_author,
            'speech': current_speech.strip()
        })

    # df_speech = pd.DataFrame(segments)

    # # Assign 'ANNOTATION' when there's a heading, but no author & no speech. 
    # df_speech['author'] = df_speech.apply(
    #     lambda row: 'ANNOTATION'
    #     if (not row['author'] or pd.isna(row['author']))
    #     and (not row['speech'] or pd.isna(row['speech']))
    #     and (row['level_1'] or row['level_2'])
    #     else row['author'],
    #     axis=1
    # )

    # return df_speech
    return pd.DataFrame(segments)

def prepare_db_payload(df_speech, prefix, date_str):

    # Construct pdf_key and sitting object
    pdf_key = f"{house_mapper.to_code(prefix).upper()}-{datetime.strptime(date_str, '%Y-%m-%d').strftime('%d%m%Y')}"
    sitting_obj = get_sitting_object(pdf_key)

    try:
        df_speech["index"] = df_speech.reset_index().index
        df_speech["date"] = pd.to_datetime(date_str)
        df_speech["house"] = house_mapper.to_display(prefix)
        df_speech["is_annotation"] = (df_speech["author"].astype(str).str.strip().str.upper() == "ANNOTATION")

        df_author = pd.DataFrame(requests.get(f"{DEV_API_URL}/api/author").json())
        df_author_hist = pd.DataFrame(requests.get(f"{DEV_API_URL}/api/author-history").json())
        df_author_hist["area"] = df_author_hist["area_name"].str[5:]

        logger = SimpleLogger()
        df_speech = perform_author_matching(df_speech, df_author, df_author_hist, logger)

        # Replace "NO MATCH" with None
        df_speech.loc[df_speech["author_id"] == "NO MATCH", "author_id"] = None

        # Assign speaker names
        df_speech = assign_speaker_names(df_speech, df_author)

        if "speaker" not in df_speech.columns:
            df_speech["speaker"] = None

        print("Sample matched rows (speaker is NOT null):")
        print(df_speech[df_speech["speaker"].notnull()][["index", "author", "author_id", "speaker"]].head(5))

        print("Sample unmatched rows (speaker IS NULL):")
        print(df_speech[df_speech["speaker"].isnull()][["index", "author", "author_id"]].head(5))

    except Exception as e:
        print(f"❌ Author matching failed: {e}")
        raise RuntimeError("Aborting because author matching is required to continue.")

    df_speech["sitting"] = sitting_obj["proper_date_str"]
    df_speech["index"] = df_speech.reset_index().index
    df_speech["proc_speech"] = df_speech["speech"]
    df_speech["speech_tokens"] = df_speech["proc_speech"].apply(preprocess_malaya)
    df_speech["length"] = df_speech["speech_tokens"].apply(len)

    if "speaker" not in df_speech.columns:
        df_speech["speaker"] = None

    # Replace empty values in columns with None 
    for col in ["level_1", "level_2", "level_3"]:
        df_speech[col] = df_speech[col].apply(lambda x: x if pd.notna(x) and str(x).strip() else None)

    if df_speech["timestamp"].isna().any():
        print("Problem: Found a null timestamp. Fix it before proceed.")

    # Filter out speeches with empty token list 
    df_speech = df_speech[df_speech["speech_tokens"].apply(lambda tokens: bool(tokens))]

    speech_data = df_speech[[
        "index", "author", "author_id", "timestamp", "speech", "proc_speech",
        "speech_tokens", "length", "level_1", "level_2", "level_3",
        "is_annotation", "sitting"
    ]].rename(columns={"author_id": "speaker"}).to_dict(orient="records")

    payload = {
        "date": sitting_obj["proper_date_str"],
        "filename": sitting_obj["renamed_filename"],
        "is_final": False,
        "house": sitting_obj["house_display"],
        "speech_data": json.dumps(speech_data),

    }

    # with open(f"payload_{date_str}.json", "w") as f:
    #     json.dump(payload, f, indent=2)
    # print(f"📝 Payload saved to payload_{date_str}.json")

    return df_speech, payload

def insert_to_db_via_api(payload):
    print("\nSending request to backend...")
    try:
        # log the json payload
        print(json.dumps(payload, indent=2))
        response = requests.post(f"{DEV_API_URL}/api/sitting", json=payload, timeout=3600)
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            print("⚠️ Response was not valid JSON:")
            print(response.text)
            response_data = {}

        if response.status_code == 201:
            if "warning" in response_data:
                print(f"⚠️ Data integrity warning: {response_data['warning']}")
            elif "speech_errors" in response_data:
                print(f"⚠️ Speech errors: {response_data['speech_errors']}")
            print("Inserted to DB")
        else:
            response.raise_for_status()

    except requests.exceptions.HTTPError as e:
        print(f"Failed to insert: {response.status_code} - {response.text}")

def insert_to_db(payload, logger):
    logger.info("Inserting directly into database...")

    conn = None
    try:
        conn = get_db_connection()
        ingest_sitting_to_db(payload, conn)
        conn.commit()
        logger.info("Inserted to DB")
    except Exception:
        if conn:
            conn.rollback()
        logger.error("Insert failed")
        raise
    finally:
        if conn:
            conn.close()


def run_batch(prefix, start_year, end_year):
    s3 = session.client("s3")
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=S3_TEXTRACT_BUCKET, Prefix=f"{prefix}/")

    all_files = []
    for page in pages:
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith("_layout.csv"):
                continue
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', key)
            if not date_match:
                continue
            date_str = date_match.group(1)
            year = int(date_str[:4])
            if start_year <= year <= end_year:
                all_files.append((key, date_str))

    print(f"\nRUNNING BATCH.. Total CSVs to process: {len(all_files)}")

    success_count = 0
    fail_count = 0
    failed_files = []
    skip_count = 0
    skipped_files = []

    for key, date_str in all_files:
        try:
            process_and_insert(prefix, key, date_str)
            success_count += 1
        except ValueError as ve:
            if str(ve) == "SKIPPED_NO_SPEECH":
                skipped_files.append(key)
                skip_count += 1
                print(f"⚠️ SKIPPED (no speech): {key}")
            else:
                print(f"❌ Failed with ValueError: {key} - {ve}")
                failed_files.append(key)
                fail_count += 1
        except Exception as e:
            print(f"❌ Failed processing {key}: {e}")
            failed_files.append(key)
            fail_count += 1

    print("\n========== PROCESS SUMMARY ==========")
    print(f"Total files found  : {len(all_files)}")
    print(f" Successful      : {success_count}")
    print(f" Skipped (no speech): {skip_count}")
    print(f" Failed          : {fail_count}")

    if skipped_files:
        print("\n⚠️ Skipped Files:")
        for f in skipped_files:
            print(f" - {f}")
    if failed_files:
        print("\n❌ Failed Files:")
        for f in failed_files:
            print(f" - {f}")

def clean_speech_using_layout(
    df_speech,
    df_layout,
    logger,
    similarity_threshold=0.85,
):
    """
    Character corruption cleanup.
    - Only modifies words containing corrupted characters
    - Uses layout text as reference to fix corrupted words, which means it can only correct to words that exist in the textracted layout.
    """

    logger.info("Running corruption cleanup...")

    # Build reference word set from layout text
    layout_text = " ".join(df_layout["text"].astype(str).tolist())
    layout_words = set(re.sub(r"[^\w]", "", w) for w in layout_text.split())
    layout_words = {w for w in layout_words if w}

    corrupted_chars = ['�', '\ufffd', '£', '€', '«', '§', '°', '¢']

    def has_corruption(word):
        if not isinstance(word, str):
            return False
        if any(c in word for c in corrupted_chars):
            return True
        if any(ord(c) > 127 for c in word):
            return True
        return False

    correction_count = 0

    def is_small_edit_distance(a, b, fallback_threshold=0.80):
        """
        Allow slightly lower similarity for corrupted words (handles missing character cases like pencerobhan -> pencerobohan)
        """
        ratio = SequenceMatcher(None, a, b).ratio()
        return ratio >= fallback_threshold

    def fix_cell(text):
        nonlocal correction_count

        if not isinstance(text, str):
            return text

        tokens = re.split(r'(\s+)', text)  # keep whitespace
        fixed_tokens = []

        for token in tokens:

            # Keep whitespace exactly as-is
            if token.isspace():
                fixed_tokens.append(token)
                continue

            word = token

            if not has_corruption(word):
                fixed_tokens.append(word)
                continue

            # --- Remove non-ascii ---
            ascii_only = ''.join(c for c in word if ord(c) < 128)

            if not ascii_only:
                fixed_tokens.append(word)
                continue

            # --- Extract prefix (leading punctuation) ---
            prefix = ''
            while ascii_only and not ascii_only[0].isalnum():
                prefix += ascii_only[0]
                ascii_only = ascii_only[1:]

            # --- Extract suffix (trailing punctuation) ---
            suffix = ''
            while ascii_only and not ascii_only[-1].isalnum():
                suffix = ascii_only[-1] + suffix
                ascii_only = ascii_only[:-1]

            core = ascii_only

            if not core:
                fixed_tokens.append(word)
                continue

            best_match = None
            best_ratio = 0

            for lw in layout_words:
                ratio = SequenceMatcher(None, core.lower(), lw.lower()).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = lw

            final_core = core

            if best_match and (
                best_ratio >= similarity_threshold
                or is_small_edit_distance(core.lower(), best_match.lower())
            ):
                final_core = best_match
                correction_count += 1

            # --- Preserve original casing pattern ---
            if core.istitle():
                final_core = final_core.title()
            elif core.isupper():
                final_core = final_core.upper()
            elif core.islower():
                final_core = final_core.lower()

            final_word = prefix + final_core + suffix

            logger.info(
                f"[CLEANUP] original='{word}' | core='{core}' | "
                f"best='{best_match}' | ratio={best_ratio:.3f} | final='{final_word}'"
            )

            fixed_tokens.append(final_word)

        return "".join(fixed_tokens)

    df_speech["speech"] = df_speech["speech"].apply(fix_cell)
    for col in ["level_1", "level_2", "level_3"]:
        if col in df_speech.columns:
            df_speech[col] = df_speech[col].apply(fix_cell)

    logger.info(f"Cleanup corrections made: {correction_count}")

    return df_speech

def merge_question_blocks(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    merged = []
    prev = df.iloc[0].to_dict()

    for _, row in df.iloc[1:].iterrows():
        curr = row.to_dict()

        same_heading = (
            curr["level_1"] == prev["level_1"]
            and curr["timestamp"] == prev["timestamp"]
        )

        both_no_author = (
            not curr.get("author")
            and not prev.get("author")
        )

        if same_heading and both_no_author:
            prev_speech = (prev.get("speech") or "").rstrip()
            curr_speech = (curr.get("speech") or "").lstrip()

            # ensure clean newline separation
            if prev_speech:
                prev["speech"] = prev_speech + "\n" + curr_speech
            else:
                prev["speech"] = curr_speech
        else:
            merged.append(prev)
            prev = curr

    merged.append(prev)
    return pd.DataFrame(merged)


def process_and_insert(prefix, key, date_str, logger):

    s3 = session.client("s3")
    logger.info(f"\nProcessing: {key}")
    obj = s3.get_object(Bucket=S3_TEXTRACT_BUCKET, Key=key)

    df = pd.read_csv(BytesIO(obj["Body"].read()))

    df.columns = [c.strip().strip("'").strip() for c in df.columns]
    for col in df.columns:
        df[col] = df[col].fillna('').astype(str).str.strip().str.strip("'")
        None
    df = df.rename(columns={
        'Page number': 'page', 'Layout': 'layout', 'Text': 'text',
        'Reading Order': 'order', 'Confidence score % (Layout)': 'confidence'
    })
    df = df[~df['layout'].str.contains('Page', case=False, na=False)]
    df['clean'] = df['text'].fillna('').str.strip()

    # Normalize whitespace: replace multiple newlines with a single space, multiple spaces with a single space, and trim leading/trailing whitespace
    df['clean'] = df['clean'].str.replace(r'\n+', ' ', regex=True)
    df['clean'] = df['clean'].str.replace(r'\s{2,}', ' ', regex=True)
    df['clean'] = df['clean'].str.strip()

    toc_df = extract_toc_block(df, filename=key.split("/")[-1])
    df_speech = process_layout(df, toc_df, filename=key.split("/")[-1])
    df_speech = merge_question_blocks(df_speech)
    df_speech = clean_speech_using_layout(df_speech, df, logger)

    if df_speech.empty:
        logger.warning(f"Skipping {key} - No speech content parsed from PDF. Skip upload to S3 & skip prepare_db_payload process.")
        raise ValueError("SKIPPED_NO_SPEECH")
    
    buffer = BytesIO()
    df_speech.to_csv(buffer, index=False)
    buffer.seek(0)

    # store raw processed file
    pdf_key = f"{house_mapper.to_code(prefix).upper()}-{datetime.strptime(date_str, '%Y-%m-%d').strftime('%d%m%Y')}"
    sitting_obj = get_sitting_object(pdf_key)
    s3_key = f"{prefix}/{sitting_obj['renamed_filename']}.csv"
    s3.put_object(Bucket=S3_PUBLIC_BUCKET, Key=s3_key, Body=buffer.getvalue(), ContentType="text/csv")
    print(f"\nSaved to {s3_key}")

    # final processed file with matched author name (no need to store in S3. its stored in DB)
    df_speech, payload = prepare_db_payload(df_speech, prefix, date_str)

    print("\nInserting payload to DB ...")
    insert_to_db(payload, logger)

def process_from_processed_csv(prefix, date_str, insert=False, logger=None):
    s3 = session.client("s3")
    pdf_key = f"{house_mapper.to_code(prefix).upper()}-{datetime.strptime(date_str, '%Y-%m-%d').strftime('%d%m%Y')}"
    sitting_obj = get_sitting_object(pdf_key)
    key = f"post_textracted/{prefix}/{sitting_obj['renamed_filename']}.csv"
    print(f"\nLoading processed speech CSV from: {key}")

    obj = s3.get_object(Bucket=S3_TEXTRACT_BUCKET, Key=key)
    df_speech = pd.read_csv(BytesIO(obj["Body"].read()))

    df_speech.columns = [c.strip().strip("'") for c in df_speech.columns]
    for col in df_speech.columns:
        df_speech[col] = df_speech[col].fillna('').astype(str).str.strip()

    df_speech, payload = prepare_db_payload(df_speech, prefix, date_str)

    if insert:
        insert_to_db(payload, logger)

    return df_speech

def assign_speaker_names(df_speech, df_author):
    """
    Assigns speaker names to df_speech using author_id and df_author.

    Parameters:
    - df_speech: DataFrame containing 'author_id'
    - df_author: DataFrame containing 'new_author_id' and 'name'

    Returns:
    - Updated df_speech with 'speaker' column filled in
    """
    # Create lookup from author.id → author.name
    author_lookup = df_author.set_index("new_author_id")["name"]

    # Map author_id to speaker name
    df_speech["speaker"] = df_speech["author_id"].map(author_lookup)

    return df_speech

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", required=True, choices=["dewanrakyat", "dewannegara", "kamarkhas"])
    parser.add_argument("--start-year", type=int, help="Start year for batch mode")
    parser.add_argument("--end-year", type=int, help="End year for batch mode")
    parser.add_argument("--filename", type=str, help="Optional: process only this file (e.g. dn_1991-02-18_layout.csv)")
    parser.add_argument("--processed-date", type=str, help="Use processed CSV instead (e.g. 1992-05-28)")
    parser.add_argument("--insert", action="store_true", help="Insert to DB after processing")

    args = parser.parse_args()

    if args.processed_date:
        process_from_processed_csv(args.prefix, args.processed_date, insert=args.insert)
    elif args.filename:
        match = re.search(r'(\d{4}-\d{2}-\d{2})', args.filename)
        if not match:
            raise ValueError("Could not extract date from filename. Expected format like 'dn_1991-02-18_layout.csv'")
        date_str = match.group(1)
        key = build_textracted_key(args.prefix, args.filename)
        process_and_insert(args.prefix, key, date_str)
    elif args.start_year and args.end_year:
        run_batch(args.prefix, args.start_year, args.end_year)
    else:
        raise ValueError("Must provide --processed-date, --filename, or both --start-year and --end-year.")


