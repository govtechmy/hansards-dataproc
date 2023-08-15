"""Uses the output of preprocess.py to generate the csv file of speeches"""
import argparse
import os
import re

categories = [
    'JAWAPAN-JAWAPAN LISAN BAGI PERTANYAAN-PERTANYAAN',
    'JAWAPAN-JAWAPAN MENTERI BAGI PERTANYAAN-PERTANYAAN',
    'USUL',
    'RANG UNDANG-UNDANG',
    'PERTANYAAN-PERTANYAAN BAGI JAWAB LISAN',
    'PEMASYHURAN DARIPADA TUAN YANG DI-PERTUA',
    "USUL-USUL",
    "WAKTU PERTANYAAN-PERTANYAAN MENTERI",
    "RANG UNDANG-UNDANG DIBAWA KE DALAM MESYUARAT"
]


def is_header(text):
    # returns the page number if it is the following form, else None
    # DR.28.3.2023 1
    # 2                                                               DR 8.3.2018
    # DR 8.3.2018                                                                  1
    return re.fullmatch(r'[ \.\d]*DR[ \.\d]*\n', text)


def is_timestamp(text):
    return re.search(r'(■|◼||▪) ?\d{4}\.?', text) or \
           re.search(r'^ *\d{1,2}[.:] ?\d{2} ?((pg)|(PG)|(pagi)|(tgh)|(Tgh)|(ptg)|(petang)|(mlm)|(malam))\.?', text)
    # Tgh is for 18102018
    # PG is for 16072018


def get_page_number(header_text):
    header_text = header_text.strip()
    if header_text.startswith('DR'):
        # some numbers might be in the form 1  1
        # some years are 2023.
        # some years missing end (2019 becomes 201)
        # get the page number after the year
        return re.split(r'\d{4}\.?', header_text)[-1].replace(' ', '')
    else:
        return header_text.split('DR')[0].replace(' ', '')


def get_author_and_speech(text):
    assert text.strip() == text, f'Expected "{text.strip()}" but got "{text}"'
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
        author += ']'
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
    elif re.search(r'^\d{1,2}\. [A-Za-z `.’\'@/\-()]+\[[A-Za-z \-]+]:? [Mm]inta', text):
        # JAWAPAN-JAWAPAN LISAN BAGI PERTANYAAN-PERTANYAAN
        # 1. Tuan Tan Kok Wai [Cheras] minta Menteri Pembangunan Usahawan menyatakan,
        author, speech = text.split('minta', maxsplit=1)
        if author.endswith(':'):
            author = author[:-1]
        speech = 'minta ' + speech
        subtopic, author = author.split('.', maxsplit=1)
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
        author += ']'  # add back the closing bracket
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
    return author, speech, subtopic


def tabulate(hansard_date):
    print(hansard_date)
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
    with open(f"preprocessed/{year}/{sortable_date}/plaintext.txt", 'r') as f:
        text = f.readlines()
    with open(f"preprocessed/{year}/{sortable_date}/bold.txt", 'r') as f:
        bold = f.readlines()
    with open(f"preprocessed/{year}/{sortable_date}/italics.txt", 'r') as f:
        italics = f.readlines()
    assert len(text) == len(bold) == len(italics), \
        f'Length of text, bold and italics do not match: {len(text)} vs {len(bold)} vs {len(italics)}'

    expected_page_num = -1
    doa_seen = False
    num_rows = len(text)
    speeches = []
    blank_speech = {
        "author": '',
        "speech": '',
        "category": '',
        "timestamp": '',
        "subtopic": ''
    }
    current = blank_speech
    row_id = -1
    while row_id + 1 < num_rows:
        row_id += 1
        # discard header rows
        if is_header(text[row_id]):
            page_num = int(get_page_number(text[row_id]))
            if expected_page_num == -1:
                expected_page_num = page_num
            # makes sure all pages are all accounted for
            assert page_num == expected_page_num, \
                f'Page number {page_num} does not match expected {expected_page_num}'
            expected_page_num += 1
            continue
        # run until DOA first
        if 'DOA' == text[row_id].strip():
            doa_seen = True
            continue
        if not doa_seen:
            # ignore rows before DOA except for the starting time
            if 'Mesyuarat dimulakan' in text[row_id]:
                current['timestamp'] = text[row_id].split('pukul')[-1].strip()
            continue

        # due to the nature of parsing the layout, sometimes single spaces are parsed as double
        # to reduce inconsistencies, we replace all double spaces with single spaces
        text[row_id] = text[row_id].replace('  ', ' ')

        # indentation is not uniform either, and can mess with author recognition
        text[row_id] = text[row_id].strip()

        # determine whether the current line is a continuation of speech
        if '1' not in bold[row_id] and not (
                text[row_id].startswith('[') and (text[row_id].endswith(']') or ']' not in text[row_id])
        ):
            # if the whole line is not bolded and is not an annotation ie. starts with [,
            # then most likely it is a continuation of speech
            # these includes empty lines
            current['speech'] += text[row_id]
        else:
            # either timestamp, new category, new author or the like
            if is_timestamp(text[row_id]):
                # timestamp
                speeches.append(current)
                current['speech'] = ''
                current['timestamp'] = text[row_id].strip()
                continue

            author, speech, subtopic = get_author_and_speech(text[row_id])
            if author != '':
                speeches.append(current)
                current['author'] = author
                current['speech'] = speech
                if subtopic:
                    current['subtopic'] = subtopic
                continue

            # sometimes the author has too long name and overflow to second line
            if row_id + 1 < num_rows:
                concat_rows = text[row_id] + ' ' + text[row_id + 1].strip()
                concat_rows = concat_rows.strip().replace('  ', ' ')  # still strip since text could be newline
                author, speech, subtopic = get_author_and_speech(concat_rows)
                if author != '':
                    speeches.append(current)
                    current['author'] = author
                    current['speech'] = speech
                    if subtopic:
                        current['subtopic'] = subtopic
                    # add to the loop counter additionally
                    row_id += 1
                    continue

            if text[row_id][0] == '[' and text[row_id][-1] == ']':
                # Annotations, examples below
                # [Tuan Yang di-Pertua mempengerusikan Jawatankuasa] 
                # [Majlis Mesyuarat bersidang semula] 
                # [Dewan ditangguhkan pada pukul 4.59 petang] 
                # [Sesi Waktu Pertanyaan-pertanyaan Menteri tamat] 
                # [Soalan No.4 – Y.B. Tuan M. Kulasegaran (Ipoh Barat) tidak hadir]
                speeches.append(current)
                current['author'] = "NO AUTHOR"
                current['speech'] = text[row_id].strip()
                # TODO extract timestamps from annotations if present
                continue

            # similarly annotations can span two lines
            if row_id + 1 < num_rows:
                concat_rows = text[row_id] + ' ' + text[row_id + 1].strip()
                concat_rows = concat_rows.replace('  ', ' ')
                if concat_rows[0] == '[' and concat_rows[-1] == ']':
                    speeches.append(current)
                    current['author'] = "NO AUTHOR"
                    current['speech'] = concat_rows.strip()
                    # add to the loop counter additionally
                    row_id += 1
                    continue
            # or 3 lines
            if row_id + 2 < num_rows:
                concat_rows = text[row_id] + ' ' + text[row_id + 1].strip() + ' ' + text[row_id + 2].strip()
                concat_rows = concat_rows.replace('  ', ' ')
                if concat_rows[0] == '[' and concat_rows[-1] == ']':
                    speeches.append(current)
                    current['author'] = "NO AUTHOR"
                    current['speech'] = concat_rows.strip()
                    # add to the loop counter additionally
                    row_id += 1
                    continue

            # many of the unparsed authors are due to an erroneous ]  or a missing ]
            if re.search(r'] ?:', text[row_id]) and '[' not in text[row_id]:
                author, speech, subtopic = get_author_and_speech(re.sub(r'] ?:', ':', text[row_id], 1))
                # TODO add these into a warning file for double-checking
                if author != '':
                    speeches.append(current)
                    current['author'] = author
                    current['speech'] = speech
                    if subtopic:
                        current['subtopic'] = subtopic
                    continue
            if ':' in text[row_id] and '[' in text[row_id] and ']' not in text[row_id]:
                author, speech, subtopic = get_author_and_speech(text[row_id].replace(':', ']:', 1))
                # TODO add these into a warning file for double-checking
                if author != '':
                    speeches.append(current)
                    current['author'] = author
                    current['speech'] = speech
                    if subtopic:
                        current['subtopic'] = subtopic
                    continue

            if text[row_id] in categories:
                speeches.append(current)
                current['author'] = ""
                current['category'] = text[row_id].strip()
                current['speech'] = ""
                # TODO do not parse this as category but instead as subtopic if
                #  there is no speech since last category, example
                # RANG UNDANG-UNDANG
                # RANG UNDANG-UNDANG PERBEKALAN 2023
                # Bacaan Kali Yang Kedua
                # DAN
                # USUL
                # ANGGARAN PEMBANGUNAN 2023
            else:
                print(text[row_id])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("hansard_date", help="hansard_date eg. 23052023",
                        default="28032023", nargs="?")
    # Parse arguments
    args = parser.parse_args()
    tabulate(args.hansard_date)
