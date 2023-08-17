import os
from PyPDF2 import PdfReader
from tqdm import tqdm

# Results
"""
"JAWAPAN-JAWAPAN MENTERI BAGI PERTANYAAN-PERTANYAAN",
"JAWAPAN-JAWAPAN LISAN BAGI PERTANYAAN-PERTANYAAN",
"RANG UNDANG-UNDANG DIBAWA KE DALAM MESYUARAT",
"USUL-USUL",
"RANG UNDANG-UNDANG"
"""

phrases = {}
for filename in tqdm(os.listdir("src_hansard")):
    f = os.path.join("src_hansard", filename)
    assert os.path.isfile(f)
    reader = PdfReader(f)
    # text = ""
    # for page in reader.pages:
    #     text += page.extract_text()
    text = reader.pages[0].extract_text()
    # print(text)
    # remove excessive whitespaces within text
    # and scan for uppercase phrases
    phrase = ""
    for word in text.split():
        if word.isupper() or word == '-':
            phrase += word + ' '
        elif phrase != '':
            phrases[phrase[:-1]] = phrases.get(phrase[:-1], 0) + 1
            phrase = ''
    if phrase != '':
        phrases[phrase[:-1]] = phrases.get(phrase[:-1], 0) + 1

phrases = dict(sorted(phrases.items(), key=lambda item: item[1]))
output = ""
for phrase in phrases:
    output += phrase + ": " + str(phrases[phrase]) + '\n'

with open("uppercase_phrases.txt", 'w') as f:
    f.write(output)
