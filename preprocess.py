"""Generate the plaintext, binary  bold, binary italic files for a given Hansard
"""

import argparse

import pdfplumber
import os
from tqdm import tqdm


def get_formatting(chars):
    # returns bold and italics list of 0, 1 for non-whitespace for the whole Hansard
    bold = []
    italics = []
    for char in chars:
        if not char['text'].isspace():
            if 'bold' in char['fontname'].lower():
                bold.append(1)
            else:
                bold.append(0)
            if 'italic' in char['fontname'].lower():
                italics.append(1)
            else:
                italics.append(0)

    return [bold, italics]


def preprocess_file(hansard_date):
    year = hansard_date[-4:]
    bold = []
    italics = []
    text = ''
    with pdfplumber.open('src_hansard/' + year + '/DR-' + hansard_date + '.pdf') as pdf:
        for idx, page in enumerate(tqdm(pdf.pages)):
            formatting = get_formatting(page.chars)
            bold += formatting[0]
            italics += formatting[1]
            text += page.extract_text() + '\n'  # add newline to separate pages

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

    dir_path = f"preprocessed/{year}/"
    if not os.path.isdir(dir_path):
        os.mkdir(dir_path)
    sortable_date = f'{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}'  # YYYY-MM-DD
    dir_path += f"{sortable_date}/"
    if not os.path.isdir(dir_path):
        os.mkdir(dir_path)

    with open(dir_path + "plaintext.txt", 'w') as f:
        f.write(text)
    with open(dir_path + "bold.txt", 'w') as f:
        f.write(spaced_bold)
    with open(dir_path + "italics.txt", 'w') as f:
        f.write(spaced_italics)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("hansard_date", help="hansard_date eg. 23052023",
                        default="04102022", nargs="?")
    # Parse arguments
    args = parser.parse_args()
    preprocess_file(args.hansard_date)
