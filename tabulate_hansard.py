"""Generate the csv file of speeches for a given Hansard.
"""
import argparse
import os
import re
from thefuzz import process
import json
import csv


def is_timestamp(text):
    text = text.strip()
    return re.search(r'[■◼▪] ?\d{4}\.?', text) or \
           re.search(r'^ *\d{1,2}[.:] ?\d ?\d ?((pg)|(PG)|(pagi)|(tgh)|(Tgh)|'
                     r'(ptg)|(Ptg)|(petang)|(mlm)|(malam)|(pm))\.?',
                     text) or \
           re.search(r'^\d{4}$', text)
    # the first two major types are
    # 1.  ■ 1030 which is in regular 10 minute intervals
    # 2.  10.03 tgh. which has irregular appearances
    # Tgh is for 18102018
    # PG is for 16072018
    # space between last digits is for 05112019
    # the 4 digits is for 30032023 and 12062023


def has_timestamp_in_annotation(text):
    return " pada pukul " in text


def get_timestamp_from_annotation(text):
    assert " pada pukul " in text
    # remove trailing ]
    return text.split(" pada pukul ")[1][:-1]


def standardise_timestamp(timestamp):
    numbers = ''.join(re.findall(r'\d+', timestamp))
    assert len(numbers) != 0
    if len(numbers) < 3:
        # 10 pagi
        numbers += '00'
    if re.search(r'^[■◼▪] ?\d{4}\.?', timestamp):
        # if there is a preceding bullet then it is usually in 24h format
        return numbers
    elif re.search(r'(pg)|(PG)|(pagi)', timestamp):
        if len(numbers) == 3:
            return '0' + numbers
        else:
            assert len(numbers) == 4, f'Expected 4 digits but got {numbers} from {timestamp}'
            return numbers
    else:
        # malam, pm, tgh etc
        # apart from 12pm, all others need to add 12
        if len(numbers) == 4 and numbers[:2] == '12':
            return numbers
        hour = int(numbers[:-2]) + 12
        if hour >= 24:
            # they reported it in 24h
            hour -= 12
        return str(hour) + numbers[-2:]


def prop_of_1_among_binary(text):
    assert re.fullmatch(r'[01\s]*', text), f'Expected binary string but got "{text}"'
    return text.count('1') / (text.count('0') + text.count('1'))


def upper_lower_ratio(text):
    upper = sum(1 for c in text if c.isupper())
    lower = sum(1 for c in text if c.islower())
    if lower == 0:
        if upper == 0:
            # no alphabets
            return 0
        return 9999
    return upper / lower


def category_probability(text, categories):
    direct_match = text in categories
    if direct_match:
        return 1
    if upper_lower_ratio(text) < 1:
        # probably not a category
        return 0
    candidate_category, match_score = process.extractOne(text, categories)
    return match_score / 100


def get_author_and_speech(text, warn=''):
    author = ''
    speech = ''
    subtopic = ''
    if re.search(r'^(Tuan )?Yang di-Pertua[\[\]A-Za-z `.’\'@/(\-),]*:', text):
        # Speaker of the House
        author, speech = text.split(':', maxsplit=1)
    elif re.search(r'^Timbalan(an)? (Tuan )?Yang [dD]i- ?Pertua[\[\]A-Za-z `.’\'@/(\-),]*:', text):
        # Deputy Speaker of the House
        author, speech = text.split(':', maxsplit=1)
    elif re.search(r'^Setiausaha[\[\]A-Za-z `.’\'@/(\-),]*:', text):
        # Secretary of the House
        author, speech = text.split(':', maxsplit=1)
    elif re.search(
            r'^(Yang Berhormat )?(Timbalan )?[Mm]enteri [A-Za-z,()\-& ]+(\[Ekonomi] )?\[[A-Za-z `.’\'@/(\-)\[\]]+] ?:',
            text):
        # Minister or Deputy Minister
        # allows () at the name part as they can have constituencies too
        # , is for Menteri Pembangunan Wanita, Keluarga dan Masyarakat
        # () is for Menteri di Jabatan Perdana Menteri (Parlimen dan Undang-Undang)
        # - is for Timbalan Menteri di Jabatan Perdana Menteri (Undang-undang dan
        # Reformasi Institusi) [Tuan Ramkarpal Singh a/l Karpal Singh]: Tuan Yang di-
        # [] is for Menteri Sumber Manusia [Tuan M. Kulasegaran [Ipoh Barat]]: Cukup Tuan Yang
        # Timbalan Menteri Pendidikan [Puan Teo Nie Ching [Kulai]]: Tuan Yang di-Pertua,
        author, speech = text.split(':', maxsplit=1)
    elif re.search(r'^((Timbalan )|(Yang Amat Berhormat ))?Perdana [A-Za-z, ]+\[[A-Za-z `.’\'@/(\-)]+]:', text):
        # Prime Minister or Deputy Primer Minister
        # allows () as they can have constituencies too
        author, speech = text.split(']:', maxsplit=1)
        author += ']'
    elif re.search(r'^(Timbalan )?(Tuan )?Pengerusi (Timbalan Yang di-Pertua )?\[[A-Za-z `.’\'@/(\-)]*]:', text):
        # Chairman of Jawatankuasa
        # Tuan Pengerusi Timbalan Yang di-Pertua [Tuan Nga Kor Ming]: Tidak apa, tidak
        # allows () as they can have constituencies too
        author, speech = text.split(':', maxsplit=1)
    elif re.search(r'^\d{1,2}\.? [A-Za-z `.’\'@\/\-()]+\[[A-Za-z \-]+]:? *[Mm](em)?inta', text):
        # JAWAPAN-JAWAPAN LISAN BAGI PERTANYAAN-PERTANYAAN
        # 1. Tuan Tan Kok Wai [Cheras] minta Menteri Pembangunan Usahawan menyatakan,
        author, speech = text.split('inta', maxsplit=1)
        author = author[:-1]
        if author.endswith(':'):
            author = author[:-1]
        speech = 'minta ' + speech
        subtopic, author = author.split(' ', maxsplit=1)
    elif re.search(
            r'^((Tuan)|(Datuk)|(Dato)|(Tan Sri)|(Puan)|(Dr\.)|(YM)|(Ustaz)|(Tun)|(Kapten)|(Haji)|(Ir\.)|(Datu)|(Cik)|'
            r'(Laksamana)|(Mejar)|(Komander)|(Seri Paduka)|(Tengku)|(Hajah)|(Raja)|(Brig)|(Datin)|(Prof\.) )'
            r'[A-Za-z `.’\'@/\-()]+:',
            text):
        # continuation of Menteri or Timbalan Menteri, example
        # Timbalan Menteri di Jabatan Perdana Menteri [Datuk Wira Dr. Md Farid bin Md
        # Rafik]: Bismillahir Rahmanir Rahim.
        #  Datuk Wira Dr. Md Farid bin Md Rafik:  Bismillahir Rahmanir Rahim.
        # YM Tengku Dato’ Sri Zafrul Tengku Abdul Aziz: Okey, saya jawab twin deficit
        # Datuk Dr. Haji Zulkifli Mohamad Al-Bakri: ...Saya hendak minta maaf banyak-
        author, speech = text.split(':', maxsplit=1)
    elif re.search(
            r'^(Yang Berhormat )?'
            r'((Tuan)|(Datuk)|(Dato)|(Tan Sri)|(Puan)|(Dr\.)|(YM)|(Ustaz)|(Tun)|(Kapten)|(Haji)|(Ir\.)|(Datu)|(Cik)|'
            r'(Laksamana)|(Mejar)|(Komander)|(Seri Paduka)|(Tengku)|(Hajah)|(Raja)|(Brig)|(Datin)|(Prof\.) )'
            r'[A-Za-z `.’\'@/(),\-]+\[[A-Za-z \-–]+][ -]?:', text):
        # possible MP
        author, speech = text.split(':', maxsplit=1)
    elif re.search(
            r'^(Seorang Ahli ?:)|(Seorang ahli:)|(Seoarang ahli:)|(Seseorang Ahli:)|(seorang Ahli:)|'
            r'(Seorang Ahli Yang Berhormat:)|(Seorang Ahli Berucap)|(\[Seorang Ahli]:)|(Sorang Ahli:)|(Seorang Ali:)|'
            r'(Beberapa Ahli:)|(Beberapa orang Ahli:)|(Beberapa ahli:)|'
            r'(Beberapa Ahli Pembangkang:)|(Ahli-ahli:)|(Beberapa Orang Ahli:)|(Beberapa Ali:)', text):
        # Beberapa orang Ahli is for 09082018
        author, speech = text.split(':', maxsplit=1)
    elif text.startswith('Setiausaha:'):
        # Speaker of the House
        speech = text.split(':', maxsplit=1)[1]
        author = 'Setiausaha'
    elif not warn and re.search(r'] ?:', text) and '[' not in text.split(':', maxsplit=1)[0]:
        # some of the unparsed authors are due to an extra ]
        # this must be double-checked since it could be that it is a missing [ instead of extra ]
        author, speech, subtopic = get_author_and_speech(re.sub(r'] ?:', ':', text, 1), warn=text)
    elif not warn and ':' in text and '[' in text and ']:' not in text.replace(' ', '') and \
            text.count('[') == text.count(']') + 1:
        # some of the unparsed authors are due to a missing ]
        author, speech, subtopic = get_author_and_speech(text.replace(':', ']:', 1), warn=text)
    elif text == "10. Datuk Wira Haji Mohd. Anuar Mohd. Tahir [Temerloh] Datuk Wira Haji Mohd.\n":
        # special case where "minta" is not said in a numbered question
        # put here before the next elif that will be activated
        author = 'Datuk Wira Haji Mohd. Anuar Mohd. Tahir [Temerloh]'
        speech = 'Datuk Wira Haji Mohd.\n'
        subtopic = "10."
    elif text == "9. Datuk Dr. Ewon Ebin [Ranau] Menteri Kemajuan Luar Bandar dan Wilayah\n":
        # special case where "minta" is not said in a numbered question
        author = 'Datuk Dr. Ewon Ebin [Ranau]'
        speech = 'Menteri Kemajuan Luar Bandar dan Wilayah\n'
        subtopic = "9."
    elif 'Menteri di Jabatan Perdana Menteri, Dato’ Sri Azalina Dato’ Othman Said ' \
         '[Pengerang]: Terima kasih Tuan Pengerusi. Yang Berhormat Kulai, rang undang-undang ini\n' == text:
        # special case where , is used
        author = 'Menteri di Jabatan Perdana Menteri, Dato’ Sri Azalina Dato’ Othman Said [Pengerang]'
        speech = 'Terima kasih Tuan Pengerusi. Yang Berhormat Kulai, rang undang-undang ini\n'
    elif not warn and ']' in text and not text.endswith(']') and \
            not text.rsplit(']', maxsplit=1)[1].strip().startswith(':') and \
            text.count('[') == text.count(']'):
        # some of the unparsed authors are due to a missing colon :
        edited_text = ']:'.join(text.rsplit(']', 1))
        author, speech, subtopic = get_author_and_speech(edited_text, warn=text)
    elif re.search(r'^((Abdul Azeez bin Abdul Rahim \[Baling]:)|'
                   r"(Ramli bin Dato' Mohd Nor \[Cameron Highlands]:)|"
                   r"(Ahmad Amzad bin Mohamed @ Hashim \[Kuala Terengganu]:)|"
                   r"(Abdul Latiff bin Abdul Rahman \[Kuala Krai]:)|"
                   r"(Maria Chin binti Abdullah \[Petaling Jaya]:)|"
                   r"(Seorang Ahli /Tuan Abdul Latiff bin Abdul Rahman \[Kuala Krai]:)|"
                   r"(Seri Tiong King Sing \[Bintulu]:)|"
                   r"(Teresa Kok Suh Sim:)|"
                   r"(Zuraida binti Kamaruddin:)|"
                   r"(Seri Dr\. Adham bin Baba \[Tenggara]:)|"
                   r"(Kelvin Yii Lee Wuen \[Bandar Kuching]:))", text):
        # special cases, the Dewan Rakyat did not give them salutatory titles
        # to minimize word edits, we will just treat them as special cases in the parser
        # instead of using edit_hansards.py
        author, speech = text.split(':', maxsplit=1)
    if author != '' and warn != '':
        with open('warnings/autocorrected_authors.txt', 'a') as f:
            f.write(warn + '\n')
    return author, speech, subtopic


def insert_speech(current):
    if current['speech'] == '':
        return []
    return [[current['level_1'], current['level_2'], current['level_3'],
             current['timestamp'], current['author'], current['speech']]]


def put_annotations_on_new_line(text, bold, italics):
    # assumptions
    # 1. [ does not end on a line
    for row in text:
        assert row.strip()[-1] != '[', f'Error [ on end of line: {row}'
    row_id = 0
    num_unclosed_brackets = 0
    while row_id < len(text):
        letter_id = 0
        while letter_id < len(text[row_id]):
            if num_unclosed_brackets > 0:
                # we are currently in an annotation
                if text[row_id][letter_id] == ']':
                    num_unclosed_brackets -= 1
                    if num_unclosed_brackets == 0:
                        # end of annotation
                        if text[row_id][:letter_id + 1] == '\n':
                            assert letter_id + 1 == len(text[row_id])
                            continue
                        text[row_id] = text[row_id][:letter_id + 1] + '\n' + text[row_id][letter_id + 1:]
                        bold[row_id] = bold[row_id][:letter_id + 1] + '\n' + bold[row_id][letter_id + 1:]
                        italics[row_id] = italics[row_id][:letter_id + 1] + '\n' + italics[row_id][letter_id + 1:]
                elif text[row_id][letter_id] == '[':
                    num_unclosed_brackets += 1
            elif text[row_id][letter_id] == '[' and letter_id + 1 < len(text[row_id]) and \
                    italics[row_id][letter_id + 1] == '1':
                # annotation detected
                num_unclosed_brackets = 1
                if letter_id - 1 >= 0 and text[row_id][letter_id - 1] != '\n':
                    # split to newline
                    text[row_id] = text[row_id][:letter_id] + '\n' + text[row_id][letter_id:]
                    bold[row_id] = bold[row_id][:letter_id] + '\n' + bold[row_id][letter_id:]
                    italics[row_id] = italics[row_id][:letter_id] + '\n' + italics[row_id][letter_id:]
                    letter_id += 1
            letter_id += 1
        row_id += 1
    text = [x.strip() + '\n' for x in (''.join(text)).split('\n') if x.strip()]
    bold = [x.strip() + '\n' for x in (''.join(bold)).split('\n') if x.strip()]
    italics = [x.strip() + '\n' for x in (''.join(italics)).split('\n') if x.strip()]
    return text, bold, italics


def tabulate(hansard_date):
    print(hansard_date)
    with open('categories.json', 'r') as f:
        categories = json.load(f)
    year = hansard_date[-4:]
    dir_path = f"tabulated/{year}/"
    if not os.path.isdir(dir_path):
        os.mkdir(dir_path)
    sortable_date = f'{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}'  # YYYY-MM-DD
    dir_path += f"{sortable_date}/"
    if not os.path.isdir(dir_path):
        os.mkdir(dir_path)

    # the strategy is to iterate across rows
    # store the contents of the preprocessed text file in a list
    input_dir = f"pretabulation/{year}/{sortable_date}/"
    with open(f"{input_dir}plaintext.txt", 'r') as f:
        text = f.readlines()
    with open(f"{input_dir}bold.txt", 'r') as f:
        bold = f.readlines()
    with open(f"{input_dir}italics.txt", 'r') as f:
        italics = f.readlines()
    assert len(text) == len(bold) == len(italics), \
        f'Length of text, bold and italics do not match: {len(text)} vs {len(bold)} vs {len(italics)}'

    text, bold, italics = put_annotations_on_new_line(text, bold, italics)

    doa_seen = False
    num_rows = len(text)
    speeches = []
    blank_speech = {
        "author": '',
        "speech": '',
        "timestamp": '',
        "level_1": '',
        "level_2": '',
        "level_3": '',
    }
    current = blank_speech
    row_id = -1
    dewan_tangguh = False
    while row_id + 1 < num_rows:
        row_id += 1

        # run until DOA first
        if 'DOA' == text[row_id].strip():
            doa_seen = True
            continue
        if not doa_seen:
            # ignore rows before DOA except for the starting time
            if 'Mesyuarat dimulakan' in text[row_id]:
                current['timestamp'] = text[row_id].split('pukul')[-1].strip()
            continue

        # determine whether the current line is a continuation of speech
        # first check whether it is an annotation
        if text[row_id].startswith('[') and italics[row_id][1] == '1':
            if text[row_id].startswith('[Dewan ditangguhkan') or \
                    text[row_id].startswith('[Mesyuarat ditangguhkan'):
                dewan_tangguh = True
            # annotation detected
            speeches += insert_speech(current)
            old_author = current['author']
            current['speech'] = text[row_id]
            current['author'] = "ANNOTATION"
            add_idx = 1
            num_unclosed_brackets = text[row_id].count('[') - text[row_id].count(']')
            while add_idx + row_id < num_rows and num_unclosed_brackets > 0:
                current['speech'] += text[row_id + add_idx]
                num_unclosed_brackets += text[row_id + add_idx].count('[') - text[row_id + add_idx].count(']')
                if text[row_id + add_idx].startswith('[Dewan ditangguhkan') or \
                        text[row_id + add_idx].startswith('[Mesyuarat ditangguhkan'):
                    dewan_tangguh = True
                add_idx += 1
            row_id += add_idx - 1
            speeches += insert_speech(current)
            current['author'] = old_author
            current['speech'] = ''
            continue
        # now check if it is author or title etc
        if '1' not in bold[row_id]:
            # if there is no bold in a line
            # then most likely it is a continuation of speech
            current['speech'] += text[row_id]
            continue
        else:
            if text[row_id].strip().lower() == "lampiran":
                # end of Hansard
                if not dewan_tangguh:
                    print(f'Lampiran found without dewan tangguh: {text[row_id]}')
                break

            # either timestamp, new category, new author or the like
            if is_timestamp(text[row_id]):
                # timestamp
                speeches += insert_speech(current)
                current['speech'] = ''
                current['timestamp'] = text[row_id].strip()
                continue

            author, speech, subtopic = get_author_and_speech(text[row_id])
            if author != '':
                speeches += insert_speech(current)
                current['author'] = author
                assert speech[-1] == '\n', f"Speech does not end with newline: {speech}"
                current['speech'] = speech
                if subtopic:
                    current['level_2'] = subtopic
                    current['level_3'] = ""
                continue

            # sometimes the author has too long name and overflow to second line
            # but make sure this is not an annotation
            if row_id + 1 < num_rows and \
                    not (text[row_id + 1].startswith('[') and italics[row_id + 1][1] == '1'):
                concat_rows = f'{text[row_id].strip()} {text[row_id + 1]}'
                author, speech, subtopic = get_author_and_speech(concat_rows)
                if author != '':
                    speeches += insert_speech(current)
                    current['author'] = author
                    current['speech'] = speech
                    if subtopic:
                        current['level_2'] = subtopic
                        current['level_3'] = ""
                    # add to the loop counter additionally
                    row_id += 1
                    continue

            if bold[row_id].count('1') < 4:
                # most likely it is just a stray bold
                stray_bold = text[row_id]
                num_bold = bold[row_id].count('1')
                current['speech'] += stray_bold
                with open("warnings/stray_bolds.txt", 'a') as f:
                    f.write(f'{hansard_date} with num bold: {num_bold}\n{stray_bold}{bold[row_id]}\n')
                continue

            if current['author'] == "" and current['speech'] == '' and current['level_1'] != '':
                # most likely a level_2 immediately following a level_1
                # usually a chain of bolds
                add_idx = 1
                current['level_2'] = text[row_id]
                current['level_3'] = ""
                while row_id + add_idx < num_rows and \
                        prop_of_1_among_binary(bold[row_id + add_idx]) > 0.8 and \
                        not is_timestamp(text[row_id + add_idx]) and \
                        not get_author_and_speech(text[row_id + add_idx])[0] and \
                        not (text[row_id + add_idx].startswith('[') and italics[row_id + add_idx][1] == '1'):
                    current['level_2'] += text[row_id + add_idx]
                    add_idx += 1
                row_id += add_idx - 1
                with open("warnings/level_2_following_level_1.txt", 'a') as f:
                    f.write(f"{hansard_date}\n{current['level_2']}\n")
                continue

            if prop_of_1_among_binary(bold[row_id]) < 0.9:
                # categories shouldn't have mixed unbolds
                # treat them as stray bolds
                current['speech'] += text[row_id]
                with open("warnings/mixed_bolds.txt", 'a') as f:
                    f.write(f'{hansard_date}\n{text[row_id]}{bold[row_id]}\n')
                continue

            if upper_lower_ratio(text[row_id]) > 1:
                # could be a new category
                # Only possible to parse as category when the speech is non-empty
                # see example below where otherwise the USUL will start a new category
                # RANG UNDANG-UNDANG
                # RANG UNDANG-UNDANG PERBEKALAN 2023
                # Bacaan Kali Yang Kedua
                # DAN
                # USUL
                # ANGGARAN PEMBANGUNAN 2023
                if text[row_id].strip() in categories:
                    # direct match
                    speeches += insert_speech(current)
                    current['author'] = ""
                    current['level_1'] = text[row_id].strip()
                    current['level_2'] = ""
                    current['level_3'] = ""
                    current['speech'] = ""
                    continue
                # keep elongating the category scope and try fuzzy matching until the category score goes down
                add_idx = 1
                current_category = text[row_id].strip()
                current_category_probability = category_probability(current_category, categories)
                while row_id + add_idx < num_rows and upper_lower_ratio(text[row_id + add_idx]) > 1 and \
                        category_probability(current_category + ' ' + text[row_id + add_idx].strip(),
                                             categories) > current_category_probability:
                    current_category += ' ' + text[row_id + add_idx].strip()
                    current_category_probability = category_probability(current_category, categories)
                    add_idx += 1
                if current_category_probability > 0.9:
                    speeches += insert_speech(current)
                    current['author'] = ""
                    current['level_1'] = current_category
                    current['level_2'] = ""
                    current['level_3'] = ""
                    current['speech'] = ""
                    row_id += add_idx - 1
                    with open("warnings/matched_categories.csv", 'a') as f:
                        f.write(f'{hansard_date},{current_category},{current_category_probability}\n')
                    continue
                # could be a capitalised subtopic
                speeches += insert_speech(current)
                current['author'] = ""
                current['speech'] = ""
                current['level_3'] = ""
                add_idx = 1
                current['level_2'] = text[row_id]
                # allow empty lines as separator
                while row_id + add_idx < num_rows and \
                        prop_of_1_among_binary(bold[row_id + add_idx]) > 0.8 \
                        and not is_timestamp(text[row_id + add_idx]) \
                        and get_author_and_speech(text[row_id + add_idx])[0] == "" \
                        and not text[row_id + add_idx].startswith('Bismilla') \
                        and (
                        row_id + add_idx + 1 >= num_rows or
                        get_author_and_speech(f'{text[row_id + add_idx].strip()} {text[row_id + add_idx + 1]}')[0] == ""
                ):
                    current['level_2'] += text[row_id + add_idx]
                    add_idx += 1
                row_id += add_idx - 1
                with open("warnings/capitalised_level_2.txt", 'a') as f:
                    f.write(f"{hansard_date}\n{current['level_2']}\n")
                continue

            # these are lower-cased bold sentences
            # most likely a level_3 subtopic
            if re.search(r'Yang (Tidak )?((Bersetuju)|(Hadir)|(Mengundi)):', text[row_id]) or \
                    re.search(r'^Bacaan Kali Yang', text[row_id]):
                speeches += insert_speech(current)
                current['author'] = ""
                current['speech'] = ""
                current['level_3'] = text[row_id].strip()
                if current['level_2'] == "":
                    print(f'WARN: level_2 not taken but inserting level_3: {text[row_id]}')
                continue
            elif re.search(r'^(Maksud)|(Kepala)|(Fasal)|(Bab)|(Tajuk)|(Jadual)[A-Za-z0-9-[\], ]+[–-]',
                           text[row_id]):
                speeches += insert_speech(current)
                add_idx = 1
                current['author'] = ""
                current['speech'] = ""
                current['level_3'] = text[row_id]
                # it could be followed by similar level_3 markers
                while row_id + add_idx < num_rows and \
                        prop_of_1_among_binary(bold[row_id + add_idx]) > 0.8 and \
                        re.search(r'^(Maksud)|(Kepala)|(Fasal)|(Bab)|(Tajuk)|(Jadual)[A-Za-z0-9-[\], ]+[–-]',
                                  text[row_id + add_idx]):
                    current['level_3'] += text[row_id + add_idx]
                    add_idx += 1
                row_id += add_idx - 1
                if current['level_2'] == "":
                    print(f'WARN: level_2 not taken but inserting level_3: {text[row_id]}')
                continue

            # special cases
            if re.fullmatch(r'Perutusan [Dd]aripada Dewan Negara [kK]epada Dewan Rakyat', text[row_id].strip()):
                # common title of this document
                # treat as continuation of speech
                current['speech'] += text[row_id]
                continue
            elif re.search(r'^[“"]?((Bahawa)|(BAHAWA)|(DAN BAHAWA)|(Dengan ini)|(DENGAN INI))', text[row_id]):
                # treat as continuation of speech
                current['speech'] += text[row_id]
                continue
            elif hansard_date == "02112018" and \
                    (re.search(r'^Strategi \d+:', text[row_id]) or re.search(r' [–-]$', text[row_id].strip())):
                # during the budget 02112018
                speeches += insert_speech(current)
                current['author'] = ""
                current['speech'] = ""
                current['level_3'] = text[row_id].strip()
                continue
            # unhandled case
            print(f'WARN IN-TEXT BOLD:\n{text[row_id]}{bold[row_id]}{italics[row_id]}')
            with open("warnings/in-text-bold.txt", 'a') as f:
                f.write(f'{hansard_date}\n{text[row_id]}{bold[row_id]}{italics[row_id]}\n')
            current['speech'] += text[row_id]

    speeches += insert_speech(current)

    # remove trailing newlines
    for idx in range(len(speeches)):
        for idx2 in range(len(current)):
            speeches[idx][idx2] = speeches[idx][idx2].strip()

    # extract timestamps from annotations
    row_id = -1
    while row_id + 1 < len(speeches):
        row_id += 1
        if speeches[row_id][4] != "ANNOTATION":
            continue
        # the 5th item is the speech
        if has_timestamp_in_annotation(speeches[row_id][5]):
            with open("warnings/timestamp_in_annotation.txt", 'a') as f:
                f.write(f'{hansard_date}\n{speeches[row_id][5]}\n\n')
            old_timestamp = speeches[row_id][3]
            new_timestamp = get_timestamp_from_annotation(speeches[row_id][5])
            add_idx = 0
            while row_id + add_idx < len(speeches) and speeches[row_id + add_idx][3] == old_timestamp:
                speeches[row_id + add_idx][3] = new_timestamp
                add_idx += 1


    old_timestamp_list = [speech[3] for speech in speeches]
    # standardise timestamps into 24 hour format
    for row_id in range(len(speeches)):
        speeches[row_id][3] = standardise_timestamp(speeches[row_id][3])

    # post-tabulation warnings
    # check if annotation is too long, usually missing ].
    # if without error it is usually [Diputuskan,
    for speech in speeches:
        if speech[4] == "ANNOTATION" and speech[5].count('\n') > 5:
            with open("warnings/annotation_too_long.txt", 'a') as f:
                f.write(f'{hansard_date}\n{speech[5]}\n\n')

    # check for uppercased misidentified non-authors
    for speech in speeches:
        if speech[4] != "ANNOTATION" and upper_lower_ratio(speech[4]) > 0.8:
            with open("warnings/uppercased_non_author.txt", 'a') as f:
                f.write(f'{hansard_date}\n{speech[4]}\n\n')

    # check that timestamps are in order
    timestamps = [speech[3] for speech in speeches]
    sorted_timestamps = sorted(timestamps)
    if timestamps != sorted_timestamps:
        with open("warnings/unsorted_timestamps.txt", 'a') as f:
            f.write(f'\n{hansard_date}\n')
            for idx in range(len(timestamps)):
                if timestamps[idx] != sorted_timestamps[idx]:
                    f.write(f'{old_timestamp_list[idx]}, {timestamps[idx]}, {sorted_timestamps[idx]}\n')

    # export speeches to csv
    with open(f'{dir_path}result.csv', mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['level_1', 'level_2', 'level_3', 'timestamp', 'author', 'speech'])
        writer.writerows(speeches)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("hansard_date", help="hansard_date eg. 23052023",
                        default="06032023", nargs="?")
    # Parse arguments
    args = parser.parse_args()
    tabulate(args.hansard_date)
