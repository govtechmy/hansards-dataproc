import pandas as pd
import pdfplumber
from tqdm import tqdm
import generate_markup
import generate_tabular

df = pd.read_csv('sessions.csv', parse_dates=['date'])
df.date = df.date.dt.date
sessions = df.session.tolist()
session_date = dict(zip(df.session, df.date))

bolds = {}
for session in tqdm(sessions[:30]):
    # print(session)
    # some pages kandungan at second or third page
    with pdfplumber.open('src_hansard/hansard_' + session + '.pdf') as pdf:
        for idx, page in enumerate(pdf.pages):
            layout_text = page.extract_text().replace(' ', '')
            # get first page with texts
            if "KANDUNGAN" in layout_text:
                target_page = idx
                break
    generate_markup.process_file(session, target_page)
    with open("output_hansard/" + session + "/" + str(target_page) + '.txt', 'r') as f:
        all_text = f.read()
    segments = generate_tabular.parse_markup(all_text)
    for segment in segments:
        if segment[1]:
            juice = segment[0].strip()
            bolds[juice] = bolds.get(juice, 0) + 1


bolds = dict(sorted(bolds.items(), key=lambda item: item[1]))
output = ""
for bold in bolds:
    output += bold + ": " + str(bolds[bold]) + '\n'
with open('kandungan-analysis.txt', 'w') as f:
    f.write(output)
