import re
import string
import logging
import pandas as pd
from datetime import datetime

# Heavy libraries (malaya, nltk) are imported lazily to reduce cold-start time and avoid
# race conditions creating cache directories during parallel Dagster process startup.
malaya = None  # will be imported on first use
nltk = None  # will be imported on first use
get_stopwords = None  # resolved after malaya import

# Lazy init state containers
_malaya_tokenizer = None
_stopwords_bm = None
_stopwords_en = None
_stopwords_all = None

stopwords_mhc = [
    "ada",
    "adakah",
    "adakan",
    "adalah",
    "adanya",
    "adapun",
    "agak",
    "agar",
    "akan",
    "akhir",
    "aku",
    "akulah",
    "akupun",
    "al",
    "alangkah",
    "allah",
    "amat",
    "antara",
    "antaramu",
    "antaranya",
    "apa",
    "apa-apa",
    "apabila",
    "apakah",
    "apapun",
    "atas",
    "atasmu",
    "atasnya",
    "atau",
    "ataukah",
    "ataupun",
    "bagai",
    "bagaimana",
    "bagaimanakah",
    "bagaimanapun",
    "bagi",
    "bagimu",
    "baginya",
    "bagitu",
    "bahawa",
    "bahkan",
    "bahwa",
    "banyak",
    "banyaknya",
    "barangkali",
    "barangsiapa",
    "bawah",
    "beberapa",
    "begitu",
    "begitupun",
    "belaka",
    "beliau",
    "belum",
    "belumkah",
    "ber",
    "berada",
    "berapa",
    "berhormat",
    "berikan",
    "berikut",
    "berkaitan",
    "berkenaan",
    "berupa",
    "beserta",
    "biarpun",
    "bila",
    "bilakah",
    "bilamana",
    "bilangan",
    "bin",
    "binti",
    "bisa",
    "boleh",
    "bukan",
    "bukankah",
    "bukanlah",
    "che",
    "chuma",
    "cuma",
    "dah",
    "dahulu",
    "dalam",
    "dalamnya",
    "dan",
    "dapat",
    "dapati",
    "dapatkah",
    "dapatlah",
    "dari",
    "daripada",
    "daripadaku",
    "daripadamu",
    "daripadanya",
    "dato",
    "datuk",
    "demi",
    "demikian",
    "demikianlah",
    "dengan",
    "dengannya",
    "di",
    "dia",
    "dialah",
    "didapat",
    "didapati",
    "dimanakah",
    "dua",
    "empat",
    "enam",
    "enche",
    "engkau",
    "engkaukah",
    "engkaulah",
    "engkaupun",
    "hai",
    "hajah",
    "haji",
    "hal",
    "hampir",
    "sebagai",
    "hampir-hampir",
    "hanya",
    "hanyalah",
    "harus",
    "hendak",
    "hendaklah",
    "hingga",
    "ia",
    "iaitu",
    "ialah",
    "ianya",
    "ii",
    "ingin",
    "inginkah",
    "ini",
    "inikah",
    "inilah",
    "itu",
    "itukah",
    "itulah",
    "izin",
    "jadi",
    "jangan",
    "janganlah",
    "jika",
    "jikalau",
    "jua",
    "juapun",
    "juga",
    "jumlah",
    "ka",
    "kadang",
    "kah",
    "kalangan",
    "kalau",
    "kali",
    "kami",
    "kamikah",
    "kamipun",
    "kamu",
    "sentiasa",
    "kamukah",
    "kamupun",
    "kan",
    "kapada",
    "katakan",
    "ke",
    "kedua",
    "kemudian",
    "kenapa",
    "kepada",
    "kerajaan",
    "kerana",
    "ketawa",
    "ketiga",
    "ketika",
    "khusus",
    "kini",
    "kita",
    "ku",
    "kurang",
    "lagi",
    "lah",
    "lain",
    "lalu",
    "lamanya",
    "langsung",
    "lebeh",
    "lebih",
    "lima",
    "macam",
    "macham",
    "maha",
    "mahu",
    "mahukah",
    "mahupun",
    "maka",
    "makin",
    "malah",
    "mana",
    "manakah",
    "manakala",
    "manapun",
    "maseh",
    "masih",
    "masing",
    "masing-masing",
    "md",
    "melainkan",
    "mem",
    "memang",
    "mempunyai",
    "men",
    "mendapat",
    "mendapati",
    "mendapatkan",
    "mengadakan",
    "mengapa",
    "mengapakah",
    "mengenai",
    "menjadi",
    "menyebabkan",
    "menyebabkannya",
    "mereka",
    "merekalah",
    "merekapun",
    "meskipun",
    "mesti",
    "misalnya",
    "mu",
    "mungkin",
    "nak",
    "namun",
    "nanti",
    "nescaya",
    "niscaya",
    "nya",
    "okey",
    "olah",
    "oleh",
    "orang",
    "pada",
    "padahal",
    "padanya",
    "padamu",
    "paling",
    "para",
    "pasti",
    "patut",
    "patutkah",
    "pelbagai",
    "per",
    "pergilah",
    "perkara",
    "perkaranya",
    "perlu",
    "pernah",
    "pertama",
    "ptg",
    "puan",
    "pula",
    "pun",
    "punya",
    "ra",
    "ramai",
    "riuh",
    "sa",
    "sadikit",
    "sahaja",
    "saja",
    "saling",
    "sama",
    "samakah",
    "sama-sama",
    "sambil",
    "sampai",
    "samping",
    "sana",
    "sangat",
    "sangatlah",
    "saperti",
    "satu",
    "saya",
    "se",
    "seandainya",
    "sebab",
    "sebagaimana",
    "sebagainya",
    "sebanyak",
    "sebarang",
    "sebelum",
    "sebelummu",
    "sebelumnya",
    "sebenarnya",
    "sebuah",
    "secara",
    "sedang",
    "sedangkan",
    "sedikit",
    "sedikitpun",
    "segala",
    "sehingga",
    "sejak",
    "sejauh",
    "sekali",
    "sekalian",
    "sekalipun",
    "sekarang",
    "sekejap",
    "sekian",
    "sekiranya",
    "sekitar",
    "sekurang",
    "selain",
    "selalu",
    "selama",
    "selama-lamanya",
    "selepas",
    "seluruh",
    "seluruhnya",
    "semakin",
    "semasa",
    "sementara",
    "semua",
    "semuanya",
    "semula",
    "senantiasa",
    "sendiri",
    "seolah",
    "seolah-olah",
    "seorang",
    "seorangpun",
    "separuh",
    "sepatutnya",
    "seperti",
    "seraya",
    "seri",
    "sering",
    "serta",
    "seseorang",
    "sesiapa",
    "sesuatu",
    "sesudah",
    "sesudahnya",
    "sesungguhnya",
    "sesungguhnyakah",
    "setakat",
    "setelah",
    "seterusnya",
    "setiap",
    "siapa",
    "siapakah",
    "sikit",
    "sini",
    "situ",
    "situlah",
    "sri",
    "suatu",
    "sudah",
    "sudahkah",
    "sunggoh",
    "sungguhpun",
    "supaya",
    "ta",
    "tadi",
    "tadinya",
    "tahu",
    "tahukah",
    "tak",
    "tanpa",
    "tanya",
    "tanyakanlah",
    "tapi",
    "telah",
    "tentang",
    "tentu",
    "tepuk",
    "terdapat",
    "terhadap",
    "terhadapmu",
    "terlalu",
    "termasuk",
    "terpaksa",
    "tersebut",
    "tertentu",
    "terus",
    "terutama",
    "terutamanya",
    "tetapi",
    "tiada",
    "tiadakah",
    "tiadalah",
    "tiap",
    "tiap-tiap",
    "tidak",
    "tidakkah",
    "tidaklah",
    "tiga",
    "tuan",
    "turut",
    "umpama",
    "untok",
    "untuk",
    "untukmu",
    "wahai",
    "walau",
    "walaupun",
    "ya",
    "yaini",
    "yaitu",
    "yakni",
    "yang",
]

custom_sw = [
    "menteri",
    "kementerian",
    "malaysia",
    "negara",
    "di-pertua",
    "peratus",
    "pertua",
    "isu",
    "akta",
    "bahas",
    "rm",
    "di",
    "dasar",
    "dewan",
    "parlimen",
    "ahli",
    "mohon",
]
custom_sp = ["terima kasih", "di pertua"]

# most of the settings here doesn't actually remove - not working
def _ensure_malaya():
    global malaya, get_stopwords, _malaya_tokenizer, _stopwords_bm
    if malaya is None:
        import malaya as _malaya
        from malaya.text.function import get_stopwords as _get_stopwords
        malaya = _malaya
        # resolve function reference
        globals()['get_stopwords'] = _get_stopwords
    if _malaya_tokenizer is None:
        _malaya_tokenizer = malaya.tokenizer.Tokenizer(
            numbers=False,
            title=False,
            percents=False,
            money=False,
            date=False,
            time=False,
            pukul=False,
            distance=False,
            temperature=False,
            volume=False,
            duration=False,
            weight=False,
        )
    if _stopwords_bm is None:
        stopwords_malaya = get_stopwords()
        _stopwords_bm = list(set(stopwords_mhc + stopwords_malaya + custom_sw))


def _ensure_nltk():
    global nltk, _stopwords_en
    if nltk is None:
        import nltk as _nltk
        nltk = _nltk
    if _stopwords_en is None:
        try:
            _stopwords_en = nltk.corpus.stopwords.words("english")
        except LookupError:
            nltk.download("stopwords")
            _stopwords_en = nltk.corpus.stopwords.words("english")


def _get_all_stopwords():
    global _stopwords_all
    if _stopwords_all is None:
        _ensure_malaya()
        _ensure_nltk()
        _stopwords_all = _stopwords_bm + _stopwords_en
    return _stopwords_all


class HouseMapping:
    """
    Class to handle mapping between different representations of Malaysian parliamentary houses.
    Provides methods to convert between:
    - canonical (dewanrakyat, dewannegara, kamarkhas)
    - code (dr, dn, kkdr)
    - display (dewan-rakyat, dewan-negara, kamar-khas)

    All methods are case-insensitive for input values.
    """

    def __init__(self):
        self._canonical_to_code = {
            "dewanrakyat": "dr",
            "dewannegara": "dn",
            "kamarkhas": "kkdr",
        }

        self._canonical_to_display = {
            "dewanrakyat": "dewan-rakyat",
            "dewannegara": "dewan-negara",
            "kamarkhas": "kamar-khas",
        }

        self._build_mappings()

    def _build_mappings(self):
        """Build all derived mappings"""
        # Create reverse mappings
        self._code_to_canonical = {v: k for k, v in self._canonical_to_code.items()}
        self._display_to_canonical = {
            v: k for k, v in self._canonical_to_display.items()
        }

        # Create direct mappings for convenience
        self._code_to_display = {
            code: self._canonical_to_display[canon]
            for code, canon in self._code_to_canonical.items()
        }
        self._display_to_code = {
            display: self._canonical_to_code[canon]
            for display, canon in self._display_to_canonical.items()
        }

        # Create case-insensitive lookup maps
        self._lowercase_canonical = {
            k.lower(): k for k in self._canonical_to_code.keys()
        }
        self._lowercase_code = {k.lower(): k for k in self._code_to_canonical.keys()}
        self._lowercase_display = {
            k.lower(): k for k in self._display_to_canonical.keys()
        }

    def to_code(self, house):
        """Convert any representation to code format (dr, dn, kkdr)"""
        canonical = self._to_canonical(house)
        return self._canonical_to_code.get(canonical, house)

    def to_display(self, house):
        """Convert any representation to display format (dewan-rakyat, dewan-negara, kamar-khas)"""
        canonical = self._to_canonical(house)
        return self._canonical_to_display.get(canonical, house)

    def to_canonical(self, house):
        """Convert any representation to canonical format (dewanrakyat, dewannegara, kamarkhas)"""
        return self._to_canonical(house)

    def display_to_code(self, display):
        """Convert directly from display format to code format"""
        return self._display_to_code.get(self._normalize_display(display), display)

    def code_to_display(self, code):
        """Convert directly from code format to display format"""
        return self._code_to_display.get(self._normalize_code(code), code)

    def _normalize_canonical(self, house):
        """Normalize canonical format for case-insensitive lookup"""
        if not house:
            return house
        house_lower = house.lower()
        return self._lowercase_canonical.get(house_lower, house)

    def _normalize_code(self, code):
        """Normalize code format for case-insensitive lookup"""
        if not code:
            return code
        code_lower = code.lower()
        return self._lowercase_code.get(code_lower, code)

    def _normalize_display(self, display):
        """Normalize display format for case-insensitive lookup"""
        if not display:
            return display
        display_lower = display.lower()
        return self._lowercase_display.get(display_lower, display)

    def _to_canonical(self, house):
        """Internal method to convert to canonical format"""
        if not house:
            return house

        house_lower = house.lower()

        # Check if it's already a canonical format
        if house_lower in self._lowercase_canonical:
            return self._lowercase_canonical[house_lower]

        # Check if it's a code
        if house_lower in self._lowercase_code:
            normalized_code = self._lowercase_code[house_lower]
            return self._code_to_canonical[normalized_code]

        # Check if it's a display format
        if house_lower in self._lowercase_display:
            normalized_display = self._lowercase_display[house_lower]
            return self._display_to_canonical[normalized_display]

        return house


# Create a global instance for use throughout the codebase
house_mapper = HouseMapping()

# For backwards compatibility
house_map = house_mapper._canonical_to_code
house_map_reverse = house_mapper._code_to_canonical
house_map_with_dash = house_mapper._canonical_to_display


def preprocess_malaya(speech):
    if pd.isnull(speech):
        return speech
    # remove numbers
    speech = re.sub(r"\b\d+\b", "", speech)
    # remove custom list of stop phrases
    for sp in custom_sp:
        speech = re.sub(sp, "", speech, flags=re.IGNORECASE)
    # remove stopwords, punctuation, tokenise then stem
    # Lazy init heavy resources only when this function is actually used.
    _ensure_malaya()
    toks = []
    stopwords_all = _get_all_stopwords()
    for tok in _malaya_tokenizer.tokenize(speech, lowercase=True):
        if tok in stopwords_all:
            continue
        if any(subtok in string.punctuation + "–" for subtok in tok):
            continue
        toks.append(tok)
    return [x for x in toks if x != ""]


def _process_line_breaks(speech):
    """Processes stray line breaks, while detecting and preserving valid paragraph breaks."""
    if type(speech) is not str:
        return speech
    # List of sentence-ending punctuation
    punctuation = [".", "!", "?", "...", ":", ":-"]

    lines = speech.split("\n")
    processed_lines = []

    for i in range(len(lines)):
        # Check if next line starts with bullet point pattern eg (a), (b)
        is_next_bullet = i < len(lines) - 1 and lines[i + 1].startswith(("(", ") "))

        # Check if line is part of a markdown table
        is_markdown_table = re.match(r"\|\s*[^|]+\s*\|\s*[^|]+\s*\|", lines[i])

        # Check if line is the end of a markdown table
        if "<END_TABLE_MARKER>" in lines[i]:
            lines[i] = lines[i].replace("<END_TABLE_MARKER>", "\n\n")

        # If the line ends with a punctuation mark, is the last line, or next line starts with bullet point, append with newline
        if (
            i == len(lines) - 1
            or lines[i].endswith(tuple(punctuation))
            or is_next_bullet
        ):
            processed_lines.append(lines[i])
            if i != len(lines) - 1:  # Don't add a newline after the last line
                processed_lines.append("\n\n")
        elif is_markdown_table:
            # If line is part of a markdown table, append it with a newline
            processed_lines.append("\n" + lines[i])
        else:
            # Otherwise, append it with a space (to merge with the next line)
            processed_lines.append(lines[i] + " ")

    # Join the processed lines back
    return "".join(processed_lines)


def _merge_authored_annotations(df_all):
    """
    Fix NaN speeches - merge ANNOTATION rows with preceding row with NaN speaker/author
    """
    df_all = df_all.reset_index(drop=True)
    index_to_remove = []
    rows_to_fill = []

    for index, row in df_all.iterrows():
        if pd.isna(row["proc_speech"]):
            index_to_remove.append(index + 1)
            next_index = index + 1

            if (
                next_index < len(df_all)
                and df_all.at[next_index, "author"] == "ANNOTATION"
            ):
                # print(f"Plan to fill {index} with {df_all.at[next_index, 'proc_speech']}")
                rows_to_fill.append(
                    (index, next_index, df_all.at[next_index, "proc_speech"])
                )

    # Fill the 'speech' column for the selected rows
    for fill_index, next_index, speech_value in rows_to_fill:
        df_all.at[fill_index, "proc_speech"] = speech_value
        df_all.at[fill_index, "is_annotation"] = True

    print(f"before drop: {df_all.shape[0]}")
    df_all = df_all.drop(index_to_remove)
    print(f"after drop: {df_all.shape[0]}")
    return df_all


def process_tabulated(df_all: pd.DataFrame, house: str):
    """Read parsed and tabulated CSV files.

    Processing applied:
    - Process and fix line breaks
    - Replace table markers with double newlines
    - [TEMP] Fill NaN author with empty string
    - Fill empty
    - Tag annotations with 'is_annotation' column

    Returns:
    - DataFrame of all speeches in csv_paths
    New columns:
    - 'proc_speech': Processed speech text
    - 'house': House of the sitting
    - 'is_annotation': Boolean column to tag annotations
    """

    df_all["length"] = df_all.speech.str.split().str.len()
    df_all["date"] = pd.to_datetime(df_all.date)
    df_all["proc_speech"] = df_all.speech.map(_process_line_breaks)

    df_all.level_1 = df_all.level_1.fillna("")
    df_all.level_2 = df_all.level_2.fillna("")
    df_all.level_3 = df_all.level_3.fillna("")

    # remove line breaks from all level headings
    df_all.level_1 = df_all.level_1.str.replace("\n", " ").str.strip()
    df_all.level_2 = df_all.level_2.str.replace("\n", " ").str.strip()
    df_all.level_3 = df_all.level_3.str.replace("\n", " ").str.strip()

    # Null out empty level headings
    df_all.level_1 = df_all.level_1.apply(lambda x: None if x == "" else x)
    df_all.level_2 = df_all.level_2.apply(lambda x: None if x == "" else x)
    df_all.level_3 = df_all.level_3.apply(lambda x: None if x == "" else x)

    df_all["house"] = house

    # create new is_annotation column - to keep track of authored speeches that are pure annotations
    df_all["is_annotation"] = df_all.author.apply(
        lambda speech: True if speech == "ANNOTATION" else False
    )
    df_all = _merge_authored_annotations(df_all)
    return df_all


def _to_postgresql_array_string(py_list):
    # Convert all elements to string and escape double quotes
    formatted_elements = [
        '"{}"'.format(str(element).replace('"', '\\"')) for element in py_list
    ]

    # Join the elements and wrap them in curly braces
    return "{" + ", ".join(formatted_elements) + "}"


def _add_to_result(levels, data, result):
    # If no heading, append data directly to result
    if not any(levels):
        result.append(data)
        return

    # For cases with headings
    current_level = result
    for level in levels:
        if not level:  # Skip empty levels
            continue

        # Check if current level has the heading
        found = False
        for item in current_level:
            if level in item:
                current_level = item[level]
                found = True
                break

        # If not found, create new entry
        if not found:
            new_entry = {level: []}
            current_level.append(new_entry)
            current_level = new_entry[level]

    # Append the data
    current_level.append(data)


def speeches_to_json(df_sitting):
    result = []
    for index, row in df_sitting.iterrows():
        speech_dict = {
            "speech": row["proc_speech"],
            "author": row["author"] if pd.notna(row["author"]) else None,
            "author_id": int(row["speaker"]) if pd.notna(row["speaker"]) else None,
            "timestamp": row["timestamp"],
            "is_annotation": row["is_annotation"],
            "index": row["index"],
        }

        # Create a list with levels
        levels = [
            level
            for level in [row["level_1"], row["level_2"], row["level_3"]]
            if pd.notna(level)
        ]

        # Add to result
        _add_to_result(levels, speech_dict, result)
    return result


def extract_pdf_url(js_string):
    # Define the regular expression pattern to match the PDF URL
    pattern = r"loadResult\('([^']*\.pdf)'"

    # Search for the pattern in the given JavaScript string
    match = re.search(pattern, js_string)

    # If a match is found, extract and return the URL
    if match:
        return match.group(1)
    else:
        return None


def rename_pdf(filename):
    """DR-DDMMYYYY.pdf -> dr_yyyy-mm-dd.pdf"""
    match = re.search(r"(DR|DN|KKDR)-(\d{2})(\d{2})(\d{4})", filename, re.IGNORECASE)
    if match is not None:
        house, day, month, year = match.groups()
        new_filename = f"{house.lower()}_{year}-{month}-{day}"
        return new_filename
    else:
        # if fail to detect filename format, return the original filename
        return filename


def reverse_date_format(date_str):
    """YYYY-MM-DD -> DDMMYYYY"""
    year, month, day = date_str.split("-")
    return f"{day}{month}{year}"


def get_sitting_object(pdf_file_key: str, logger=None):
    """Convert PDF file key to house, date_str and datetime
    
    Args:
        pdf_file_key: Filename like 'DR-12122024' or 'DR-12122024.pdf' or 'DN01051961.pdf' (no dash)
        
    Returns:
        Dict containing house, date, and filename information
        
    Raises:
        ValueError: If the filename format is invalid
    """
    log = logger if logger else logging

    # Strip whitespace and remove extensions (case-insensitive)
    # Handle cases like .pdf, .genpro.pdf, .PindaanTimMDN, etc.
    # Expected formats: 
    # - DR-12122024 or DN-12122024 or KKDR-12122024 (with dash)
    # - DN01051961 or DR12122024 (without dash)
    base_name = pdf_file_key.strip()
    
    # Remove all extensions - keep removing until no more dots or last part is all digits
    while '.' in base_name:
        last_part = base_name.split('.')[-1]
        # Only keep the last part if it's all digits (part of date format)
        if not last_part.isdigit():
            base_name = base_name.rsplit('.', 1)[0]
        else:
            break
    
    # Remove trailing patterns like (1), (2), (3), etc. or [1], [2], etc.
    base_name = re.sub(r'\s*[\(\[][0-9]+[\)\]]\s*$', '', base_name)
    
    # Remove trailing dash followed by small number (e.g., -1, -2, -3) but NOT dates (8 digits)
    base_name = re.sub(r'-[0-9]{1,3}$', '', base_name)
    
    # Keep only the house-date portion (e.g., DR-12122024 from DR-12122024_Updated)
    if "_" in base_name:
        base_name = base_name.split("_")[0]
    
    base_name = base_name.strip()
    
    # Try to parse with dash first
    if "-" in base_name:
        parts = base_name.split("-")
        if len(parts) < 2:
            log.warning("Invalid filename format (missing date part) - expected format like 'DR-12122024', skipped: '%s'", pdf_file_key)
            return None
        
        house = parts[0].strip().upper()  # DR
        date_str = parts[1].strip()  # 12122024
    else:
        # No dash - try to extract house code and date
        # Expected formats: DN01051961, DR12122024, KKDR12122024
        # House codes: DR (2 chars), DN (2 chars), KKDR (4 chars)
        
        if base_name.startswith(("KKDR", "kkdr")):
            house = base_name[:4].upper()  # KKDR
            date_str = base_name[4:].strip()  # 12122024
        elif len(base_name) >= 10:  # Minimum: 2 char house + 8 char date
            house = base_name[:2].upper()  # DR or DN
            date_str = base_name[2:].strip()  # 12122024 or 01051961
        else:
            log.warning("Invalid filename format (too short) - expected format like 'DR-12122024' or 'DN01051961', skipped: '%s'", pdf_file_key)
            return None
    
    # Validate house code
    try:
        house_folder = house_mapper.to_canonical(house.lower())  # dr -> dewanrakyat (for s3)
    except (KeyError, AttributeError) as e:
        log.warning("Invalid house code: '%s' in filename '%s', skipped", house, pdf_file_key)
        return None
    
    # Validate and fix date format
    if not date_str.isdigit():
        log.warning("Invalid date format (non-digit) '%s' in filename '%s' - contains non-digit characters, skipped", date_str, pdf_file_key)
        return None
    
    # Handle 7-digit dates by padding with leading zero (e.g., 1032023 -> 01032023)
    if len(date_str) == 7:
        date_str = '0' + date_str
        log.warning(f"Padded 7-digit date in filename '{pdf_file_key}': now using '{date_str}'")
    # Handle 9-digit dates by removing extra zero (e.g., 140022023 -> 14022023)
    elif len(date_str) == 9:
        # Try removing character at position 2 (extra 0 after day)
        fixed_date = date_str[:2] + date_str[3:]
        try:
            datetime.strptime(fixed_date, "%d%m%Y")
            date_str = fixed_date
            log.warning(f"Fixed 9-digit date in filename '{pdf_file_key}': removed extra digit at position 2, now using '{date_str}'")
        except ValueError:
            # Try removing character at position 3 instead
            fixed_date = date_str[:3] + date_str[4:]
            try:
                datetime.strptime(fixed_date, "%d%m%Y")
                date_str = fixed_date
                log.warning(f"Fixed 9-digit date in filename '{pdf_file_key}': removed extra digit at position 3, now using '{date_str}'")
            except ValueError:
                log.warning("Invalid date format '%s' in filename '%s' - expected DDMMYYYY (8 digits), skipped", date_str, pdf_file_key)
                return None
    elif len(date_str) != 8:
        log.warning("Invalid date format '%s' in filename '%s' - expected DDMMYYYY (8 digits), skipped", date_str, pdf_file_key)
        return None

    try:
        date = datetime.strptime(date_str, "%d%m%Y")
    except ValueError as e:
        log.warning("Invalid date: '%s' in filename '%s', skipped", date_str, pdf_file_key)
        return None

    proper_date_str = date.strftime("%Y-%m-%d")  # 2024-12-12 or 1961-05-01
    original_filename = base_name + ".pdf"
    renamed_filename = rename_pdf(base_name)  # DR-12122024 -> dr_2024-12-12
    renamed_filename_key = (
        f"{house_folder}/{renamed_filename}.pdf"  # dewanrakyat/dr_2024-12-12.pdf
    )
    
    return {
        "house": house,  # DR
        "house_folder": house_folder,  # dewanrakyat
        "house_display": house_mapper.to_display(house),  # dewan-rakyat
        "date_str": date_str,  # 12122024
        "proper_date_str": proper_date_str,  # 2024-12-12
        "date": date,
        "original_filename": original_filename,
        "renamed_filename": renamed_filename,  # dr_2024-12-12
        "renamed_filename_key": renamed_filename_key,  # dewanrakyat/dr_2024-12-12.pdf
    }
