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


def preprocess_file(hansard_date):
    year = hansard_date[-4:]
    bold = []
    italics = []
    tables = []
    text = ''

    dir_path = f"preprocessed/{year}/"
    if not os.path.isdir(dir_path):
        os.mkdir(dir_path)
    sortable_date = f'{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}'  # YYYY-MM-DD
    dir_path += f"{sortable_date}/"
    if not os.path.isdir(dir_path):
        os.mkdir(dir_path)

    doa_seen = False
    with pdfplumber.open('src_hansard/' + year + '/DR-' + hansard_date + '.pdf') as pdf:
        for idx, page in enumerate(tqdm(pdf.pages)):
            if 'DOA' in page.extract_text():
                doa_seen = True
            if not doa_seen:
                continue
            text += page.extract_text() + '\n'  # add newline to separate pages
            current_tables = page.extract_tables()  # if there are tables, add them to the list
            if current_tables:
                # add page number
                tables += [[idx, current_tables]]  # first wrapping is for appending. Want to preserve array structure
                # the structure is then
                # [ # master array
                #   [ page number,
                #       tables
                #   ]
                # ]
                # where the tables is a list (tables) of lists (table) of lists (row) where final items are the cells

            formatted_words = page.extract_words(extra_attrs=['fontname'])
            for word in formatted_words:
                is_bold = 0
                if 'bold' in word['fontname'].lower():
                    is_bold = 1
                is_italic = 0
                if 'italic' in word['fontname'].lower():
                    is_italic = 1
                bold += [is_bold] * len(word['text'])
                italics += [is_italic] * len(word['text'])

    assert len(bold) == len(italics), f'Length of bold and italics do not match: {len(bold)} vs {len(italics)}'
    raw_text = re.sub(r'\s+', '', text)
    assert len(bold) == len(raw_text), f'Length of bold and raw_text do not match: {len(bold)} vs {len(raw_text)}'
    # add whitespace to bold and italics using the raw text layout
    spaced_bold = ''
    spaced_italics = ''
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
    assert len(bold) == 0, f'Not all bold characters were processed: {len(bold)}'
    assert len(italics) == 0, f'Not all italic characters were processed: {len(italics)}'

    with open(dir_path + "plaintext.txt", 'w') as f:
        f.write(text)
    with open(dir_path + "bold.txt", 'w') as f:
        f.write(spaced_bold)
    with open(dir_path + "italics.txt", 'w') as f:
        f.write(spaced_italics)
    with open(dir_path + "tables.txt", 'w') as f:
        json.dump(tables, f, indent=4)

    # for global logging
    if tables:
        with open("hansards_with_tables.txt", 'a') as f:
            f.write(f"{sortable_date}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("hansard_date", help="hansard_date eg. 23052023",
                        default="28032023", nargs="?")
    # Parse arguments
    args = parser.parse_args()
    preprocess_file(args.hansard_date)
