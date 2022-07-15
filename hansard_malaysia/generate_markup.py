import pdfplumber
import os
from tqdm import tqdm

hansard_code = "14-04-02-14"
dir_path = "output_hansard/" + hansard_code

def add_markup(chars):
    text = ""
    bold_streak = False
    italic_streak = False
    chars.append({'text': '', 'fontname': ''})
    prev_char = ''
    new_chars = []
    for char in chars:
        # double spaces act like break points between bold sentences
        if char['text'] == ' ' and prev_char == ' ':
            # can optimise below?
            new_chars = new_chars[:-1]
            char['text'] = '\n'
            # remove boldness
            char["fontname"] = char["fontname"].replace("Arial-BoldItalicMT", "Arial-ItalicMT")
            char["fontname"] = char["fontname"].replace("Arial-BoldMT", "ArialMT")
        new_chars.append(char)
        prev_char = char['text']
    chars = new_chars
    for char in chars:
        if "Italic" not in char["fontname"] and italic_streak:
            text += "___"
            italic_streak = False
        if "Bold" not in char["fontname"] and bold_streak:
            if text.strip()[-3:] == '***':
                # delete ghost segments
                text = text.strip()[:-3]
            else:
                text += "***"
            bold_streak = False

        if "Bold" in char["fontname"] and not bold_streak:
            text += "***"
            bold_streak = True
        if "Italic" in char["fontname"] and not italic_streak:
            text += "___"
            italic_streak = True
        text += char['text']

    return text

with pdfplumber.open('src_hansard/hansard_' + hansard_code + '.pdf') as pdf:
    print("adding markup...")
    for idx, page in tqdm(enumerate(pdf.pages)):
        if not os.path.isdir(dir_path):
            os.mkdir(dir_path)
        with open(dir_path + "/" + str(idx) + ".txt", 'w') as f:
            # add markup for bold and italics
            f.write(add_markup(page.chars))

# for special generation
# with pdfplumber.open('src_hansard/hansard_14-04-01-13.pdf') as pdf:
#     with open("output_hansard/14-04-01-02-plumber/" + str(10) + "-layout.txt", 'w') as f:
#         f.write(pdf.pages[10].extract_text(layout=True))

# for special generation
# with pdfplumber.open('src_hansard/hansard_' + hansard_code + '.pdf') as pdf:
#     special_id = 15
#     with open(dir_path + '/' + str(special_id) + ".txt", 'w') as f:
#         f.write(add_markup(pdf.pages[special_id].chars))
