import os
import pprint
import re
import pdfplumber
import numpy as np
import pandas as pd
import argparse


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
    if segment:
        segments.append([segment, bold])
    return segments


def remove_timestamps(text):
    # removing irregular formatting of timestamps
    text = re.sub(r'■\*\*\*\d{4}', '***', text)
    text = re.sub(r'\*\*\*■\d{4}\*\*\*', '', text)
    text = re.sub(r'■\d{4}', '', text)
    text = re.sub(r'\d{1,2}\.\d{2} ((tgh)|(ptg)|(pg))\.', '', text)
    text = re.sub(r'\d{1,2}\.\d{2} ((tgh)|(ptg)|(pg))', '', text)
    return text


def export_hansard(df, hansard_code):
    analysis_dir = "analysis_hansard/" + hansard_code
    if not os.path.isdir(analysis_dir):
        os.mkdir(analysis_dir)

    with open(analysis_dir + '/' + hansard_code + '-plain.csv', 'w') as f:
        f.write(df.to_csv())
    # print(df.head().to_string())
    # print(df.tail().to_string())
    # print(df.category)
    df.category = pd.Categorical(df.category)
    category_df = df[['category']].copy()
    category_df['code'] = df.category.cat.codes
    category_df = category_df.drop_duplicates()
    category_df.to_parquet(analysis_dir + '/' + hansard_code + '-category.parquet')
    with open(analysis_dir + '/' + hansard_code + '-category.csv', 'w') as f:
        f.write(category_df.to_csv(index=False))

    df.subtopic = pd.Categorical(df.subtopic)
    subtopic_df = df[['subtopic']].copy()
    subtopic_df['code'] = df.subtopic.cat.codes
    subtopic_df = subtopic_df.drop_duplicates()

    subtopic_df.to_parquet(analysis_dir + '/' + hansard_code + '-subtopic.parquet')
    with open(analysis_dir + '/' + hansard_code + '-subtopic.csv', 'w') as f:
        f.write(subtopic_df.to_csv(index=False))

    df['category'] = df.category.cat.codes

    df.to_parquet(analysis_dir + '/' + hansard_code + '.parquet')
    with open(analysis_dir + '/' + hansard_code + '-encoded.csv', 'w') as f:
        f.write(df.to_csv())


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

    # separate Dewan annotations
    # new_segments = []
    # for _segment in _segments:
    #     if not _segment[1]:
    #         lst = re.compile('\n *\[').split(_segment[0])
    #         # lst = _segment[0].split('\n[')
    #         if lst[0]:
    #             new_segments.append([lst[0], 0])
    #         for i in lst[1:]:
    #             new_segments.append(['[' + i, 0])
    #     else:
    #         new_segments.append(_segment)
    # _segments = new_segments

    # strip whitespaces
    _segments = [[segment[0].strip(), segment[1]] for segment in _segments]
    return _segments


def get_categories(hansard_code):
    _all_text = ""
    with pdfplumber.open('src_hansard/hansard_' + hansard_code + '.pdf') as pdf:
        # locate KANDUNGAN
        for idx, page in enumerate(pdf.pages):
            with open('preprocessed_hansard/' + hansard_code + '/' + str(idx) + '.txt', 'r') as f:
                _all_text = f.read()
            if "KANDUNGAN" in _all_text.replace(' ', ''):
                found = True
                break
    assert _all_text
    assert found
    _segments = parse_markup(_all_text)
    _segments = clean_segments(_segments)
    # remove the first segment (kandungan)
    assert _segments[0][0].replace(' ', '') == "KANDUNGAN"
    _segments = _segments[1:]

    # for table of contents, it is better to join consecutive bold segments
    # since separate categories must be separated by a non-bold segment (Halaman X)
    new_segments = []
    for segment in _segments:
        if segment[1] and new_segments and new_segments[-1][1]:
            new_segments[-1][0] += " " + segment[0]
        else:
            new_segments.append(segment)
    _segments = new_segments

    bolds = []
    for segment in _segments:
        if segment[1]:
            bolds.append(segment[0].replace(':', ''))
    # sometimes bullet points are single bold segments, remove them if no alphanumeric content is present
    categories = [bold for bold in bolds if re.search(r'\w+', bold)]

    if "USUL-USUL" in categories:
        categories[categories.index("USUL-USUL")] = "USUL"
    return categories


def get_date_of_session(session):
    """
    :param session: the code of the session eg. 14-04-01-17
    :return: session date in the format dd.mm.yyyy
    """
    df = pd.read_csv('sessions.csv', parse_dates=['date'])
    df.date = df.date.dt.date
    session_date = dict(zip(df.session, df.date))
    session_date = session_date[session].strftime('%d.%m.%Y')
    return session_date


def get_content(hansard_code):
    pdf_code = "DR." + get_date_of_session(hansard_code)
    with pdfplumber.open('src_hansard/hansard_' + hansard_code + '.pdf') as pdf:
        for idx, page in enumerate(pdf.pages):
            with open('preprocessed_hansard/' + hansard_code + '/' + str(idx) + '.txt', 'r') as f:
                text = f.readlines()
            # get first page with texts
            if text and text[0].strip().endswith(pdf_code[-8:] + ' 1'):
                first_page = idx
                break
        print('first page:', first_page)
        all_text = ""
        for idx in range(first_page, len(pdf.pages)):
            with open('preprocessed_hansard/' + hansard_code + '/' + str(idx) + ".txt", 'r') as f:
                # remove the PDF code in the first line
                all_text += ''.join(f.readlines()[1:])
    return all_text


def segments_to_dataframe(segments, categories, hansard_code):
    j = 0
    logs = ""
    subtopic = -1
    table = []
    current_category = "NO CATEGORY DETECTED"
    while "DOA" not in segments[j][0]:
        j += 1
    j += 1
    while j < len(segments):
        # ignore known, special bold segments
        if '[' == segments[j][0][0] and ']' == segments[j][0][-1]:
            # DEWAN annotations
            print("annotation:", segments[j][0])
            author = "DEWAN"
            speech = segments[j][0].strip()
            logs += "author: " + author + '\n'
            logs += "speech: " + speech + '\n'
            row = [
                current_category,
                subtopic,
                author,
                speech
            ]
            table.append(row)
            j += 1
            continue
        if not segments[j][1]:
            # not bold, text without author
            author = "DEWAN"
            speech = segments[j][0].strip()
            logs += "author: " + author + '\n'
            logs += "speech: " + speech + '\n'
            print("text without author:", speech)
            row = [
                current_category,
                subtopic,
                author,
                speech
            ]
            table.append(row)
            j += 1
            continue

        new_category = ""
        # initiate category parsing if is bold and all uppercase
        if segments[j][1] and segments[j][0].isupper():
            # after initiation, conditions are less strict: text can be lowercase (eg. Bacaan kali...)
            # additionally, separate title from speakers (usually with [ ]) and numbering at start
            while segments[j][1] and (
                    segments[j][0].isupper() or (not re.search(r'\[[A-Za-z’\'()\-\. ]+(]:?)$', segments[j][0].strip())
                                                 and not "Tuan Yang di-Pertua:" == segments[j][0].strip()
                                                 and not re.search(r'\A\d+\.', segments[j][0].strip()))):
                # while bold
                if new_category:
                    new_category += ' '
                new_category += segments[j][0]
                j += 1
        if new_category:
            candidate_category = ""
            for category in categories:
                if new_category.startswith(category):
                    candidate_category = category
                    break
            if not candidate_category:
                raise AssertionError("New category not in TOC.\nFound:" + new_category + "\nAvailable categories: \n"
                                     + '\n'.join(categories)
                                     + "\nIf only slight typo, edit TOC and rerun")
            current_category = candidate_category
            new_category = new_category[len(candidate_category):]
            if new_category:
                subtopic = new_category
            else:
                subtopic = -1
            print("New category:", current_category)
            print("subtopic:", subtopic)
            logs += "New category:" + current_category + '\n'
            continue
        if j + 1 < len(segments) and segments[j][1] and segments[j + 1][1]:
            # double bold
            if re.match(r'\d+\.', segments[j][0]) and "JAWAPAN-JAWAPAN" in current_category:
                subtopic = segments[j][0].split('.')[0]
                logs += "QUESTION NUMBER DETECTED: " + subtopic + '\n'
                j += 1
                continue
            subtopic = segments[j][0].strip()
            print("double bold, new subtopic:", subtopic)
            logs += "double bold, new subtopic: " + subtopic + '\n'
            j += 1
            continue

        if j + 1 < len(segments) and segments[j][1] and not segments[j + 1][1]:
            # typical author-speech
            author = segments[j][0].replace(':', '')
            if re.match(r'\d+\.', author):
                subtopic = author.split('.')[0]
                author = '.'.join(author.split('.')[1:])
                logs += "QUESTION NUMBER DETECTED: " + subtopic + '\n'
            author = author.strip()
            speech = segments[j + 1][0].strip()
            logs += "author: " + author + '\n'
            logs += "speech: " + speech + '\n'
            row = [
                current_category,
                subtopic,
                author,
                speech
            ]
            table.append(row)
            j += 1
        else:
            print("ignoring with boldness ", segments[j][1], segments[j][0])
            logs += "ignoring: " + segments[j][0] + '\n'
        j += 1

    # convert to numpy array
    table = np.array(table)

    # convert to pandas dataframe
    df = pd.DataFrame(data=table, columns=["category", "subtopic", "speaker", "content"])

    # save logs
    with open('analysis_hansard/' + hansard_code + '/' + hansard_code + '-logs.txt', 'w') as f:
        f.write(logs)
    return df


def process_file(hansard_code):
    # check if it is final version
    with open("preprocessed_hansard/" + hansard_code + '/0.txt', 'r') as f:
        if "Naskhah belum disemak" in f.read():
            return -1
    analysis_dir = "analysis_hansard/" + hansard_code
    if not os.path.isdir(analysis_dir):
        os.mkdir(analysis_dir)
    categories = get_categories(hansard_code)
    print("Extracted categories")
    print(categories)

    markup_dir = "preprocessed_hansard/" + hansard_code

    all_text = get_content(hansard_code)

    # ignore special texts in the format [XX mempengerusikan Mesyuarat]
    # for example: [Timbalan Yang di-Pertua (Dato’ Mohd Rashid Hasnon) mempengerusikan Mesyuarat]
    # as they cut inside dialogue mid-speech
    all_text = re.sub(r'\[[A-Za-z’\'()\-\. ]+ mempengerusikan Mesyuarat]', '', all_text)

    # remove timestamps for now
    all_text = remove_timestamps(all_text)

    with open(analysis_dir + "/cleaned_text.txt", "w") as f:
        f.write(all_text)

    # separate chunks by boldness
    segments = parse_markup(all_text)

    # remove ghost whitespaces
    segments = clean_segments(segments)

    dataframe = segments_to_dataframe(segments, categories, hansard_code)

    export_hansard(dataframe, hansard_code)

    return 0

    # authors = list(authors)
    # authors.sort(key=lambda item: (-len(item), item))
    # print("Number of speakers:", len(authors))
    # print("Check if the speakers below are indeed, speakers:")
    # print('\n'.join(authors[:5]))
    # print('\n'.join(authors[-5:]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("hansard_code", help="The session code eg. 14-04-01-16")
    args = parser.parse_args()
    process_file(args.hansard_code)
