import os

from PyPDF2 import PdfReader

hansard_code = "14-04-01-13"
reader = PdfReader("src_hansard/hansard_" + hansard_code + ".pdf")
output = ""

path = "output_hansard/" + hansard_code
if not os.path.isdir(path):
    os.makedirs(path)

for idx, page in enumerate(reader.pages):
    text = page.extract_text()
    # remove excessive whitespaces within text in original extracted document
    text = " ".join(text.split())
    with open("output_hansard/" + hansard_code + "/" + str(idx) + ".txt", 'w') as f:
        f.write(text)
