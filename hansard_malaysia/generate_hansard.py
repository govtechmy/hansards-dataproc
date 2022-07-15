import re
import pdfplumber

pdf_code = "DR.16.11.2021"
fonts = set()
hansard_code = "14-04-02-14"


def parse_markup(text):
    sentences = []
    sentence = text[:2]
    bold = False
    for i in range(2, len(text)):
        sentence += text[i]
        if text[i - 2:i + 1] == '***':
            sentence = sentence[:-3]
            if bold:
                package = [sentence, 1]
            else:
                package = [sentence, 0]
            sentences.append(package)
            bold = not bold
            sentence = ""
    return sentences


def remove_timestamps(text):
    # removing irregular formatting of timestamps
    text = re.sub(r'■\*\*\*\d{4}', '***', text)
    text = re.sub(r'\*\*\*■\d{4}\*\*\*', '', text)
    text = re.sub(r'■\d{4}', '', text)
    return text


# TODO: categories parse from "K A N D U N G A N"
categories = [
    "JAWAPAN-JAWAPAN MENTERI BAGI PERTANYAAN-PERTANYAAN",
    "JAWAPAN-JAWAPAN LISAN BAGI PERTANYAAN-PERTANYAAN",
    "RANG UNDANG-UNDANG DIBAWA KE DALAM MESYUARAT",
    "USUL-USUL",
    "RANG UNDANG-UNDANG"
]

dir_path = "output_hansard/" + hansard_code

with pdfplumber.open('src_hansard/hansard_' + hansard_code + '.pdf') as pdf:
    for idx, page in enumerate(pdf.pages):
        layout_text = page.extract_text()
        # get first page with texts
        if layout_text[:16] == pdf_code + '  1':
            first_page = idx
            break
    nxt = 0
    all_text = ""
    for idx in range(first_page, len(pdf.pages)):
        with open(dir_path + "/" + str(idx) + ".txt", 'r') as f:
            # remove the PDF code in the first line
            all_text += ''.join(f.readlines()[1:])

    # ignore the preface and prayers
    all_text = all_text.split("mempengerusikan Mesyuarat***]___")[1]
    all_text = remove_timestamps(all_text)
    # separate chunks by boldness
    sentences = parse_markup(all_text)
    # remove ghost bold spaces
    sentences = [sentence for sentence in sentences if not sentence[1] or sentence[0].strip()]
    new_sentences = [sentences[0]]
    for i in range(1, len(sentences)):
        if not sentences[i][1] and not new_sentences[-1][1]:
            new_sentences[-1][0] += ' ' + sentences[i][0]
        else:
            new_sentences.append(sentences[i])
    sentences = new_sentences

    # print(sentences)
    parsed_categories = []
    category = []
    j = 0
    category_id = -1
    logs = ""
    while j < len(sentences):
        if sentences[j][0].strip() == '':
            j += 1
            continue
        if sentences[j][1] and re.match(r'\d+\.', sentences[j][0].strip()):
            # detect question number
            print("Question number detected")
            logs += "Question number detected\n"
            print(sentences[j][0])
            logs += sentences[j][0] + '\n'
            j += 1
            continue
        if category_id + 1 < len(categories) and categories[category_id + 1] in sentences[j][0]:
            print("NEW CATEGORY DETECTED:", categories[category_id + 1])
            logs += "NEW CATEGORY DETECTED: " + categories[category_id + 1] + '\n'
            parsed_categories.append([categories[category_id], category])
            category = []
            category_id += 1
            j += 1
            continue
        if sentences[j][1] and not sentences[j + 1][1]:
            author = sentences[j][0]
            speech = sentences[j + 1][0]
            print("author:", author)
            logs += "author: " + author + '\n'
            print("speech:", speech)
            logs += "speech: " + speech + '\n'
            category.append([author, speech])
            j += 1
        else:
            print("ignoring", sentences[j][0])
            logs += "ignoring: " + sentences[j][0] + '\n'
        j += 1

# with open("output_hansard/14-04-01-02-plumber/2-layout.txt") as f:
#     text = f.read()
#     assert "K A N D U N G A N" in text

with open('output.txt', 'w') as f:
    f.write(str(categories))

with open('logs.txt', 'w') as f:
    f.write(logs)
