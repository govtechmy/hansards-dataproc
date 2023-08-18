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
    elif re.search(r'^(Timbalan )?[Mm]enteri [A-Za-z,()\-& ]+(\[Ekonomi] )?\[[A-Za-z `.’\'@/(\-)]+] ?:', text):
        # Minister or Deputy Minister
        # allows () at the name part as they can have constituencies too
        # , is for Menteri Pembangunan Wanita, Keluarga dan Masyarakat
        # () is for Menteri di Jabatan Perdana Menteri (Parlimen dan Undang-Undang)
        # - is for Timbalan Menteri di Jabatan Perdana Menteri (Undang-undang dan
        # Reformasi Institusi) [Tuan Ramkarpal Singh a/l Karpal Singh]: Tuan Yang di-
        author, speech = text.split(':', maxsplit=1)
    elif re.search(r'^((Timbalan )|(Yang Amat Berhormat ))?Perdana [A-Za-z, ]+\[[A-Za-z `.’\'@/(\-)]+]:', text):
        # Prime Minister or Deputy Primer Minister
        # allows () as they can have constituencies too
        author, speech = text.split(']:', maxsplit=1)
        author += ']'
    elif re.search(r'^((Tuan)|(Timbalan)) Pengerusi (Timbalan Yang di-Pertua )?\[[A-Za-z `.’\'@/(\-)]*]:', text):
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
            r'^((Tuan)|(Datuk)|(Dato)|(Tan Sri)|(Puan)|(Dr\.)|(YM)|(Ustaz)|(Tun)|'
            r'(Laksamana)|(Mejar)|(Komander)|(Seri Paduka)|(Tengku)|(Hajah)|(Raja)|(Brig)|(Datin))'
            r'[A-Za-z `.’\'@/\-()]+:',
            text):
        # continuation of Menteri or Timbalan Menteri, example
        # Timbalan Menteri di Jabatan Perdana Menteri [Datuk Wira Dr. Md Farid bin Md
        # Rafik]: Bismillahir Rahmanir Rahim.
        #  Datuk Wira Dr. Md Farid bin Md Rafik:  Bismillahir Rahmanir Rahim.
        # YM Tengku Dato’ Sri Zafrul Tengku Abdul Aziz: Okey, saya jawab twin deficit
        # Datuk Dr. Haji Zulkifli Mohamad Al-Bakri: ...Saya hendak minta maaf banyak-
        author, speech = text.split(':', maxsplit=1)
    elif re.search(r'^[A-Za-z `.’\'@/(),\-]+\[[A-Za-z \-–]+][ -]?:', text):
        # possible MP
        # TODO check start with MP salutation eg. Tan Sri or Tuan
        author, speech = text.split(':', maxsplit=1)
        # TODO sometimes start with numbering eg. 1.
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
        author, speech, subtopic = get_author_and_speech(re.sub(r'] ?:', ':', text, 1), warn=text)
    elif not warn and ':' in text and '[' in text and ']' not in text:
        # some of the unparsed authors are due to a missing ]
        author, speech, subtopic = get_author_and_speech(text.replace(':', ']:', 1), warn=text)
    elif not warn and ':' not in text and \
            re.search(r'^((Tuan)|(Datuk)|(Dato)|(Tan Sri)|(Puan)|(Dr\.)|(YM)|(Ustaz)|(Tun)|'
                      r'(Laksamana)|(Mejar)|(Komander)|(Seri Paduka)|(Tengku)|(Hajah)|(Raja)|(Brig)|(Datin))'
                      r'[A-Za-z `.’\'@/\-()]+\[[A-Za-z \-–]+]', text):
        # some of the unparsed authors are due to a missing colon :
        author, speech, subtopic = get_author_and_speech(text.replace(']', ']:', 1), warn=text)
    if author != '' and warn != '':
        with open('warnings/autocorrected_authors.txt', 'a') as f:
            f.write(warn + '\n')
    return author, speech, subtopic


def insert_speech(current):
    if current['speech'] == '':
        return []
    return [[current['level-1'], current['level-2'], current['level-3'],
             current['timestamp'], current['author'], current['speech']]]


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

    doa_seen = False
    num_rows = len(text)
    speeches = []
    blank_speech = {
        "author": '',
        "speech": '',
        "timestamp": '',
        "level-1": '',
        "level-2": '',
        "level-3": '',
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
        if '1' not in bold[row_id]:
            # if there is no bold in a line
            # then most likely it is a continuation of speech
            # these includes annotations without bold e.g. [Tepuk]
            # for annotations, do a look ahead to ensure that it is not a bolded one
            if prop_of_1_among_binary(italics[row_id]) > 0.5 and \
                    '[' in text[row_id] and not text[row_id + 1].startswith('[') and \
                    row_id + 1 < num_rows and '1' in bold[row_id + 1] \
                    and re.search(r'mempengerusikan (([Mm]esyuarat)|(Jawatankuasa))', text[row_id + 1]):
                text[row_id + 1] = text[row_id] + text[row_id + 1]
                bold[row_id + 1] = bold[row_id] + bold[row_id + 1]
                italics[row_id + 1] = italics[row_id] + italics[row_id + 1]
                continue

            current['speech'] += text[row_id]
        else:
            if row_id == 793:
                print()
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
                    current['level-2'] = subtopic
                    current['level-3'] = ""
                continue

            # sometimes the author has too long name and overflow to second line
            if row_id + 1 < num_rows:
                concat_rows = f'{text[row_id].strip()} {text[row_id + 1]}'
                author, speech, subtopic = get_author_and_speech(concat_rows)
                if author != '':
                    speeches += insert_speech(current)
                    current['author'] = author
                    current['speech'] = speech
                    if subtopic:
                        current['level-2'] = subtopic
                        current['level-3'] = ""
                    # add to the loop counter additionally
                    row_id += 1
                    continue

            if bold[row_id].count('1') < 4:
                # most likely it is just a stray bold
                stray_bold = text[row_id]
                num_bold = bold[row_id].count('1')
                # sometimes stray bolds go over a line as annotations
                # Perbelanjaan Pembangunan 2023 dalam Jawatankuasa sebuah-buah Majlis.” [Hari 
                # Kesepuluh]
                if row_id + 1 < num_rows and '[' in text[row_id] and \
                        ']' not in text[row_id] and ']' in text[row_id + 1] and \
                        prop_of_1_among_binary(italics[row_id + 1]) > 0.5:
                    stray_bold += text[row_id + 1]
                    num_bold += bold[row_id + 1].count('1')
                    row_id += 1
                current['speech'] += stray_bold
                with open("warnings/stray_bolds.txt", 'a') as f:
                    f.write(f'{hansard_date} with num bold: {num_bold}\n{stray_bold}\n')
                continue

            if prop_of_1_among_binary(italics[row_id]) > 0.8:
                if not text[row_id].startswith('['):
                    print(f'ERROR: annotation without starting [: {text[row_id]}')
                # Annotations, examples below
                # this will also take care quite a lot of bolds
                # [Tuan Yang di-Pertua mempengerusikan Jawatankuasa] 
                # [Majlis Mesyuarat bersidang semula] 
                # [Dewan ditangguhkan pada pukul 4.59 petang] 
                # [Sesi Waktu Pertanyaan-pertanyaan Menteri tamat] 
                # [Soalan No.4 – Y.B. Tuan M. Kulasegaran (Ipoh Barat) tidak hadir]
                if text[row_id].startswith('[Dewan ditangguhkan') or \
                        text[row_id].startswith('[Mesyuarat ditangguhkan'):
                    dewan_tangguh = True
                speeches += insert_speech(current)
                current['author'] = "ANNOTATIONS"
                current['speech'] = ''
                add_idx = 0
                while row_id + add_idx < num_rows and prop_of_1_among_binary(italics[row_id + add_idx]) > 0.8:
                    current['speech'] += text[row_id + add_idx]
                    add_idx += 1
                    if text[row_id + add_idx - 1].strip().endswith(']'):
                        break
                row_id += add_idx - 1
                # TODO extract timestamps from annotations if present
                continue

            if current['author'] == "" and current['level-1'] != '':
                # most likely a level-2 immediately following a level-1
                # usually a chain of bolds
                # TODO warn
                add_idx = 1
                current['level-2'] = text[row_id]
                current['level-3'] = ""
                while row_id + add_idx < num_rows and \
                        prop_of_1_among_binary(bold[row_id + add_idx]) > 0.8 and \
                        not is_timestamp(text[row_id + add_idx]) and \
                        not get_author_and_speech(text[row_id + add_idx])[0]:
                    current['level-2'] += text[row_id + add_idx]
                    add_idx += 1
                row_id += add_idx - 1
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
                    current['level-1'] = text[row_id].strip()
                    current['level-2'] = ""
                    current['level-3'] = ""
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
                    current['level-1'] = current_category
                    current['level-2'] = ""
                    current['level-3'] = ""
                    current['speech'] = ""
                    row_id += add_idx - 1
                    with open("warnings/matched_categories.csv", 'a') as f:
                        f.write(f'{hansard_date},{current_category},{current_category_probability}\n')
                    continue
                # could be a capitalised subtopic
                # TODO WARN
                speeches += insert_speech(current)
                current['author'] = ""
                current['speech'] = ""
                current['level-3'] = ""
                add_idx = 1
                current['level-2'] = text[row_id]
                # allow empty lines as separator
                while row_id + add_idx < num_rows and \
                        prop_of_1_among_binary(bold[row_id + add_idx]) > 0.8 \
                        and not is_timestamp(text[row_id + add_idx]) \
                        and get_author_and_speech(text[row_id + add_idx])[0] == "":
                    current['level-2'] += text[row_id + add_idx]
                    add_idx += 1
                row_id += add_idx - 1
                continue

            # these are lower-cased bold sentences
            # most likely a level-3 subtopic
            if re.search(r'Yang (Tidak )?((Bersetuju)|(Hadir)|(Mengundi)):', text[row_id]) or \
                    re.search(r'^Bacaan Kali Yang', text[row_id]):
                speeches += insert_speech(current)
                current['author'] = ""
                current['speech'] = ""
                current['level-3'] = text[row_id].strip()
                if current['level-2'] == "":
                    print(f'CHECK: level-2 not taken but inserting level-3: {text[row_id]}')
                continue
            elif re.search(r'^(Maksud)|(Kepala)|(Fasal)|(Bab)|(Tajuk)|(Jadual)[A-Za-z0-9-[\], ]+[–-]',
                           text[row_id]):
                # TODO warn
                speeches += insert_speech(current)
                add_idx = 1
                current['author'] = ""
                current['speech'] = ""
                current['level-3'] = text[row_id]
                # it could be followed by similar level-3 markers
                while row_id + add_idx < num_rows and \
                        prop_of_1_among_binary(bold[row_id + add_idx]) > 0.8 and \
                        re.search(r'^(Maksud)|(Kepala)|(Fasal)|(Bab)|(Tajuk)|(Jadual)[A-Za-z0-9-[\], ]+[–-]',
                                  text[row_id + add_idx]):
                    current['level-3'] += text[row_id + add_idx]
                    add_idx += 1
                row_id += add_idx - 1
                if current['level-2'] == "":
                    print(f'CHECK: level-2 not taken but inserting level-3: {text[row_id]}')
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
                current['level-3'] = text[row_id].strip()
                continue
            elif hansard_date == '12032019' and text[row_id].strip() == "Pada 7 Januari 2019:":
                # treat as continuation of speech
                current['speech'] += text[row_id]
                continue
            elif hansard_date in ['06062023', '12062023', '27092021', '18102018', '18102018', '05122019']:
                # these Hansard has bunch of bolded words as first word due to some important speeches
                # we checked them and they are all ok
                # treat as continuation of speech
                current['speech'] += text[row_id]
                continue
            # unhandled case
            print(f'WARN UNHANDLED BOLD: {text[row_id]}')
            current['speech'] += text[row_id]

    speeches += insert_speech(current)
    for idx in range(len(speeches)):
        for idx2 in range(6):
            speeches[idx][idx2] = speeches[idx][idx2].strip()
    # export speeches to csv
    with open(f'{dir_path}result.csv', mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['level-1', 'level-2', 'level-3', 'timestamp', 'author', 'speech'])
        writer.writerows(speeches)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("hansard_date", help="hansard_date eg. 23052023",
                        default="13032023", nargs="?")
    # Parse arguments
    args = parser.parse_args()
    tabulate(args.hansard_date)
