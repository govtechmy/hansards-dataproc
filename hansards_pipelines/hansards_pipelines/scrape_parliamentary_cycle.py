"""
Parliamentary cycle scraping module.
Contains both arkib and active scraping strategies.
"""

import re
import xml.etree.ElementTree as ET
import requests
import psycopg
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional, List, Dict, Set, Tuple
from dagster import AssetExecutionContext

BASE_URL = "https://www.parlimen.gov.my"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

HOUSE_MAP = {
    "dewanrakyat": 0,  
    "dewannegara": 1,  
    "kamarkhas": 2,   
}

MALAY_MONTHS = {
    "januari": 1, "februari": 2, "mac": 3, "april": 4,
    "mei": 5, "jun": 6, "julai": 7, "ogos": 8,
    "september": 9, "oktober": 10, "november": 11, "disember": 12
}


def malay_ordinal_to_number(ordinal_text: str) -> Optional[int]:
    """
    Convert Malay ordinal words to numbers.
    Handles simple ordinals (pertama-kesepuluh), teens (belas), and tens (puluh).
    """
    ordinal_lower = ordinal_text.lower().strip()
    normalized = " ".join(ordinal_lower.split())

    # Base numbers (1-10)
    base_numbers = {
        "pertama": 1, "kedua": 2, "ketiga": 3, "keempat": 4, "kelima": 5,
        "keenam": 6, "ketujuh": 7, "kelapan": 8, "kesembilan": 9, "kesepuluh": 10
    }
    
    if normalized in base_numbers:
        return base_numbers[normalized]
    
    # Teens (11-19) - ends with "belas"
    if "belas" in normalized:
        if normalized == "kesebelas":
            return 11
        
        belas_match = re.match(r"^ke(\w+)\s+belas$", normalized)
        if belas_match:
            stem = belas_match.group(1)
            cardinal_map = {
                "dua": 2, "tiga": 3, "empat": 4, "lima": 5,
                "enam": 6, "tujuh": 7, "lapan": 8, "sembilan": 9,
            }
            digit = cardinal_map.get(stem)
            if digit is not None:
                return 10 + digit
    
    # Tens (20-90+) - contains "puluh"
    if "puluh" in normalized:
        parts = normalized.split("puluh")
        tens_part = parts[0].strip()
        ones_part = parts[1].strip() if len(parts) > 1 else ""
        
        base_to_tens = {
            "kedua": 2, "ketiga": 3, "keempat": 4, "kelima": 5,
            "keenam": 6, "ketujuh": 7, "kelapan": 8, "kesembilan": 9
        }
        
        tens_digit = base_to_tens.get(tens_part, 0)
        ones_digit = 0
        
        if ones_part:
            ones_map = {
                "satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5,
                "enam": 6, "tujuh": 7, "lapan": 8, "sembilan": 9
            }
            ones_digit = ones_map.get(ones_part, 0)
        
        return tens_digit * 10 + ones_digit
    
    return None


def fetch_db_cycles(
    hansard_db_url: str, 
    context: Optional[AssetExecutionContext] = None
) -> Set[Tuple]:
    """Fetch existing parliamentary cycles from database to prevent duplicates."""
    existing_keys = set()
    
    try:
        if not hansard_db_url:
            raise ValueError("HANSARD_DB_URL is not configured.")
        
        if context:
            context.log.info("[parliamentary_cycle] Connecting to database...")
        
        with psycopg.connect(hansard_db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT house, term, session, meeting, start_date, end_date
                    FROM api_parliamentary_cycle
                """)
                existing_cycles = cur.fetchall()
                
                if context:
                    context.log.info(f"[parliamentary_cycle] Database returned {len(existing_cycles)} existing cycles")
                
                for row in existing_cycles:
                    house, term, session, meeting, start_date, end_date = row
                    key = (
                        house,
                        term,
                        session,
                        meeting,
                        start_date.isoformat() if hasattr(start_date, 'isoformat') else str(start_date),
                        end_date.isoformat() if hasattr(end_date, 'isoformat') else str(end_date)
                    )
                    existing_keys.add(key)
                    
        if context:
            context.log.info(f"[parliamentary_cycle] Built {len(existing_keys)} unique keys from database")
                
    except Exception as e:
        if context:
            context.log.error(f"[parliamentary_cycle] ERROR fetching existing cycles: {type(e).__name__}: {e}")
        existing_keys = set()
    
    return existing_keys


def upsert_cycles_via_api(
    cycles: List[Dict],
    existing_keys: Set[Tuple],
    api_endpoint: str,
    log_prefix: str = "parliamentary_cycle",
    context: Optional[AssetExecutionContext] = None
) -> Dict:
    """Upsert cycles via API and return summary statistics."""
    inserted = updated = skipped = failed = 0

    for cycle in cycles:
        try:
            cycle_key = (
                cycle["house"],
                cycle["term"],
                cycle["session"],
                cycle["meeting"],
                cycle["start_date"],
                cycle["end_date"]
            )
            
            if cycle_key in existing_keys:
                if context:
                    context.log.info(f"[{log_prefix}] SKIPPED - Already exists: {cycle}")
                skipped += 1
                continue
            
            if context:
                context.log.info(f"[{log_prefix}] NEW cycle, posting to API: {cycle}")
            
            response = requests.post(api_endpoint, json=cycle, timeout=300)
            
            if response.status_code == 409:
                if context:
                    context.log.debug(f"[{log_prefix}] Already exists (409): {cycle}")
                skipped += 1
                continue
            
            if response.status_code == 400:
                try:
                    error_data = response.json()
                    error_message = (
                        error_data.get("detail", "")
                        or error_data.get("message", "")
                        or response.text
                    )
                except (ValueError, KeyError):
                    error_message = response.text
                
                if context:
                    context.log.error(f"[{log_prefix}] API validation error {response.status_code}: {error_message}")
                failed += 1
                continue
            
            if response.status_code >= 400:
                if context:
                    context.log.error(f"[{log_prefix}] API error {response.status_code}: {response.text}")
                failed += 1
                continue
            
            # Success responses (2xx)
            if response.status_code == 201:
                if context:
                    context.log.info(f"[{log_prefix}] Inserted: {cycle}")
                inserted += 1
                existing_keys.add(cycle_key)
            elif response.status_code == 200:
                if context:
                    context.log.info(f"[{log_prefix}] Updated: {cycle}")
                updated += 1
            else:
                if context:
                    context.log.warning(f"[{log_prefix}] Unexpected success code {response.status_code}: {cycle}")
                updated += 1
                
        except Exception as e:
            if context:
                context.log.error(f"[{log_prefix}] Failed to upsert cycle: {e}")
            failed += 1

    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
    }


# ============================================================================
# ARKIB (ARCHIVE) SCRAPER - Scrapes from archive tree structure
# ============================================================================

ARKIB_SOURCES = [
    ("https://www.parlimen.gov.my/hansard-dewan-rakyat.html?uweb=dr&arkib=yes", "dewanrakyat"),
    ("https://www.parlimen.gov.my/hansard-dewan-negara.html?uweb=dn&arkib=yes", "dewannegara"),
    ("https://www.parlimen.gov.my/hansard-dewan-khas.html?uweb=dr&arkib=yes", "kamarkhas"),
]


def _extract_parliament_number_from_text(text: str, context: Optional[AssetExecutionContext] = None) -> Optional[int]:
    """Extract parliament number from text like 'Parlimen Pertama' or 'Parlimen Kelima Belas'"""
    match = re.search(r"Parlimen\s+Ke[- ](\d+)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    match = re.search(r"Parlimen\s+(.+?)(?:\s*\(|$)", text, re.IGNORECASE)
    if match:
        ordinal_text = match.group(1).strip()
        number = malay_ordinal_to_number(ordinal_text)
        
        if number:
            return number
        elif context:
            context.log.warning(f"[arkib] could not parse parliament number from: '{text}'")
    
    return None


def _convert_penggal_to_number(text: str, context: Optional[AssetExecutionContext] = None) -> Optional[int]:
    """Convert 'Penggal' (session) to numbers"""
    match = re.search(r"Penggal\s+Ke[- ](\d+)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    match = re.search(r"Penggal\s+(.+?)(?:\s*\(|$)", text, re.IGNORECASE)
    if match:
        ordinal_text = match.group(1).strip()
        number = malay_ordinal_to_number(ordinal_text)
        if number:
            return number
        elif context:
            context.log.warning(f"[arkib] could not parse penggal number from: '{text}'")
    
    return None


def _convert_mesyuarat_to_number(mesyuarat_word: str, context: Optional[AssetExecutionContext] = None) -> Optional[int]:
    """Convert ordinal words for 'Mesyuarat' (meeting) to numbers."""
    mesyuarat_lower = mesyuarat_word.lower().strip()
    
    if mesyuarat_lower == "khas":
        return 0
    
    number = malay_ordinal_to_number(mesyuarat_lower)
    
    if number:
        return number

    if context:
        context.log.warning(f"[arkib] could not parse mesyuarat number from: '{mesyuarat_word}'")
    
    return None


def scrape_arkib_cycles(context: Optional[AssetExecutionContext] = None) -> List[Dict]:
    """Scrape parliamentary cycles from archive tree structure."""
    session = requests.Session()
    session.headers.update(HEADERS)
    verify_ssl = True
    all_cycles: List[Dict] = []

    for source_url, house_code in ARKIB_SOURCES:
        cycles = []
        
        if context:
            context.log.info(f"[arkib] Scraping {house_code} from {source_url}")

        try:
            parlimen_url = f"{source_url}&ajx=0"
            response = session.get(parlimen_url, verify=verify_ssl, timeout=60)
            response.raise_for_status()
        except requests.exceptions.SSLError:
            if context:
                context.log.warning(f"[arkib] SSL failed, retrying without verify")
            response = session.get(parlimen_url, verify=False, timeout=60)
            response.raise_for_status()
            verify_ssl = False

        try:
            root_xml = ET.fromstring(response.text)
        except ET.ParseError as e:
            if context:
                context.log.error(f"[arkib] Failed to parse XML for {house_code}: {e}")
            continue

        parlimens = root_xml.findall('.//item')
        if context:
            context.log.info(f"[arkib] Found {len(parlimens)} Parlimen entries for {house_code}")

        for parlimen_item in parlimens:
            parlimen_id = parlimen_item.get('id')
            parlimen_text = parlimen_item.get('text')
        
            parlimen_number = _extract_parliament_number_from_text(parlimen_text, context)
            if not parlimen_number:
                continue

            # Fetch penggals (sessions)
            penggal_url = f"{source_url}&ajx=1&id={parlimen_id}"
            try:
                penggal_response = session.get(penggal_url, verify=verify_ssl, timeout=60)
                penggal_response.raise_for_status()
            except requests.exceptions.SSLError:
                penggal_response = session.get(penggal_url, verify=False, timeout=60)
                penggal_response.raise_for_status()
                verify_ssl = False
            except Exception as e:
                if context:
                    context.log.error(f"[arkib] Failed to get Penggals for {parlimen_id}: {e}")
                continue
            
            try:
                penggal_xml = ET.fromstring(penggal_response.text)
            except ET.ParseError as e:
                if context:
                    context.log.error(f"[arkib] Failed to parse Penggals XML for {parlimen_id}: {e}")
                continue

            penggals = penggal_xml.findall('.//item')
            
            for penggal_item in penggals:
                penggal_id = penggal_item.get('id')
                penggal_text = penggal_item.get('text')
                
                penggal_number = _convert_penggal_to_number(penggal_text, context)
                if not penggal_number:
                    continue

                # Fetch mesyuarats (meetings)
                mesyuarat_url = f"{source_url}&ajx=1&id={penggal_id}"
                try:
                    mesyuarat_response = session.get(mesyuarat_url, verify=verify_ssl, timeout=60)
                    mesyuarat_response.raise_for_status()
                except requests.exceptions.SSLError:
                    mesyuarat_response = session.get(mesyuarat_url, verify=False, timeout=60)
                    mesyuarat_response.raise_for_status()
                    verify_ssl = False
                except Exception as e:
                    if context:
                        context.log.error(f"[arkib] Failed to get Mesyuarats for {penggal_id}: {e}")
                    continue
                
                try:
                    mesyuarat_xml = ET.fromstring(mesyuarat_response.text)
                except ET.ParseError as e:
                    if context:
                        context.log.error(f"[arkib] Failed to parse Mesyuarats XML for {penggal_id}: {e}")
                    continue

                mesyuarats = mesyuarat_xml.findall('.//item')
                
                for mesyuarat_item in mesyuarats:
                    mesyuarat_text = mesyuarat_item.get('text')

                    # Captures: Mesyuarat <Word> (DD/MM/YYYY - DD/MM/YYYY)
                    match = re.search(
                        r'Mesyuarat\s+([A-Za-z\s]+?)\s+\((\d{1,2}/\d{1,2}/\d{4})\s*-\s*(\d{1,2}/\d{1,2}/\d{4})\)',
                        mesyuarat_text,
                        re.IGNORECASE
                    )
                    
                    if not match:
                        continue
                    
                    mesyuarat_word = match.group(1).strip()
                    start_str = match.group(2)
                    end_str = match.group(3)
                    
                    try:
                        start_date = datetime.strptime(start_str, "%d/%m/%Y").date().isoformat()
                        end_date = datetime.strptime(end_str, "%d/%m/%Y").date().isoformat()
                    except ValueError as e:
                        if context:
                            context.log.warning(f"[arkib] Bad date format: {start_str} or {end_str} - {e}")
                        continue
                    
                    mesyuarat_number = _convert_mesyuarat_to_number(mesyuarat_word, context)
                    if mesyuarat_number is None:
                        continue

                    house_number = HOUSE_MAP.get(house_code)
                    if house_number is None:
                        continue

                    cycle = {
                        "start_date": start_date,
                        "end_date": end_date,
                        "house": house_number,
                        "term": parlimen_number,
                        "session": penggal_number,
                        "meeting": mesyuarat_number,
                    }
                    
                    cycles.append(cycle)

        all_cycles.extend(cycles)
        if context:
            context.log.info(f"[arkib] Found {len(cycles)} cycles for {house_code}")

    # Deduplicate
    unique = {}
    for c in all_cycles:
        key = (c["house"], c["term"], c["session"], c["meeting"], c["start_date"], c["end_date"])
        unique[key] = c

    cycles = list(unique.values())
    
    if context:
        context.log.info(f"[arkib] Total unique cycles scraped: {len(cycles)}")

    return cycles


# ============================================================================
# ACTIVE SCRAPER - Scrapes from main page display
# ============================================================================

ACTIVE_SOURCES = [
    ("https://www.parlimen.gov.my/hansard-dewan-rakyat.html?uweb=dr&lang=bm", "dewanrakyat"),
    ("https://www.parlimen.gov.my/hansard-dewan-negara.html?uweb=dn&lang=bm", "dewannegara"),
    ("https://www.parlimen.gov.my/hansard-dewan-khas.html?uweb=dr&lang=bm", "kamarkhas"),
]


def parse_malay_date(date_str: str) -> Optional[str]:
    """Parse Malay date string to YYYY-MM-DD format"""
    try:
        match = re.search(r'(\d+)\s+(\w+)\s+(\d{4})', date_str.lower())
        if match:
            day = int(match.group(1))
            month_name = match.group(2)
            year = int(match.group(3))
            
            month = MALAY_MONTHS.get(month_name)
            if month:
                return f"{year:04d}-{month:02d}-{day:02d}"
    except Exception as e:
        print(f"Error parsing date '{date_str}': {e}")
    return None


def scrape_active_cycles(context: Optional[AssetExecutionContext] = None) -> List[Dict]:
    """Scrape active parliamentary cycles from main pages."""
    all_cycles = []
    
    for url, house_folder in ACTIVE_SOURCES:
        house_code = HOUSE_MAP.get(house_folder)
        if house_code is None:
            if context:
                context.log.error(f"[active] Invalid house_folder: {house_folder}")
            continue
        
        if context:
            context.log.info(f"[active] Scraping {house_folder} from {url}")
        
        try:
            response = requests.get(url, verify=False, timeout=30)
            response.raise_for_status()
        except requests.exceptions.SSLError:
            if context:
                context.log.warning(f"[active] SSL failed for {url}, retrying without verify")
            response = requests.get(url, verify=False, timeout=30)
            response.raise_for_status()
        except Exception as e:
            if context:
                context.log.error(f"[active] Error scraping {house_folder}: {e}")
            continue
        
        soup = BeautifulSoup(response.text, 'html.parser')
        text_content = soup.get_text()
        
        # Search for pattern: "Mesyuarat Pertama, Penggal Kelima Parlimen Kelima Belas (2026)"
        session_pattern = r'Mesyuarat\s+(\w+(?:\s+\w+)?),\s+Penggal\s+(\w+(?:\s+\w+)?)\s+Parlimen\s+(\w+(?:\s+\w+)?)\s+\((\d{4})\)'
        session_matches = re.finditer(session_pattern, text_content, re.IGNORECASE)
        
        for match in session_matches:
            meeting_text = match.group(1)
            session_text = match.group(2)
            term_text = match.group(3)
            year = match.group(4)
            
            # Parse ordinal numbers
            meeting_number = malay_ordinal_to_number(meeting_text)
            session_number = malay_ordinal_to_number(session_text)
            term_number = malay_ordinal_to_number(term_text)
            
            if not all([meeting_number, session_number, term_number]):
                if context:
                    context.log.warning(f"[active] Could not parse numbers from: {match.group(0)}")
                continue
            
            # Search for date range pattern near the session info
            date_pattern = r'(\d{1,2}\s+\w+\s+\d{4})\s*-\s*(\d{1,2}\s+\w+\s+\d{4})'
            date_match = re.search(date_pattern, text_content[max(0, match.start()-200):match.end()+200])
            
            if not date_match:
                if context:
                    context.log.warning(f"[active] No date range found for session")
                continue
            
            start_date_str = date_match.group(1)
            end_date_str = date_match.group(2)
            
            start_date = parse_malay_date(start_date_str)
            end_date = parse_malay_date(end_date_str)
            
            if not start_date or not end_date:
                if context:
                    context.log.warning(f"[active] Could not parse dates: {start_date_str} - {end_date_str}")
                continue
            
            cycle = {
                "house": house_code,
                "term": term_number,
                "session": session_number,
                "meeting": meeting_number,
                "start_date": start_date,
                "end_date": end_date,
            }
            
            all_cycles.append(cycle)
            
            if context:
                context.log.info(
                    f"[active] Found: P{term_number}, S{session_number}, M{meeting_number} "
                    f"({start_date} to {end_date})"
                )
            break
    
    if context:
        context.log.info(f"[active] Total active cycles found: {len(all_cycles)}")
    
    return all_cycles
