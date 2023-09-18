"""Generate the plaintext, binary  bold, binary italic files for a given Hansard
"""

import argparse
import re

import pdfplumber
import os
from tqdm import tqdm


def add_markup(chars):
    size_dict = {}
    font_dict = {}
    for char in chars:
        if char['size'] in size_dict:
            size_dict[char['size']] += char['text']
        else:
            size_dict[char['size']] = char['text']

        if char['fontname'] in font_dict:
            font_dict[char['fontname']] += char['text']
        else:
            font_dict[char['fontname']] = char['text']

    return ''.join([x['text'] for x in chars])


def process_file(hansard_date):
    print(hansard_date)
    year = hansard_date[-4:]
    size_dict = {}
    font_dict = {}
    with pdfplumber.open('src_hansard/' + year + '/DN-' + hansard_date + '.pdf') as pdf:
        sortable_date = f'{hansard_date[-4:]}-{hansard_date[2:3]}-{hansard_date[:2]}'  # YYYY-MM-DD
        dir_path = f"preprocessed/{sortable_date}/"
        if not os.path.isdir(dir_path):
            os.mkdir(dir_path)
        for idx, page in enumerate(tqdm(pdf.pages)):
            with open(dir_path + "/" + str(idx) + ".txt", 'w') as f:
                output = add_markup(page.chars)
                text_using_extraction = page.extract_text()
                comparison_text = text_using_extraction.replace('\n', '')
                comparison_text = re.sub(r'  +', ' ', comparison_text)
                verdict = output == comparison_text
                print(verdict)
            pass

        with open('size_dict.txt', 'w') as file:
            for key, value in size_dict.items():
                file.write(f'{key}: {value}\n')
        with open('font_dict.txt', 'w') as file:
            for key, value in font_dict.items():
                file.write(f'{key}: {value}\n')

    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("hansard_date", help="hansard_date eg. 23052023",
                        default="04102022", nargs="?")
    # Parse arguments
    args = parser.parse_args()
    process_file(args.hansard_date)
