import os
import pprint
import re
import pdfplumber
import numpy as np
import pandas as pd
import generate_markup

def parse_markup(text):
    segments = []
    segment = text[:2]
    bold = False
    for i in range(2, len(text)):
        segment += text[i]
        if text[i - 2:i + 1] == '***':
            segment = segment[:-3]
            if bold:
                package = [segment, 1]
            else:
                package = [segment, 0]
            segments.append(package)
            bold = not bold
            segment = ""
    return segments


def remove_timestamps(text):
    # removing irregular formatting of timestamps
    text = re.sub(r'■\*\*\*\d{4}', '***', text)
    text = re.sub(r'\*\*\*■\d{4}\*\*\*', '', text)
    text = re.sub(r'■\d{4}', '', text)
    text = re.sub(r'\d{1,2}\.\d{2} ((tgh)|(ptg))\.', '', text)
    return text


def export_hansard(table):
    # convert to numpy array
    table = np.array(table)

    # convert to pandas dataframe
    df = pd.DataFrame(data=table, columns=["category", "category_remark", "speaker", "content"])
    # print(df.head().to_string())
    # print(df.tail().to_string())

    if not os.path.isdir(analysis_dir):
        os.mkdir(analysis_dir)

    df.to_parquet(analysis_dir + '/' + hansard_code + '.parquet')

    with open(analysis_dir + '/' + hansard_code + '-output.txt', 'w') as f:
        f.write(df.to_string())

    with open(analysis_dir + '/' + hansard_code + '-logs.txt', 'w') as f:
        f.write(logs)


def clean_segments(_segments):
    # remove ghost spaces
    # eg. the space between <> is non-bold, while the rest is bold: Tuan M. Kulasegaran [Ipoh< >Barat]
    print("removing ghost spaces")
    print("number of segments:", len(_segments))
    new_segments = []
    i = 1
    while i < len(_segments) - 1:
        if _segments[i][0] == ' ' and _segments[i - 1][1] == _segments[i + 1][1]:
            new_segments[-1][0] += _segments[i + 1][0]
            i += 1
        else:
            new_segments.append(_segments[i])
        i += 1
    _segments = new_segments
    print("number of segments:", len(_segments))

    # remove ghost bold whitespaces (not just spaces)
    print("removing ghost whitespaces")
    _segments = [segment for segment in _segments if segment[0].strip()]
    print("number of segments:", len(_segments))

    print("Combining adjacent non-bold segments")
    new_segments = [_segments[0]]
    for i in range(1, len(_segments)):
        if not _segments[i][1] and not new_segments[-1][1]:
            # if ghost spaces separate non-bold paragraphs, stitch them back
            new_segments[-1][0] += ' ' + _segments[i][0]
        else:
            new_segments.append(_segments[i])
    _segments = new_segments
    print("number of segments:", len(_segments))

    # strip whitespaces
    _segments = [[segment[0].strip(), segment[1]] for segment in _segments]
    return _segments


def get_categories(hansard_code):
    with pdfplumber.open('src_hansard/hansard_' + hansard_code + '.pdf') as pdf:
        for idx, page in enumerate(pdf.pages):
            layout_text = page.extract_text().replace(' ', '')
            # get first page with texts
            if "KANDUNGAN" in layout_text:
                all_text = generate_markup.process_file(hansard_code, page_num=idx)
                break
    print(all_text)
    _segments = parse_markup(all_text)
    print(len(_segments))
    _segments = clean_segments(_segments)
    bolds = []
    for segment in _segments:
        if segment[1]:
            bolds.append(segment[0].replace(':',''))
    # remove the first bold (kandungan)
    return bolds[1:]


if __name__ == "__main__":
    pdf_code = "DR.16.11.2021"
    hansard_code = "14-04-02-14"
    analysis_dir = "analysis_hansard/" + hansard_code
    categories = get_categories(hansard_code)
    print(categories)
    # TODO: categories parse from "K A N D U N G A N"
    # categories = [
    #     # 14-04-01-17
    #     "USUL MENANGGUHKAN BACAAN KALI YANG KEDUA DAN KETIGA RANG UNDANG-UNDANG",
    #     "JAWAPAN-JAWAPAN MENTERI BAGI PERTANYAAN-PERTANYAAN",
    #     "JAWAPAN-JAWAPAN LISAN BAGI PERTANYAAN-PERTANYAAN",
    #     # 14-04-01-17
    #     "USUL",
    #     "RANG UNDANG-UNDANG DIBAWA KE DALAM MESYUARAT",
    #     # 14-04-01-17
    #     "USUL MENTERI DI JABATAN PERDANA MENTERI DI BAWAH P.M. 76:",
    #     # 14-04-01-16
    #     "USUL MENTERI DI BAWAH P.M. 86(5)",
    #     # 14-04-01-13
    #     "USUL MENANGGUHKAN MESYUARAT DI BAWAH P.M. 18(1)",
    #     "USUL-USUL",
    #     "RANG UNDANG-UNDANG",
    #     # 14-04-01-17
    #     "USUL-USUL MENTERI KEWANGAN:"
    # ]

    dir_path = "output_hansard/" + hansard_code

    with pdfplumber.open('src_hansard/hansard_' + hansard_code + '.pdf') as pdf:
        for idx, page in enumerate(pdf.pages):
            layout_text = page.extract_text()
            # get first page with texts
            if layout_text[:16] == pdf_code + '  1':
                first_page = idx
                break
        print('first page:', first_page)
        all_text = ""
        for idx in range(first_page, len(pdf.pages)):
            with open(dir_path + "/" + str(idx) + ".txt", 'r') as f:
                # remove the PDF code in the first line
                all_text += ''.join(f.readlines()[1:])

        # ignore special texts in the format [XX mempengerusikan Mesyuarat]
        # for example: [Timbalan Yang di-Pertua (Dato’ Mohd Rashid Hasnon) mempengerusikan Mesyuarat]
        print("number of text:", len(all_text))
        all_text = re.sub(r'\[[A-Za-z’()\- ]+ \*\*\*mempengerusikan Mesyuarat\*\*\*]', '', all_text)
        print("number of text:", len(all_text))

        # remove timestamps for now
        print("removing timestamps")
        all_text = remove_timestamps(all_text)
        print("number of text:", len(all_text))

        with open(analysis_dir + "/cleaned_text.txt", "w") as f:
            f.write(all_text)

        # separate chunks by boldness
        segments = parse_markup(all_text)
        with open(analysis_dir + "/segments.log", "w") as log_file:
            pprint.pprint(segments, log_file)
        print("number of segments:", len(segments))

        segments = clean_segments(segments)

        # print(segments)
        j = 0
        category_id = -1
        logs = ""
        question_num = -1
        table = []

        print(segments[:5])
        while j < len(segments):
            if j + 1 < len(segments) and segments[j][1] and segments[j + 1][1]:
                if category_id + 1 < len(categories) and categories[category_id + 1] in segments[j][0]:
                    print("NEW CATEGORY DETECTED:" + categories[category_id + 1])
                    logs += "NEW CATEGORY DETECTED: " + categories[category_id + 1] + '\n'
                    question_num = -1
                    category_id += 1
                    j += 1
                    continue
                elif re.match(r'\d+\.', segments[j][0]):
                    question_num = segments[j][0].split('.')[0]
                    print("QUESTION NUMBER DETECTED:", question_num)
                    j += 1
                    continue
                print("double bold, ignoring:", segments[j][0])
                logs += "double bold, ignoring: " + segments[j][0] + '\n'
                j += 1
                continue
            question_num_search_result = re.search('\d+\.', segments[j][0])

            if j + 1 < len(segments) and segments[j][1] and not segments[j + 1][1]:
                author = segments[j][0].replace(':', '')
                if re.match(r'\d+\.', author):
                    question_num = author.split('.')[0]
                    author = '.'.join(author.split('.')[1:])
                    print("QUESTION NUMBER DETECTED:", question_num)
                speech = segments[j + 1][0].strip()
                logs += "author: " + author + '\n'
                logs += "speech: " + speech + '\n'
                row = [
                    categories[category_id],
                    question_num,
                    author,
                    speech
                ]
                table.append(row)
                j += 1
            else:
                print("ignoring with status ", segments[j][1], segments[j][0])
                logs += "ignoring: " + segments[j][0] + '\n'
            j += 1

    export_hansard(table)
