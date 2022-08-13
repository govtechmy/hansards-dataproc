import os
import pprint
import re
import warnings
import pdfplumber
import pandas as pd
import argparse
import analyse_speakers
from hashlib import sha256


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
    text = re.sub(r'■\d{4}\.?', '', text)
    text = re.sub(r'\d{1,2}\.\d{2} ?((tgh)|(ptg)|(pg)|(mlm))\.?', '', text)
    return text


def get_bare_name(name):
    name = analyse_speakers.remove_titles(name)
    extended_titles = analyse_speakers.titles + ['Tuan']
    for title in extended_titles:
        name = name.replace(title+' ', ' ')
    return re.sub('  +', ' ', name).strip()


def similarity_score(name_1, name_2):
    name_1 = get_bare_name(name_1)
    name_2 = get_bare_name(name_2)
    for joint in [' bin ', ' binti ']:
        if joint in name_1 and joint in name_2:
            name_1_first, name_1_last = name_1.split(joint)
            name_2_first, name_2_last = name_2.split(joint)
            result_1 = similarity_score(name_1_first, name_2_first)
            result_2 = similarity_score(name_1_last, name_2_last)
            if result_1 and result_2:
                return result_1 + result_2
            else:
                return 0
    name_1_list = name_1.split()
    name_2_list = name_2.split()
    matches = []
    for chunk in name_1_list:
        if chunk in name_2_list:
            name_2_list.pop(name_2_list.index(chunk))
            matches.append(chunk)
    if not len(matches):
        return 0
    indexes = []
    name_2_list = name_2.split()
    for chunk in matches:
        indexes.append(name_2_list.index(chunk))
        name_2_list.pop(name_2_list.index(chunk))
    if sorted(indexes) != indexes:
        return 0
    indexes = []
    for chunk in matches:
        indexes.append(name_1_list.index(chunk))
        name_1_list.pop(name_1_list.index(chunk))
    if sorted(indexes) != indexes:
        return 0

    return len(indexes)


def get_closest_mp(name, df_speakers):
    df_speakers = df_speakers.copy()
    df_speakers['score'] = df_speakers['name'].apply(lambda x: int(similarity_score(name, x)))
    return df_speakers.loc[df_speakers['score'] == df_speakers['score'].max(), ['name']].values[0][0]


def export_hansard(df, hansard_code, df_speakers):
    analysis_dir = f"analysis_hansard/{hansard_code}"
    output_dir = f"release/{hansard_code}"
    if not os.path.isdir(analysis_dir):
        os.mkdir(analysis_dir)
    if not os.path.isdir(output_dir):
        os.mkdir(output_dir)

    # use constituencies or roles
    df['speaker'] = df['speaker'].apply(lambda x: get_role(x, df_speakers))

    # save role-person information to separate parquet
    for speaker_name in role_of_speaker:
        # check if role is a constituency
        new_role = role_of_speaker[speaker_name].replace('–', '-')
        speaker_series = df_speakers.loc[df_speakers['seat_name'] == new_role, ['name']].values
        if speaker_series.size == 1:
            # constituency match
            possible_speaker_match = speaker_series[0][0]
            if not similarity_score(possible_speaker_match, speaker_name):
                # score is zero between names
                print(
                    f"WARN: Same constituency ({new_role}) but different names:\nIn text: {speaker_name}\nIn list: {possible_speaker_match}")
            else:
                # constituency and name match
                if similarity_score(possible_speaker_match, speaker_name) < len(get_bare_name(speaker_name).split()) / 2:
                    print(
                        f"WARN: Same constituency ({new_role}) but low similarity score:\nIn text: {speaker_name}\nIn list: {possible_speaker_match}")
                continue
        elif speaker_series.size == 0:
            # not a constituency, probably an add-on role, have to match with name
            speaker_series = df_speakers.loc[df_speakers['name'] == speaker_name, 'name'].values
            if speaker_series.size == 1:
                # found exact match
                current_role = df_speakers.loc[df_speakers['name'] == speaker_name, 'role'].values[0]
                if current_role and current_role != new_role:
                    print(f"WARN: Role collision for {speaker_name}\nOLD: {current_role}\nNew: {new_role}")
                df_speakers.loc[df_speakers['name'] == speaker_name, 'role'] = new_role
            else:
                # no exact name match, have to approximate
                possible_speaker_match = get_closest_mp(speaker_name, df_speakers)
                print(f'WARN: Matching speaker to MP list:\nIn text: {speaker_name} (as {new_role})\nIn list: {possible_speaker_match}')
                current_role = df_speakers.loc[df_speakers['name'] == possible_speaker_match, 'role'].values[0]
                if current_role and current_role != new_role:
                    print(f"WARN: Role collision for {speaker_name}\nOLD: {current_role}\nNew: {new_role}")
                df_speakers.loc[df_speakers['name'] == possible_speaker_match, 'role'] = new_role
        elif speaker_series.size > 1:
            print(f"WARN: Name collision for: {speaker_name}")
        else:
            print(f"WARN: Cannot find speaker in MP list: {speaker_name}")

    df_speakers.to_csv(f"{analysis_dir}/speakers.csv", index=False)
    df_speakers.to_parquet(f"{output_dir}/speakers.parquet", index=False)

    df.to_csv(f"{analysis_dir}/hansard.csv", index=False)
    df.to_parquet(f"{output_dir}/hansard.parquet", index=False)

    # export categories for logging and verification
    category_df = df[['category', 'subtopic']].copy()
    category_df = category_df.drop_duplicates()
    category_df.to_csv(f'{analysis_dir}/category.csv', index=False)


def stitch_segments(_segments, glue=" "):
    # stitch neighboring non-bold segments
    new_segments = [_segments[0]]
    for i in range(1, len(_segments)):
        if not _segments[i][1] and not new_segments[-1][1]:
            new_segments[-1][0] += glue + _segments[i][0]
        else:
            new_segments.append(_segments[i])
    return new_segments


def log_to_file(filename, string):
    with open(filename, 'w') as f:
        f.write(string)


def clean_segments(_segments):
    # remove ghost spaces
    # eg. the space between <> is non-bold, while the rest is bold: Tuan M. Kulasegaran [Ipoh< >Barat]
    new_segments = [_segments[0]]
    i = 1
    while i < len(_segments):
        if i < len(_segments) - 1 and _segments[i][0] == ' ' and _segments[i - 1][1] == _segments[i + 1][1]:
            new_segments[-1][0] += _segments[i + 1][0]
            i += 1
        else:
            new_segments.append(_segments[i])
        i += 1
    _segments = new_segments

    # remove segments that only have spaces
    _segments = [segment for segment in _segments if segment[0].strip(' ')]

    # remove segments that only have spaces or italic markup
    _segments = [segment for segment in _segments if segment[0].replace('___', '').strip(' ')]

    _segments = stitch_segments(_segments)

    # remove segments that only have newlines
    _segments = [segment for segment in _segments if segment[0].strip('\n')]
    _segments = stitch_segments(_segments, '\n')

    # remove redundant italic markup
    _segments = [[re.sub('___ +___', ' ', segment[0]), segment[1]] for segment in _segments]
    _segments = [segment for segment in _segments if segment[0].strip()]
    _segments = stitch_segments(_segments)

    _segments = [[segment[0].replace('______', ''), segment[1]] for segment in _segments]
    _segments = [segment for segment in _segments if segment[0]]
    _segments = stitch_segments(_segments, '')

    _segments = [[re.sub('___[\n ]+___', '\n', segment[0]), segment[1]] for segment in _segments]
    _segments = [segment for segment in _segments if segment[0].strip()]
    _segments = stitch_segments(_segments, '\n')

    # strip whitespaces
    _segments = [[segment[0].strip(), segment[1]] for segment in _segments]

    # convert double spaces to newlines
    _segments = [[segment[0].replace('  ', '\n'), segment[1]] for segment in _segments]
    return _segments


role_of_speaker = {}


def remove_tuan(name):
    if name.startswith("Tuan"):
        name = name[len("Tuan"):].strip()
    return name


def get_role(speaker, df_speakers):
    speaker = speaker.strip()
    # for in-text use
    # there are multiple forms
    # Timbalan Yang di-Pertua [Dato’ Mohd Rashid Hasnon]
    # Tuan Noor Amin bin Ahmad [Kangar]
    # Timbalan Menteri di Jabatan Perdana Menteri (Parlimen dan Undang- undang) [Datuk Wira Hajah Mas Ermieyati binti Samsudin]
    # Datuk Wira Hajah Mas Ermieyati binti Samsudin

    if '[' not in speaker:
        if speaker == "Tuan Yang di-Pertua":
            return "Yang di-Pertua"
        elif speaker in ['Beberapa Ahli', "Tuan Pengerusi",
                         "DEWAN", 'Timbalan Yang di-Pertua', 'Seorang Ahli']:
            return speaker
        else:
            raw_name = remove_tuan(analyse_speakers.remove_titles(speaker))
            if raw_name in role_of_speaker:
                # get role from previous introduction
                return role_of_speaker[raw_name]
            else:
                # Attempt to get role from MP list
                possible_row = df_speakers.loc[df_speakers['name'] == raw_name]
                if not possible_row.empty:
                    return possible_row.seat_name.item()
                else:
                    print(f"WARN: Unrecognised speaker: {raw_name}")
                    df_speakers.to_csv('error-log-speakers.csv')
                    log_to_file('dict_log.txt', str(role_of_speaker))
                    return raw_name
    segments = speaker.split('[')
    # remove ]
    assert len(segments) == 2
    segments[1] = segments[1][:-1]
    segments = [segment.strip() for segment in segments]
    if [x for x in ['Menteri', 'Yang di-Pertua', 'Pengerusi'] if x in segments[0]]:
        speaker_name = analyse_speakers.remove_titles(segments[1])
        speaker_role = segments[0]
    else:
        speaker_name = analyse_speakers.remove_titles(segments[0])
        speaker_role = segments[1]
    speaker_name = remove_tuan(analyse_speakers.remove_titles(speaker_name))
    role_of_speaker[speaker_name] = speaker_role.replace('Tuan','').strip()
    assert speaker_name
    assert speaker_role
    return speaker_role


def get_categories(hansard_code):
    _all_text = ""
    with pdfplumber.open('src_hansard/hansard_' + hansard_code + '.pdf') as pdf:
        # locate KANDUNGAN
        for idx, page in enumerate(pdf.pages):
            with open('preprocessed_hansard/' + hansard_code + '/' + str(idx) + '.txt', 'r') as f:
                _all_text = f.read()
            if "KANDUNGAN" in _all_text.replace(' ', ''):
                print(f'TOC at page {idx}')
                found = True
                break
    assert _all_text
    assert found
    _segments = parse_markup(_all_text)
    _segments = clean_segments(_segments)
    # skip first segment Diterbitkan Oleh:\nSEKSYEN PENYATA RASMI
    if "Diterbitkan Oleh:" not in _segments[0][0]:
        raise AssertionError(f"TOC page does not start with publisher but: {_segments[0][0]}")
    _segments.pop(0)
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
    used_categories = set()
    j = 0
    logs = ""
    subtopic = ''
    table = []
    current_category = ""
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
                raise AssertionError("New category not in TOC.\nFound: " + new_category + "\nAvailable categories: \n"
                                     + '\n'.join(categories)
                                     + "\nIf only slight typo, edit TOC and rerun")
            current_category = candidate_category
            new_category = new_category[len(candidate_category):]
            print("New category:", current_category)
            used_categories.add(current_category)
            if new_category:
                subtopic = new_category.strip().rstrip('-').rstrip('–').strip()
                print("New subtopic:", subtopic)
            else:
                subtopic = ''
            logs += "New category:" + current_category + '\n'
            continue
        if j + 1 < len(segments) and segments[j][1] and segments[j + 1][1]:
            # double bold
            if re.match(r'\d+\.', segments[j][0]) and "JAWAPAN-JAWAPAN" in current_category:
                subtopic = segments[j][0].split('.')[0]
                logs += "QUESTION NUMBER DETECTED: " + subtopic + '\n'
                j += 1
                continue
            subtopic = segments[j][0].strip().rstrip('-').rstrip('–').strip()
            print("double bold, new subtopic:", subtopic)
            logs += "double bold, new subtopic: " + subtopic + '\n'
            j += 1
            continue

        if j + 1 < len(segments) and segments[j][1] and not segments[j + 1][1]:
            # typical author-speech
            author = segments[j][0].replace(':', '')
            if re.match(r'\d', segments[j][0]) and segments[j + 1][
                0].strip() == '.' and "JAWAPAN-JAWAPAN" in current_category:
                subtopic = segments[j][0]
                logs += "QUESTION NUMBER DETECTED: " + subtopic + '\n'
                j += 2
                continue
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
            print(f"WARN: ignoring statement (bold: {segments[j][1]}): {segments[j][0]}")
            if table:
                print("previous row is", str(table[-1]))
                print(f'index {j} of length {len(segments)}')
            logs += "ignoring: " + segments[j][0] + '\n'
        j += 1

    # extracting DEWAN annotations
    new_table = []
    for row in table:
        text = row[-1]
        matches = re.findall(r'\n *\[[^\[]+] *(?=[\[\n]|$)', text)
        if matches:
            for match in matches:
                annotation = match
                if annotation.strip() in ["[Ketawa]", "[Tepuk]"]:
                    # action belongs to the speaker
                    continue
                speaker_text, text = text.split(annotation, 1)
                if speaker_text.strip():
                    if speaker_text.strip()[0] == '[' and speaker_text.strip()[-1] == ']' and speaker_text.count(
                            '[') == 1:
                        new_table.append(
                            row[:-2] + ["DEWAN", speaker_text.strip()]
                        )
                    else:
                        new_table.append(
                            row[:-1] + [speaker_text.strip()]
                        )
                new_table.append(
                    row[:-2] + ["DEWAN", annotation.strip()]
                )
            if text.strip():
                new_table.append(
                    row[:-1] + [text.strip()]
                )
        else:
            new_table.append(row)
    table = new_table

    for row in table:
        if '[Mesyuarat' in row[3] and row[2] != "DEWAN":
            print(f"WARN: Possible trailing annotation:\n" + str(row))

    # convert to pandas dataframe
    df = pd.DataFrame(data=table, columns=["category", "subtopic", "speaker", "content"], dtype="string")

    warned = False
    for category in categories:
        if category not in used_categories:
            warned = True
            print(f"WARN: Unused category: {category}")

    if not warned:
        print("All categories used")

    # save logs
    with open('analysis_hansard/' + hansard_code + '/' + hansard_code + '-logs.txt', 'w') as f:
        f.write(logs)
    return df


def process_file(hansard_code):
    # check if it is final version
    with open("preprocessed_hansard/" + hansard_code + '/0.txt', 'r') as f:
        if "Naskhah belum disemak" in f.read():
            print("Aborting due to unfinalised Hansard")
            return -1
    analysis_dir = "analysis_hansard/" + hansard_code
    if not os.path.isdir(analysis_dir):
        os.mkdir(analysis_dir)
    categories = get_categories(hansard_code)
    # checks for USUL-USUL before USUL
    categories.sort()
    categories.reverse()
    print("Extracted categories")
    print(categories)

    all_text = get_content(hansard_code)

    # remove timestamps for now
    all_text = remove_timestamps(all_text)

    with open(analysis_dir + "/removed_timestamps.txt", "w") as f:
        f.write(all_text)

    # separate chunks by boldness
    segments = parse_markup(all_text)

    # remove ghost whitespaces
    print(f"number of segments before cleaning: {len(segments)}")
    segments = clean_segments(segments)
    print(f"number of segments after cleaning: {len(segments)}")

    with open(analysis_dir + "/cleaned_segments.txt", "w") as f:
        f.write('\n~~~\n'.join([s[0] for s in segments]))

    dataframe = segments_to_dataframe(segments, categories, hansard_code)
    df_speakers = analyse_speakers.get_speakers_from_toc(hansard_code)
    export_hansard(dataframe, hansard_code, df_speakers)
    print(f'Done processing {hansard_code}')

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("hansard_code", help="The session code eg. 14-04-01-16")
    args = parser.parse_args()
    process_file(args.hansard_code)
