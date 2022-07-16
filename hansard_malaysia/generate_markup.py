import pprint
import pdfplumber
import os
from tqdm import tqdm


def add_markup(chars, dir_path):
    chars.append({'text': '', 'fontname': ''})
    prev_char = ''
    new_chars = []
    for char in chars:
        # double spaces act like break points between bold sentences
        if char['text'] == ' ' and prev_char == ' ':
            # can optimise below?
            new_chars = new_chars[:-1]
            char['text'] = '\n'
        new_chars.append(char)
        prev_char = char['text']
    chars = new_chars

    sentences = []
    sentence = ["", -1]
    text = ""
    bold_streak = False
    italic_streak = False
    for char in chars:
        # if "Italic" not in char["fontname"] and italic_streak:
        #     text += "___"
        #     italic_streak = False
        if char['text'] == '\n' and bold_streak:
            # newlines separates two bold segments
            text += "******"
            continue

        if "Bold" not in char["fontname"] and bold_streak:
            sentences.append(sentence)
            sentence = ['', 1]
            text += "***"
            bold_streak = False

        if "Bold" in char["fontname"] and not bold_streak:
            sentences.append(sentence)
            sentence = ['', 1]
            text += "***"
            bold_streak = True

        sentence[0] += char['text']
        # if "Italic" in char["fontname"] and not italic_streak:
        #     text += "___"
        #     italic_streak = True
        text += char['text']
    if sentence[0]:
        sentences.append(sentence)

    with open(dir_path + '/' + 'analysis.txt', 'w') as f:
        pprint.pprint(sentences, f)
    return text


def process_file(hansard_code, page_num=-1):
    dir_path = "output_hansard/" + hansard_code
    with pdfplumber.open('src_hansard/hansard_' + hansard_code + '.pdf') as pdf:
        # print("adding markup...")
        if not os.path.isdir(dir_path):
            os.mkdir(dir_path)
        if page_num != -1:
            with open(dir_path + "/" + str(page_num) + ".txt", 'w') as f:
                f.write(add_markup(pdf.pages[page_num].chars, dir_path))
        else:
            for idx, page in enumerate(tqdm(pdf.pages)):
                with open(dir_path + "/" + str(idx) + ".txt", 'w') as f:
                    # add markup for bold and italics
                    f.write(add_markup(page.chars, dir_path))


if __name__ == "__main__":
    hansard_code = "14-04-02-14"
    process_file(hansard_code)

# for special generation
# with pdfplumber.open('src_hansard/hansard_' + hansard_code + '.pdf') as pdf:
#     with open(dir_path + "/" + str(10) + "-layout.txt", 'w') as f:
#         f.write(pdf.pages[10].extract_text(layout=True))


# with pdfplumber.open('src_hansard/hansard_' + hansard_code + '.pdf') as pdf:
#     with open(dir_path + "/" + str(10) + "-extract.txt", 'w') as f:
#         f.write(pdf.pages[10].extract_text())

# with pdfplumber.open('src_hansard/hansard_' + hansard_code + '.pdf') as pdf:
#     with open(dir_path + "/" + str(10) + "-plain.txt", 'w') as f:
#         f.write(''.join([x['text'] for x in pdf.pages[10].chars]))

# with pdfplumber.open('src_hansard/hansard_' + hansard_code + '.pdf') as pdf:
#     text = ''
#     for page in tqdm(pdf.pages[10:]):
#         text += ''.join([x['text'] for x in page.chars])
#     with open(dir_path + "/plain.txt", 'w') as f:
#         f.write(text)

# for special generation
# with pdfplumber.open('src_hansard/hansard_' + hansard_code + '.pdf') as pdf:
#     special_id = 15
#     with open(dir_path + '/' + str(special_id) + ".txt", 'w') as f:
#         f.write(add_markup(pdf.pages[special_id].chars))
