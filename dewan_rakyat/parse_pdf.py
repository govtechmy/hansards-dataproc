"""Accepts PDF Hansards and produces four files as preprocessing.

The four files are:
1. plaintext.txt: raw text extracted from PDF
2. bold.txt: 1 if bold, 0 otherwise. Whitespace characters as is
3. italics.txt: 1 if italic, 0 otherwise. Whitespace characters as is
4. tables.txt: json of tables
"""

import argparse
import re

import pdfplumber
import os
from tqdm import tqdm
import json


def not_invisible_rect(obj):
    if obj["object_type"] != "rect":
        return True
    if isinstance(obj["non_stroking_color"], int) or isinstance(
        obj["non_stroking_color"], float
    ):
        return obj["non_stroking_color"] < 0.9
    return not (min(obj["non_stroking_color"]) > 0.9)


def parse_hansard(hansard_date):
    print(f"Parsing {hansard_date}")
    year = hansard_date[-4:]
    bold = []
    italics = []
    tables = []
    text = ""
    base_path = os.path.dirname(os.path.realpath(__file__))
    dir_path = f"{base_path}/parsed_pdf/"
    if not os.path.isdir(dir_path):
        os.mkdir(dir_path)
    sortable_date = (
        f"{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}"  # YYYY-MM-DD
    )
    dir_path += f"{sortable_date}/"
    if not os.path.isdir(dir_path):
        os.mkdir(dir_path)

    doa_seen = False
    doa_idx = -1
    with pdfplumber.open(f"{base_path}/src_hansard/new/DR-{hansard_date}.pdf") as pdf:
        extract_attn_start = False
        attn_text = ""
        for idx, page in enumerate(tqdm(pdf.pages)):
            extracted = page.extract_text()
            if not doa_seen:
                # extract attendance list before DOA section
                if "ahli-ahli yang hadir" in extracted.lower():
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
            if hansard_date == "09072019":
                # special case where snap tolerance doesn't work
                current_tables = page.filter(not_invisible_rect).extract_tables()
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

    with open(dir_path + "plaintext.txt", "w") as f:
        f.write(text)
    with open(dir_path + "bold.txt", "w") as f:
        f.write(spaced_bold)
    with open(dir_path + "italics.txt", "w") as f:
        f.write(spaced_italics)
    with open(dir_path + "tables.json", "w") as f:
        json.dump(tables, f, indent=4)
    with open(dir_path + "attendance.txt", "w") as f:
        f.write(attn_text)

    # for global logging
    if tables:
        with open("hansards_with_tables.txt", "a") as f:
            f.write(f"{sortable_date}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "hansard_date", help="hansard_date eg. 23052023", default="18092023", nargs="?"
    )
    # Parse arguments
    args = parser.parse_args()
    parse_hansard(args.hansard_date)
