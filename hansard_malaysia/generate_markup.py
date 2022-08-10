import argparse

import pdfplumber
import os
from tqdm import tqdm


def add_markup(chars):
    chars.append({'text': '', 'fontname': ''})
    prev_char = ''
    new_chars = []
    for char in chars:
        # there are no newlines in chars, they are represented by double spaces
        # this is especially important between bold sentences
        if char['text'] == ' ' and prev_char == ' ':
            # delete previous space
            new_chars.pop()
            char['text'] = '\n'
        new_chars.append(char)
        prev_char = char['text']
    chars = new_chars

    text = ""
    bold_streak = False
    italic_streak = False
    in_annotation = False
    # adding bold markup
    for char in chars:
        if char['text'] == '\n' and bold_streak:
            # newlines separates two bold segments
            # so markup must be separate as well
            assert not italic_streak
            text += "******"
            continue

        if "Bold" not in char["fontname"]:
            if bold_streak:
                # end of bold segment
                text += "***"
                bold_streak = False
            if "Italic" in char["fontname"] and not italic_streak and not in_annotation:
                text += "___"
                italic_streak = True
            elif "Italic" not in char["fontname"] and italic_streak:
                text += "___"
                italic_streak = False

        if char['text'] == '[' and not bold_streak:
            # to prevent bold inside annotations
            # eg. [Rang undang-undang dimaklumkan kepada Majlis sekarang]
            # but prevent debolding speaker context
            # eg. Tuan Chan Ming Kai [Alor Setar]:
            if italic_streak:
                italic_streak = False
                text += "___"
            in_annotation = True

        if "Bold" in char["fontname"] and not bold_streak \
                and not in_annotation and char['text'] != ' ':
            # start of bold segment
            # annotations are enforced to be non-bold and spaces cannot be start of a bold segment
            if italic_streak:
                italic_streak = False
                text += "___"
            text += "***"
            bold_streak = True

        if char['text'] == ']':
            in_annotation = False

        text += char['text']

    return text


def process_file(hansard_code, page_num=-1):
    dir_path = "preprocessed_hansard/" + hansard_code
    with pdfplumber.open('src_hansard/hansard_' + hansard_code + '.pdf') as pdf:
        # print("adding markup...")
        if not os.path.isdir(dir_path):
            os.mkdir(dir_path)
        if page_num != -1:
            # special invocation for single page parsing
            with open(dir_path + "/" + str(page_num) + ".txt", 'w') as f:
                output = add_markup(pdf.pages[page_num].chars)
                f.write(output)
        else:
            for idx, page in enumerate(tqdm(pdf.pages)):
                with open(dir_path + "/" + str(idx) + ".txt", 'w') as f:
                    output = add_markup(page.chars)
                    f.write(output)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("hansard_code", help="The session code eg. 14-04-01-16")
    args = parser.parse_args()
    process_file(args.hansard_code)