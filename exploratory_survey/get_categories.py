"""Extract TOC and get all categories through bold and uppercase
"""

import argparse
import re

import pdfplumber
import os


def upper_lower_ratio(text):
    upper = sum(1 for c in text if c.isupper())
    lower = sum(1 for c in text if c.islower())
    if lower == 0:
        if upper == 0:
            # no alphabets
            return 0
        return 9999
    return upper / lower


def get_categories(hansard_date):
    print(hansard_date)
    year = hansard_date[-4:]
    bold = []
    italics = []
    text = ''
    kandungan_seen_idx = -1
    sortable_date = f'{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}'  # YYYY-MM-DD
    logged_long_toc = False
    kandungan_seen = False
    with pdfplumber.open('../src_hansard/' + year + '/DR-' + hansard_date + '.pdf') as pdf:
        for idx, page in enumerate(pdf.pages):
            # skip until TOC
            extracted_text = page.extract_text()
            if not kandungan_seen:
                if 'KANDUNGAN' in extracted_text.replace(' ', ''):
                    kandungan_seen = True
                    kandungan_seen_idx = idx
                else:
                    continue
            else:
                # TOC stops at the Senarai Ahli-Ahli, which title evolves over the years
                if re.search(r'(AHLI-AHLI +DEWAN +RAKYAT)|'
                             r'(SENARAI +KEHADIRAN +AHLI-AHLI +PARLIMEN)|'
                             r'(KEHADIRAN +AHLI-AHLI +PARLIMEN)|'
                             r'(SENARAI +AHLI-AHLI +)', extracted_text):
                    break
                if re.search(r'MALAYSIA\s+DEWAN +RAKYAT\s+PARLIMEN\s+', extracted_text):
                    # hard stop, missing attendance. e.g. 2020-07-27
                    break
            if kandungan_seen and kandungan_seen_idx < idx and \
                    re.search(r'[AEIOUaeiou]', extracted_text) and not logged_long_toc:
                # this is a Hansard where the TOC is more than two pages
                # e.g. 30032023
                logged_long_toc = True
                with open('long_toc_hansards.txt', 'a') as f:
                    f.write(hansard_date + '\n')
            text += extracted_text + '\n'  # add newline to separate pages
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

    dir_path = f"toc_analysis/{year}/"
    if not os.path.isdir(dir_path):
        os.mkdir(dir_path)
    dir_path += f"{sortable_date}/"
    if not os.path.isdir(dir_path):
        os.mkdir(dir_path)

    with open(dir_path + "plaintext.txt", 'w') as f:
        f.write(text)
    with open(dir_path + "bold.txt", 'w') as f:
        f.write(spaced_bold)
    with open(dir_path + "italics.txt", 'w') as f:
        f.write(spaced_italics)

    text = re.sub(r'\(Halaman +\d+ ?\)', '!!!', text)  # this is to allow upper_lower_ratio to work
    # keep in mind that text is now out of sync of bold and italics at the inline level
    lines = text.split('\n')
    bold_lines = spaced_bold.split('\n')
    # get the line index where the TOC starts
    toc_start_idx = 0
    while not re.search(r'K *A *N *D *U *N *G *A *N', lines[toc_start_idx]):
        toc_start_idx += 1

    lines = lines[toc_start_idx + 1:]
    bold_lines = bold_lines[toc_start_idx + 1:]
    line_idx = -1
    categories = []
    while line_idx + 1 < len(lines):
        line_idx += 1
        # check if current line is category
        if '1' in bold_lines[line_idx] and upper_lower_ratio(lines[line_idx]) > 1:
            category = lines[line_idx].strip()
            # check if the next line is a continuation of category
            add_idx = 1
            while line_idx + add_idx < len(lines) and \
                    upper_lower_ratio(lines[line_idx + add_idx]) > 1 and \
                    "!!!" not in lines[line_idx + add_idx - 1]:
                category += ' ' + lines[line_idx + add_idx].strip()
                add_idx += 1
            line_idx += add_idx - 1
            categories.append(category.replace("!!!", "").strip())

    if len(categories) == 0:
        with open("get_categories_log.txt", 'a') as f:
            f.write(f'Empty category found in {hansard_date}' + '\n')
    # global logging
    with open("categories.txt", 'a') as f:
        f.write('\n'.join(categories) + '\n')


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("hansard_date", help="hansard_date eg. 23052023",
                        default="30032023", nargs="?")
    # Parse arguments
    args = parser.parse_args()
    get_categories(args.hansard_date)
