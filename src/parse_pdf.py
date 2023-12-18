"""Accepts PDF Hansards and produces five files as preprocessing.

The five files are:
1. plaintext.txt: raw text extracted from PDF
2. bold.txt: 1 if bold, 0 otherwise. Whitespace characters as is
3. italics.txt: 1 if italic, 0 otherwise. Whitespace characters as is
4. tables.txt: json of tables
5. attendance.txt: raw text from the attendance section (for DR-26072021 onwards)
"""

import argparse
import re

import pdfplumber
import os
import json
import pandas as pd
from tqdm import tqdm
from pathlib import Path
from config import DEFAULT_DATA_DIR, BASE_PATH


def not_invisible_rect(obj):
    if obj["object_type"] != "rect":
        return True
    if isinstance(obj["non_stroking_color"], int) or isinstance(
            obj["non_stroking_color"], float
    ):
        return obj["non_stroking_color"] < 0.9
    return not (min(obj["non_stroking_color"]) > 0.9)


def parse_hansard(hansard_date, house, source_dir=DEFAULT_DATA_DIR):
    print(f"Parsing {hansard_date} {house}")
    year = hansard_date[-4:]
    bold = []
    italics = []
    tables = []
    text = ""
    dir_path = BASE_PATH / "parsed_pdf" / house / year
    dir_path.mkdir(parents=True, exist_ok=True)
    sortable_date = (
        f"{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}"  # YYYY-MM-DD
    )
    dir_path = dir_path / sortable_date
    dir_path.mkdir(parents=True, exist_ok=True)

    # only parse attendance list for DR-26072021 onwards
    # DN attendance parsing not supported
    has_attendance = (
            pd.to_datetime(sortable_date) >= pd.to_datetime("2021-07-26")
            and house.upper() == "DR"
    )

    doa_seen = False
    doa_idx = -1
    with pdfplumber.open(source_dir / f"{house.upper()}-{hansard_date}.pdf") as pdf:
        extract_attn_start = False
        attn_text = ""
        for idx, page in enumerate(tqdm(pdf.pages)):
            extracted = page.extract_text()
            if not doa_seen:
                # extract attendance list before DOA section
                if has_attendance and "ahli-ahli yang hadir" in extracted.lower():
                    extract_attn_start = True
                    attn_text += extracted
                    print("Ahli-Ahli Yang Hadir", page)
                    continue
                if "DOA" in extracted:
                    doa_seen = True
                    doa_idx = idx
                    extract_attn_start = False  # stop extracting attendance list
                else:
                    if extract_attn_start:
                        attn_text += extracted
                    continue
            text += extracted + "\n"  # add newline to separate pages
            if hansard_date == "09072019" or (house == "kkdr" and hansard_date == "15112023"):
                # special case where snap tolerance doesn't work
                current_tables = page.filter(not_invisible_rect).extract_tables()
            elif hansard_date == "31102023":
                current_tables = page.filter(not_invisible_rect).extract_tables(
                    {"snap_x_tolerance": 9}
                )
            else:
                current_tables = page.filter(not_invisible_rect).extract_tables(
                    {"snap_tolerance": 9}
                )
            if current_tables:
                # add page number
                tables += [
                    [idx, idx - doa_idx + 1, current_tables]
                ]  # first wrapping is for appending. Want to preserve array structure
                # the structure is then
                # [ # master array
                #   [ page number, page number relative to DOA,
                #       tables
                #   ]
                # ]
                # where the tables is a list (tables) of lists (table) of lists (row) where final items are the cells

            formatted_words = page.extract_words(extra_attrs=["fontname"])
            for word in formatted_words:
                is_bold = 0
                if "bold" in word["fontname"].lower():
                    is_bold = 1
                is_italic = 0
                if "italic" in word["fontname"].lower():
                    is_italic = 1
                bold += [is_bold] * len(word["text"])
                italics += [is_italic] * len(word["text"])

    assert len(bold) == len(
        italics
    ), f"Length of bold and italics do not match: {len(bold)} vs {len(italics)}"
    raw_text = re.sub(r"\s+", "", text)
    assert len(bold) == len(
        raw_text
    ), f"Length of bold and raw_text do not match: {len(bold)} vs {len(raw_text)}"
    # add whitespace to bold and italics using the raw text layout
    spaced_bold = ""
    spaced_italics = ""
    # to improve time complexity, reverse the string and pop from the end
    bold.reverse()
    italics.reverse()
    for char in text:
        if char.isspace():
            spaced_bold += char
            spaced_italics += char
        else:
            spaced_bold += str(bold.pop())
            spaced_italics += str(italics.pop())
    assert len(bold) == 0, f"Not all bold characters were processed: {len(bold)}"
    assert (
            len(italics) == 0
    ), f"Not all italic characters were processed: {len(italics)}"

    with open(str(dir_path / "plaintext.txt"), "w") as f:
        f.write(text)
    with open(str(dir_path / "bold.txt"), "w") as f:
        f.write(spaced_bold)
    with open(str(dir_path / "italics.txt"), "w") as f:
        f.write(spaced_italics)
    with open(str(dir_path / "tables.json"), "w") as f:
        json.dump(tables, f, indent=4)
    if has_attendance:
        with open(str(dir_path / "attendance.txt"), "w") as f:
            f.write(attn_text)

    # for global logging
    if tables:
        with open(f"dump/{house}/hansards_with_tables.txt", "a") as f:
            f.write(f"{sortable_date}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "hansard_date", help="hansard_date eg. 23052023", default="15112023", nargs="?"
    )
    parser.add_argument(
        "house",
        help="parliament house. Possible values: 'dr' or 'dn'",
        choices=["dr", "dn", "kkdr"],
        default="kkdr", nargs="?"
    )
    # optional directory argument
    parser.add_argument(
        "--source_dir",
        help="directory to Hansard PDFs",
        default=DEFAULT_DATA_DIR,
        nargs="?",
    )
    # Parse arguments
    args = parser.parse_args()
    parse_hansard(args.hansard_date, args.house, args.source_dir)
