"""
Website: https://www.politicians.my
"""
import requests
import re
import json
import time
import csv
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE = "https://www.politicians.my"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def get_slugs_from_rsc():
    print("Fetching RSC listing stream...")
    url = f"{BASE}/politicians.txt?_rsc=1"
    r = requests.get(url, headers=HEADERS)

    text = r.text

    slugs = re.findall(r'/politician/([a-z0-9\-]+)', text)

    if not slugs:
        slugs = re.findall(r'"id":"([a-z0-9\-]+)"', text)

    slugs = list(set(slugs))
    print(f"Found {len(slugs)} slugs")
    return slugs


def extract_json_object(text, keyword):
    start = text.find(keyword)
    if start == -1:
        return None

    start = text.find("{", start)
    if start == -1:
        return None

    brace_count = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            brace_count += 1
        elif text[i] == "}":
            brace_count -= 1
            if brace_count == 0:
                return text[start:i+1]

    return None


def fetch_politician(slug):
    url = f"{BASE}/politician/{slug}.txt?_rsc=1"
    r = requests.get(url, headers=HEADERS)

    text = r.text

    # Find the politician key directly
    key_index = text.find('"politician":{')
    if key_index == -1:
        print(f"politician key not found for {slug}")
        return None

    # Find the opening brace BEFORE politician
    start = text.rfind("{", 0, key_index)
    if start == -1:
        print(f"Could not locate object start for {slug}")
        return None

    brace_count = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            brace_count += 1
        elif text[i] == "}":
            brace_count -= 1
            if brace_count == 0:
                raw_json = text[start:i+1]
                break
    else:
        print(f"Brace mismatch for {slug}")
        return None

    try:
        data = json.loads(raw_json)
        return data.get("politician")
    except Exception as e:
        print(f"JSON parse error for {slug}: {e}")
        return None

def clean_politicians(raw_data):
    cleaned = []

    for p in raw_data:
        cleaned.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "gender": p.get("gender"),
            "position": p.get("position"),
            "birth_year": p.get("birth_year"),
            "constituency": p.get("constituency"),
            "date_of_birth": p.get("date_of_birth"),
            "party_history": p.get("party_history", []),
            "constituency_id": p.get("constituency_id"),
        })

    return cleaned

def export_author_schema(cleaned_json_file, author_file, author_history_file):
    with open(cleaned_json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    author_rows = []
    history_rows = []

    record_counter = 1
    author_id_map = {}
    next_author_id = 6000

    for person in data:

        slug = person.get("id")

        # ---------------------------
        # Assign numeric new_author_id
        # ---------------------------
        if slug not in author_id_map:
            author_id_map[slug] = next_author_id
            next_author_id += 1

        numeric_author_id = author_id_map[slug]

        # ---------------------------
        # Normalize gender → m / f
        # ---------------------------
        raw_gender = person.get("sex") or person.get("gender")

        if isinstance(raw_gender, str):
            raw_gender = raw_gender.strip().lower()
            if raw_gender == "male":
                normalized_gender = "m"
            elif raw_gender == "female":
                normalized_gender = "f"
            else:
                normalized_gender = None
        else:
            normalized_gender = None

        # ---------------------------
        # Build FULL NAME from slug
        # ---------------------------
        if isinstance(slug, str):
            full_name = slug.replace("-", " ").strip().upper()
        else:
            full_name = None

        # ---------------------------
        # Clean display name → ALL CAPS
        # ---------------------------
        raw_name = person.get("name")
        if isinstance(raw_name, str):
            cleaned_name = raw_name.strip().upper()
        else:
            cleaned_name = None

        # -------- author.csv --------
        author_rows.append({
            "new_author_id": numeric_author_id,
            "full_name": full_name,
            "name": cleaned_name,
            "birth_year": person.get("birth_year"),
            "ethnicity": None,
            "sex": normalized_gender,
        })

        # -------- author_history.csv --------
        for party in person.get("party_history", []):
            party_id = party.get("id")
            start_date = party.get("start_date")
            end_date = party.get("end_date")

            # Normalize start_date to DD/MM/YYYY
            if start_date and isinstance(start_date, str):
                start_date = start_date.strip()
                if "/" in start_date:
                    # Already has slashes (e.g., "1/1/71" or "24/06/2016")
                    parts = start_date.split("/")
                    if len(parts) == 3:
                        day, month, year = parts[0], parts[1], parts[2]
                        # Handle 2-digit years
                        if len(year) == 2:
                            year = f"19{year}" if int(year) > 50 else f"20{year}"
                        start_date = f"{day.zfill(2)}/{month.zfill(2)}/{year}"
                elif "-" in start_date:
                    parts = start_date.split("-")
                    if len(parts) == 3:
                        # YYYY-MM-DD format
                        start_date = f"{parts[2].zfill(2)}/{parts[1].zfill(2)}/{parts[0]}"
                    elif len(parts) == 2:
                        # YYYY-MM format - use 01 as day
                        start_date = f"01/{parts[1].zfill(2)}/{parts[0]}"
                else:
                    # Just a year (YYYY) - use 01/01/YYYY
                    if start_date.isdigit() and len(start_date) == 4:
                        start_date = f"01/01/{start_date}"

            # Normalize end_date to DD/MM/YYYY
            if end_date == "current":
                end_date = None
            elif end_date and isinstance(end_date, str):
                end_date = end_date.strip()
                if "/" in end_date:
                    # Already has slashes (e.g., "8/9/16" or "24/06/2016")
                    parts = end_date.split("/")
                    if len(parts) == 3:
                        day, month, year = parts[0], parts[1], parts[2]
                        # Handle 2-digit years
                        if len(year) == 2:
                            year = f"19{year}" if int(year) > 50 else f"20{year}"
                        end_date = f"{day.zfill(2)}/{month.zfill(2)}/{year}"
                elif "-" in end_date:
                    parts = end_date.split("-")
                    if len(parts) == 3:
                        # YYYY-MM-DD format
                        end_date = f"{parts[2].zfill(2)}/{parts[1].zfill(2)}/{parts[0]}"
                    elif len(parts) == 2:
                        # YYYY-MM format - use last day of month
                        month_days = {
                            "01": "31", "02": "28", "03": "31", "04": "30",
                            "05": "31", "06": "30", "07": "31", "08": "31",
                            "09": "30", "10": "31", "11": "30", "12": "31"
                        }
                        month = parts[1].zfill(2)
                        day = month_days.get(month, "31")
                        end_date = f"{day}/{month}/{parts[0]}"
                else:
                    # Just a year (YYYY) - use 01/01/YYYY (we don't know the actual date)
                    if end_date.isdigit() and len(end_date) == 4:
                        end_date = f"01/01/{end_date}"

            history_rows.append({
                "record_id": record_counter,
                "author_id": numeric_author_id,
                "party": party_id,
                "area_id": None,
                "exec_posts": None,
                "service_posts": None,
                "start_date": start_date,
                "end_date": end_date,
            })

            record_counter += 1

    # Write author.csv
    with open(author_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "new_author_id",
                "full_name",
                "name",
                "birth_year",
                "ethnicity",
                "sex",
            ],
        )
        writer.writeheader()
        writer.writerows(author_rows)

    # Write author_history.csv
    with open(author_history_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "record_id",
                "author_id",
                "party",
                "area_id",
                "exec_posts",
                "service_posts",
                "start_date",
                "end_date",
            ],
        )
        writer.writeheader()
        writer.writerows(history_rows)

    print("Export complete:")
    print(" - author.csv:", len(author_rows), "rows")
    print(" - author_history.csv:", len(history_rows), "rows")


def main():

    # Get file paths from environment variables with defaults
    OUTPUT_DIR = os.getenv("SCRAPER_OUTPUT_DIR", "scripts/ahli_parlimen/outputs")
    
    RAW_FILE = f"{OUTPUT_DIR}/politicians.json"
    CLEANED_FILE = f"{OUTPUT_DIR}/politicians_cleaned.json"
    AUTHOR_FILE = f"{OUTPUT_DIR}/author.csv"
    AUTHOR_HISTORY_FILE = f"{OUTPUT_DIR}/author_history.csv"

    # ==========================================
    # STEP 1 — SCRAPE (OPTIONAL)
    # ==========================================

    slugs = get_slugs_from_rsc()
    results = []

    for slug in slugs:
        print("Fetching:", slug)
        data = fetch_politician(slug)
        if data:
            results.append(data)
        time.sleep(0.3)

    with open(RAW_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("Saved raw:", len(results), "politicians")

    # ==========================================
    # STEP 2 — CLEAN
    # ==========================================
    with open(RAW_FILE, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    cleaned_data = clean_politicians(raw_data)

    with open(CLEANED_FILE, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

    print("Saved cleaned:", len(cleaned_data), "politicians")

    # ==========================================
    # STEP 3 — EXPORT TO AUTHOR SCHEMA CSV
    # ==========================================
    export_author_schema(CLEANED_FILE, AUTHOR_FILE, AUTHOR_HISTORY_FILE)


if __name__ == "__main__":
    main()