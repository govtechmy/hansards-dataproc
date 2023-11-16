"""Generate the csv file of speeches for a given Hansard.
"""
import argparse
import os
import re
from thefuzz import process
import json
import csv
from datetime import datetime, timedelta


def more_than_30_minutes_past(time_str1, time_str2):
    try:
        # Parse the time strings to datetime objects
        time1 = datetime.strptime(time_str1, "%H%M")
        time2 = datetime.strptime(time_str2, "%H%M")
    except ValueError:
        # Handle invalid time format
        raise ValueError("Invalid time format. Please use HHMM format.")

    # Find the absolute difference between the two times
    time_difference = (time2 - time1).total_seconds() / 60  # Convert seconds to minutes

    # Check if the difference is within 30 minutes
    return time_difference <= -30


def is_timestamp(text):
    text = text.strip()
    return (
        re.search(r"[■◼▪] ?\d{4}\.?", text)
        or re.search(
            r"^[■◼▪]?(\(cid:2[12]\))? *\d{1,2}[.:] ?\d ?\d ?((pg)|(PG)|(pagi)|(tgh)|(Tgh)|"
            r"(ptg)|(Ptg)|(petang)|(mlm)|(malam)|(pm))\.?",
            text,
        )
        or re.search(r"^(\(cid:[12]\))* ?\d{4}$", text)
    )
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
    def mod_24(x):
        assert len(x) == 4
        if x[:2] == "24":
            x = "00" + x[2:]
        return x

    # strip cid
    timestamp = re.sub(r"\(cid:[12]\)", "", timestamp)
    numbers = "".join(re.findall(r"\d+", timestamp))
    assert len(numbers) != 0
    if len(numbers) < 3:
        # 10 pagi
        numbers += "00"
    if re.search(r"^[■◼▪] ?\d{4}\.?", timestamp):
        # if there is a preceding bullet then it is usually in 24h format
        return mod_24(numbers)
    elif re.search(r"(pg)|(PG)|(pagi)", timestamp):
        if len(numbers) == 3:
            return mod_24("0" + numbers)
        else:
            assert (
                len(numbers) == 4
            ), f"Expected 4 digits but got {numbers} from {timestamp}"
            return mod_24(numbers)
    else:
        # malam, pm, tgh etc
        # apart from 12pm, all others need to add 12
        if len(numbers) == 4 and numbers[:2] == "12":
            return mod_24(numbers)
        hour = int(numbers[:-2]) + 12
        if hour >= 24:
            # they reported it in 24h
            hour -= 12
        return mod_24(str(hour) + numbers[-2:])


def prop_of_1_among_binary(text):
    assert re.fullmatch(r"[01\s]*", text), f'Expected binary string but got "{text}"'
    return text.count("1") / (text.count("0") + text.count("1"))


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


def get_author_and_speech(text, bold, italics, warn=""):
    author = ""
    speech = ""
    speech_bold = ""
    speech_italics = ""
    subtopic = ""
    if (
        re.search(
            r"^(Timbalan(an)? )?(Tuan )?([Yy]ang )?[dD]i-? ?[Pp]ertua[\[\]A-Za-z `.’\'@/(\-),]*:",
            text,
        )
        or re.search(r"^Setiausaha[\[\]A-Za-z `.’\'@/(\-),]*:", text)
        or re.search(
            r"^(Yang Berhormat )?(Timbalan )?(Perdana )?[Mm]enteri [A-Za-z,()\-& ]+(\[Ekonomi] )"
            r"?\[[A-Za-z `.’\'@/(\-)\[\]]+] ?:",
            text,
        )
        or re.search(
            r"^(Timbalan )?(Tuan )?Pengerusi (Timbalan Yang di-Pertua )?\[[A-Za-z `.’\'@/(\-)]*]:",
            text,
        )
        or re.search(
            r"^((Tuan)|(Datuk)|(Dato)|(Tan Sri)|(Puan)|(Dr\.)|(YM)|(Ustaz)|(Tun)|(Kapten)|(Haji)|(Ir\.)|(Datu)|(Cik)|"
            r"(Laksamana)|(Mejar)|(Komander)|(Seri Paduka)|(Tengku)|(Hajah)|(Raja)|(Brig)|(Datin)|(Prof\.) )"
            r"[A-Za-z `.’\'@/\-()]+:",
            text,
        )
        or re.search(
            r"^(Yang Berhormat )?"
            r"((Tuan)|(Datuk)|(Dato)|(Tan Sri)|(Puan)|(Dr\.)|(YM)|(Ustaz)|(Tun)|(Kapten)|(Haji)|(Ir\.)|(Datu)|(Cik)|"
            r"(Laksamana)|(Mejar)|(Komander)|(Seri Paduka)|(Tengku)|(Hajah)|(Raja)|(Brig)|(Datin)|(Prof\.) )"
            r"[A-Za-z `.’\'@/(),\-]+\[[A-Za-z \-–]+][ -]?:",
            text,
        )
        or re.search(
            r"^(Seorang Ahli ?:)|(Seorang ahli:)|(Seoarang ahli:)|(Seseorang Ahli:)|(seorang Ahli:)|"
            r"(Seorang Ahli Yang Berhormat:)|(Seorang Ahli Berucap)|(\[Seorang Ahli]:)|(Sorang Ahli:)|(Seorang Ali:)|"
            r"(Beberapa Ahli:)|(Beberapa orang Ahli:)|(Beberapa ahli:)|"
            r"(Beberapa Ahli Pembangkang:)|(Ahli-ahli:)|(Beberapa Orang Ahli:)|(Beberapa Ali:)",
            text,
        )
    ):
        # 3. allows () at the name part as they can have constituencies too
        # , is for Menteri Pembangunan Wanita, Keluarga dan Masyarakat
        # () and - is for Menteri di Jabatan Perdana Menteri (Parlimen dan Undang-Undang)
        # [] is for Menteri Sumber Manusia [Tuan M. Kulasegaran [Ipoh Barat]]
        # Timbalan Menteri Pendidikan [Puan Teo Nie Ching [Kulai]]

        # 4. Tuan Pengerusi Timbalan Yang di-Pertua [Tuan Nga Kor Ming]: Tidak apa, tidak

        # 5. continuation of Menteri or Timbalan Menteri using name only, example
        # Timbalan Menteri di Jabatan Perdana Menteri [Datuk Wira Dr. Md Farid bin Md Rafik]:
        # Datuk Wira Dr. Md Farid bin Md Rafik:

        # 6. possible MP
        split_idx = text.find(":")
        author = text[:split_idx]
        speech = text[split_idx + 1 :]
        speech_bold = bold[split_idx + 1 :]
        speech_italics = italics[split_idx + 1 :]
    elif re.search(
        r"^((Timbalan )|(Yang Amat Berhormat ))?Perdana [A-Za-z, ]+\[[A-Za-z `.’\'@/(\-)]+]:",
        text,
    ):
        # Prime Minister or Deputy Primer Minister
        # allows () as they can have constituencies too
        split_idx = text.find("]:")
        author = text[: split_idx + 1]
        speech = text[split_idx + 2 :]
        speech_bold = bold[split_idx + 2 :]
        speech_italics = italics[split_idx + 2 :]
    elif re.search(
        r"^\d{1,2}\.? [A-Za-z `.’\'@\/\-()]+\[[A-Za-z \-]+]:? *[Mm](em)?inta", text
    ):
        # JAWAPAN-JAWAPAN LISAN BAGI PERTANYAAN-PERTANYAAN
        # 1. Tuan Tan Kok Wai [Cheras] minta Menteri Pembangunan Usahawan menyatakan,
        split_idx = text.find("minta")
        if split_idx == -1:
            split_idx = text.find("Minta")
        author = text[:split_idx].strip()
        if author.endswith(":"):
            author = author[:-1]
        speech = text[split_idx:]
        speech_bold = bold[split_idx:]
        speech_italics = italics[split_idx:]
        # get the numbering
        subtopic, author = author.split(" ", maxsplit=1)
    elif text.startswith("Setiausaha:"):
        # Speaker of the House
        print("this happens")
        split_idx = text.find(":")
        author = text[:split_idx]
        speech = text[split_idx + 1 :]
        speech_bold = bold[split_idx + 1 :]
        speech_italics = italics[split_idx + 1 :]
    elif (
        not warn
        and re.search(r"] ?:", text)
        and "[" not in text.split(":", maxsplit=1)[0]
    ):
        # some of the unparsed authors are due to an extra ]
        # this must be double-checked since it could be that it is a missing [ instead of extra ]
        edit_idx = re.search(r"] ?:", text).start()
        edit_text = text[:edit_idx] + text[edit_idx + 1 :]
        edit_bold = bold[:edit_idx] + bold[edit_idx + 1 :]
        edit_italics = italics[:edit_idx] + italics[edit_idx + 1 :]
        author, speech, speech_bold, speech_italics, subtopic = get_author_and_speech(
            edit_text, edit_bold, edit_italics, warn=text
        )
    elif (
        not warn
        and ":" in text
        and "[" in text
        and "]:" not in text.replace(" ", "")
        and text.count("[") == text.count("]") + 1
    ):
        # some of the unparsed authors are due to a missing ]
        edit_idx = re.search(r":", text).start()
        edit_text = text[:edit_idx] + "]" + text[edit_idx:]
        edit_bold = bold[:edit_idx] + "1" + bold[edit_idx:]
        edit_italics = italics[:edit_idx] + "0" + italics[edit_idx:]
        author, speech, speech_bold, speech_italics, subtopic = get_author_and_speech(
            edit_text, edit_bold, edit_italics, warn=text
        )
    elif (
        text
        == "10. Datuk Wira Haji Mohd. Anuar Mohd. Tahir [Temerloh] Datuk Wira Haji Mohd.\n"
    ):
        # special case where "minta" is not said in a numbered question
        # put here before the next elif that will be activated
        author = "Datuk Wira Haji Mohd. Anuar Mohd. Tahir [Temerloh]"
        speech = "Datuk Wira Haji Mohd.\n"
        speech_bold = "00000 0000 0000 00000\n"
        speech_italics = "00000 0000 0000 00000\n"
        subtopic = "10."
    elif (
        text
        == "9. Datuk Dr. Ewon Ebin [Ranau] Menteri Kemajuan Luar Bandar dan Wilayah\n"
    ):
        # special case where "minta" is not said in a numbered question
        author = "Datuk Dr. Ewon Ebin [Ranau]"
        speech = "Menteri Kemajuan Luar Bandar dan Wilayah\n"
        speech_bold = "0000000 00000000 0000 000000 000 0000000\n"
        speech_italics = "0000000 00000000 0000 000000 000 0000000\n"
        subtopic = "9."
    elif (
        not warn
        and "]" in text
        and not text.endswith("]")
        and not text.rsplit("]", maxsplit=1)[1].strip().startswith(":")
        and text.count("[") == text.count("]")
    ):
        # some of the unparsed authors are due to a missing colon :
        edit_idx = text.rfind("]")
        edit_text = text[: edit_idx + 1] + ":" + text[edit_idx + 1 :]
        edit_bold = bold[: edit_idx + 1] + "1" + bold[edit_idx + 1 :]
        edit_italics = italics[: edit_idx + 1] + "0" + italics[edit_idx + 1 :]
        author, speech, speech_bold, speech_italics, subtopic = get_author_and_speech(
            edit_text, edit_bold, edit_italics, warn=text
        )
    elif re.search(
        r"^((Abdul Azeez bin Abdul Rahim \[Baling]:)|"
        r"(Ramli bin Dato' Mohd Nor \[Cameron Highlands]:)|"
        r"(Ahmad Amzad bin Mohamed @ Hashim \[Kuala Terengganu]:)|"
        r"(Abdul Latiff bin Abdul Rahman \[Kuala Krai]:)|"
        r"(Maria Chin binti Abdullah \[Petaling Jaya]:)|"
        r"(Seorang Ahli /Tuan Abdul Latiff bin Abdul Rahman \[Kuala Krai]:)|"
        r"(Seri Tiong King Sing \[Bintulu]:)|"
        r"(Teresa Kok Suh Sim:)|"
        r"(Zuraida binti Kamaruddin:)|"
        r"(Seri Dr\. Adham bin Baba \[Tenggara]:)|"
        r"(Mohd Sany bin Hamzan \[Hulu Langat]:)|"
        r"(Kelvin Yii Lee Wuen \[Bandar Kuching]:))",
        text,
    ):
        # special cases, the Dewan Rakyat did not give them salutatory titles
        # to minimize word edits, we will just treat them as special cases in the parser
        # instead of using edit_hansards.py
        split_idx = text.find(":")
        author = text[:split_idx]
        speech = text[split_idx + 1 :]
        speech_bold = bold[split_idx + 1 :]
        speech_italics = italics[split_idx + 1 :]
    if author != "" and warn != "":
        with open("warnings/autocorrected_authors.txt", "a") as f:
            f.write(warn + "\n")
    return author, speech, speech_bold, speech_italics, subtopic


def possible_author(text, bold, italics, idx, num_rows):
    # check if this line or the combination of the next is a valid author
    # return true if so
    if get_author_and_speech(text[idx], bold[idx], italics[idx])[0] != "":
        return True
    if idx + 1 < num_rows and not (
        text[idx + 1].startswith("[") and italics[idx + 1][1] == "1"
    ):
        concat_rows = f"{text[idx].strip()} {text[idx + 1]}"
        concat_rows_bold = f"{bold[idx].strip()} {bold[idx + 1]}"
        concat_rows_italics = f"{italics[idx].strip()} {italics[idx + 1]}"
        return (
            get_author_and_speech(concat_rows, concat_rows_bold, concat_rows_italics)[0]
            != ""
        )
    return False


def insert_speech(current):
    if current["speech"] == "":
        return []
    return [
        [
            current["level_1"],
            current["level_2"],
            current["level_3"],
            current["timestamp"],
            current["author"],
            current["speech"],
            current["speech_bold"],
            current["speech_italics"],
        ]
    ]


def markdownify(text, is_bold, is_italics):
    text = text.replace("*", "\*")
    suffix = ""
    if re.search(r"\s+$", text):
        suffix = re.search(r"\s+$", text).group(0)
        text = text.strip()
    if is_bold:
        text = f"**{text}**"
    if is_italics:
        text = f"*{text}*"
    return text + suffix


def add_formatting(text, bold, italics):
    assert (
        len(text.replace(" ", ""))
        == len(bold.replace(" ", ""))
        == len(italics.replace(" ", ""))
    ), (
        f"Without spaces, text ({text.replace(' ', '')}), "
        f"bold ({bold.replace(' ', '')}), "
        f"and italics ({italics.replace(' ', '')}) must be of the same length"
    )
    # begin by separating words into chunks of homogenous formatting
    if len(text) == 0:
        return ""
    assert re.search(
        r"\S", text[0]
    ), f"First character of text is not a non-whitespace character: {text}"
    assert re.search(
        r"\S", bold[0]
    ), f"First character of bold is not a non-whitespace character: {text}"
    assert re.search(
        r"\S", italics[0]
    ), f"First character of italics is not a non-whitespace character: {text}"
    current_text = text[0]
    current_bold = bold[0]
    current_italics = italics[0]
    result = ""
    for i in range(1, len(text)):
        if (bold[i] in ["0", "1"] and bold[i] != current_bold) or (
            italics[i] in ["0", "1"] and italics[i] != current_italics
        ):
            result += markdownify(
                current_text, current_bold == "1", current_italics == "1"
            )
            current_text = text[i]
            current_bold = bold[i]
            current_italics = italics[i]
        else:
            current_text += text[i]
    if current_text != "":
        result += markdownify(current_text, current_bold == "1", current_italics == "1")
    return result


def put_annotations_on_new_line(text, bold, italics):
    # assumptions
    # 1. [ does not end on a line
    for row in text:
        assert row.strip()[-1] != "[", f"Error [ on end of line: {row}"
    row_id = 0
    num_unclosed_brackets = 0
    while row_id < len(text):
        letter_id = 0
        while letter_id < len(text[row_id]):
            if num_unclosed_brackets > 0:
                # we are currently in an annotation
                if text[row_id][letter_id] == "]":
                    num_unclosed_brackets -= 1
                    if num_unclosed_brackets == 0:
                        # end of annotation
                        if text[row_id][: letter_id + 1] == "\n":
                            assert letter_id + 1 == len(text[row_id])
                            continue
                        text[row_id] = (
                            text[row_id][: letter_id + 1]
                            + "\n"
                            + text[row_id][letter_id + 1 :]
                        )
                        bold[row_id] = (
                            bold[row_id][: letter_id + 1]
                            + "\n"
                            + bold[row_id][letter_id + 1 :]
                        )
                        italics[row_id] = (
                            italics[row_id][: letter_id + 1]
                            + "\n"
                            + italics[row_id][letter_id + 1 :]
                        )
                elif text[row_id][letter_id] == "[":
                    num_unclosed_brackets += 1
            elif (
                text[row_id][letter_id] == "["
                and letter_id + 1 < len(text[row_id])
                and italics[row_id][letter_id + 1] == "1"
            ):
                # annotation detected
                num_unclosed_brackets = 1
                if letter_id - 1 >= 0 and text[row_id][letter_id - 1] != "\n":
                    # split to newline
                    text[row_id] = (
                        text[row_id][:letter_id] + "\n" + text[row_id][letter_id:]
                    )
                    bold[row_id] = (
                        bold[row_id][:letter_id] + "\n" + bold[row_id][letter_id:]
                    )
                    italics[row_id] = (
                        italics[row_id][:letter_id] + "\n" + italics[row_id][letter_id:]
                    )
                    letter_id += 1
            letter_id += 1
        row_id += 1
    text = [x.strip() + "\n" for x in ("".join(text)).split("\n") if x.strip()]
    bold = [x.strip() + "\n" for x in ("".join(bold)).split("\n") if x.strip()]
    italics = [x.strip() + "\n" for x in ("".join(italics)).split("\n") if x.strip()]
    return text, bold, italics


def format_attendance(text):
    # process attendance list
    replacement_dict = {
        "(johorbaru)": "(johorbahru)",
        "(kulimbandarbaharu)": "(kulim-bandarbaharu)",
        "(ipohtimur)": "(ipohtimor)",
        "bentong)": "(bentong)",  # dr_2022-12-20.pdf
        "sembrong)": "(sembrong)",  # dr_2022-12-20.pdf
        "(serian": "(serian)",  # dr_2022-03-08.pdf
    }
    text = text.lower()

    # detect list items that start with number.
    list_item_pattern = re.compile(r"^\d+\.\s+.*$", re.MULTILINE)

    # split the text into lines to process each individually
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # dict of headings -> list items
    parsed_data = {}
    current_heading = None
    for line in lines:
        if not list_item_pattern.match(line) and line.endswith(":"):
            current_heading = line
            parsed_data[current_heading] = ""
        elif current_heading is not None:
            parsed_data[current_heading] += line

    # segragate headings for attendance and absence
    attended_text = ""
    absent_text = ""
    for key in parsed_data.keys():
        if "tidak" in key or "digantung" in key:
            print("absent", key)
            absent_text += "".join(parsed_data[key].split())
        else:
            print("attendance", key)
            attended_text += "".join(parsed_data[key].split())

    for old, new in replacement_dict.items():
        absent_text = absent_text.replace(old, new)
        attended_text = attended_text.replace(old, new)

    assert absent_text, "No absentees found in attendance list"
    assert attended_text, "No attendance found in attendance list"

    return absent_text, attended_text


def tabulate(hansard_date, house):
    print(hansard_date)
    with open("categories.json", "r") as f:
        categories = json.load(f)
    year = hansard_date[-4:]
    dir_path = f"tabulated/{house}/"
    if not os.path.isdir(dir_path):
        os.makedirs(dir_path, exist_ok=True)
    sortable_date = (
        f"{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}"  # YYYY-MM-DD
    )
    dir_path += f"{sortable_date}/"
    if not os.path.isdir(dir_path):
        os.makedirs(dir_path, exist_ok=True)

    # sometimes the level_2 in a Hansard is a level_1 in some other Hansards' TOC
    # this is a fundamentally unresolvable problem because we cannot detect the presence of underlines
    # we simply edit the TOC for Hansards with known problems
    if hansard_date == "20012022":
        categories = [
            "PEMASYHURAN DARIPADA TUAN YANG DI-PERTUA",
            "USUL",
            "PENERANGAN DARIPADA MENTERI-MENTERI DI BAWAH P.M 14(1)(i)",
        ]

    # the strategy is to iterate across rows
    # store the contents of the preprocessed text file in a list
    input_dir = f"pretabulation/{house}/{year}/{sortable_date}/"
    with open(f"{input_dir}plaintext.txt", "r") as f:
        text = f.readlines()
    with open(f"{input_dir}bold.txt", "r") as f:
        bold = f.readlines()
    with open(f"{input_dir}italics.txt", "r") as f:
        italics = f.readlines()
    assert (
        len(text) == len(bold) == len(italics)
    ), f"Length of text, bold and italics do not match: {len(text)} vs {len(bold)} vs {len(italics)}"

    with open(f"parsed_pdf/{house}/{year}/{sortable_date}/categories.json", "r") as f:
        categories = json.load(f)

    fuzzy_ydp = [
        "PEMASYHURAN OLEH TUAN YANG DI-PERTUA",
        "PEMASYHURAN TUAN YANG DI-PERTUA",
        "PEMASYHURAN DARIPADA TUAN YANG DI-PERTUA",
    ]
    fuzzy_jawapan = [
        "JAWAPAN-JAWAPAN MENTERI BAGI PERTANYAAN-PERTANYAAN",
        "JAWAPAN-JAWAPAN LISAN BAGI PERTANYAAN-PERTANYAAN",
        "PERTANYAAN-PERTANYAAN BAGI JAWAB LISAN",
    ]

    # PEMASYHURAN OLEH TUAN YANG DI-PERTUA is very fuzzy and the match score is low
    if any("TUAN YANG DI-PERTUA" in x for x in categories):
        categories += fuzzy_ydp
    # YDPA has a longer title than TOC
    if "TITAH SERI PADUKA BAGINDA YANG DI-PERTUAN AGONG" in categories:
        categories.append(
            "TITAH KEBAWAH DULI YANG MAHA MULIA SERI PADUKA BAGINDA YANG DI-PERTUAN AGONG XVI AL-SULTAN ABDULLAH "
            "RI’AYATUDDIN AL-MUSTAFA BILLAH SHAH IBNI ALMARHUM SULTAN HAJI AHMAD SHAH AL-MUSTA’IN BILLAH"
        )
    # P.M. is sometimes expanded as Peraturan Mesyuarat
    for x in categories:
        if "P.M" in x:
            categories.append(x.replace("P.M", "PERATURAN MESYUARAT"))
    # Sometimes UNDANG sometimes UNDANG-UNDANG
    to_add = []
    for x in categories:
        # Replace "UNDANG" with "UNDANG-UNDANG" only when "UNDANG" is a standalone word
        if re.search(r"\b(?<!UNDANG-)UNDANG(?!-UNDANG)\b", x) and not re.search(
            r"\bUNDANG-UNDANG\b", x
        ):
            to_add.append(
                re.sub(r"\b(?<!UNDANG-)UNDANG(?!-UNDANG)\b", "UNDANG-UNDANG", x)
            )

        # Replace "UNDANG-UNDANG" with "UNDANG" only when "UNDANG-UNDANG" is a standalone word
        if re.search(r"\bUNDANG-UNDANG\b", x) and not re.search(
            r"\b(?<!UNDANG-)UNDANG(?!-UNDANG)\b", x
        ):
            to_add.append(re.sub(r"\bUNDANG-UNDANG\b", "UNDANG", x))
    categories += to_add
    to_add = []
    for x in categories:
        # Replace "UNDANG" with "UNDANG-UNDANG" only when "UNDANG" is a standalone word
        if re.search(r"\b(?<!USUL-)USUL(?!-USUL)\b", x) and not re.search(
            r"\bUSUL-USUL\b", x
        ):
            to_add.append(re.sub(r"\b(?<!USUL-)USUL(?!-USUL)\b", "USUL-USUL", x))

        # Replace "UNDANG-UNDANG" with "UNDANG" only when "UNDANG-UNDANG" is a standalone word
        if re.search(r"\bUSUL-USUL\b", x) and not re.search(
            r"\b(?<!USUL-)USUL(?!-USUL)\b", x
        ):
            to_add.append(re.sub(r"\bUSUL-USUL\b", "USUL", x))

    categories += to_add
    to_add = []
    # 2018 and earlier TOC will say JAWAPAN and in-text will say PERTANYAAN-PERTANYAAN BAGI JAWAB LISAN
    if any(x.startswith("JAWAPAN-JAWAPAN") for x in categories) or any(
        x.startswith("PERTANYAAN-PERTANYAAN") for x in categories
    ):
        categories += fuzzy_jawapan

    text, bold, italics = put_annotations_on_new_line(text, bold, italics)

    doa_seen = False
    num_rows = len(text)
    speeches = []
    blank_speech = {
        "author": "",
        "speech": "",
        "speech_bold": "",
        "speech_italics": "",
        "timestamp": "",
        "level_1": "",
        "level_2": "",
        "level_3": "",
    }
    current = blank_speech
    row_id = -1
    dewan_tangguh = False
    while row_id + 1 < num_rows:
        row_id += 1
        # if row_id == 979:
        #     print(1)
        #     pass

        # run until DOA first
        if "DOA" == text[row_id].strip():
            doa_seen = True
            continue
        if not doa_seen:
            # ignore rows before DOA except for the starting time
            if "Mesyuarat dimulakan" in text[row_id]:
                current["timestamp"] = text[row_id].split("pukul")[-1].strip()
            continue

        # determine whether the current line is a continuation of speech
        # first check whether it is an annotation
        if text[row_id].startswith("[") and italics[row_id][1] == "1":
            if text[row_id].startswith("[Dewan ditangguhkan") or text[
                row_id
            ].startswith("[Mesyuarat ditangguhkan"):
                dewan_tangguh = True
            # annotation detected
            speeches += insert_speech(current)
            old_author = current["author"]
            current["speech"] = text[row_id]
            current["speech_bold"] = bold[row_id]
            current["speech_italics"] = italics[row_id]
            current["author"] = "ANNOTATION"
            add_idx = 1
            num_unclosed_brackets = text[row_id].count("[") - text[row_id].count("]")
            # keep on looping until we tally up the correct number of brackets
            while add_idx + row_id < num_rows and num_unclosed_brackets > 0:
                if (
                    len(text[row_id + add_idx].strip()) > 5
                    and prop_of_1_among_binary(italics[row_id + add_idx]) == 0
                    and hansard_date != "26032018"
                ):
                    # most likely the annotation is missing a ]
                    # we will assume that the annotation is closed
                    # turn off autoclosing for 26032018 where a whole chunk of annotation is not italicized
                    with open("dump/autoclosed_annotation.txt", "a") as f:
                        f.write(f"{hansard_date}\n")
                        f.write(f'{current["speech"]}\n')
                        f.write("AUTOCLOSED AS IT IS FOLLOWED BY\n")
                        f.write(f"{text[row_id + add_idx]}")
                        f.write(f"{bold[row_id + add_idx]}")
                        f.write(f"{italics[row_id + add_idx]}")
                        f.write("\n")
                    break
                current["speech"] += text[row_id + add_idx]
                current["speech_bold"] += bold[row_id + add_idx]
                current["speech_italics"] += italics[row_id + add_idx]
                num_unclosed_brackets += text[row_id + add_idx].count("[") - text[
                    row_id + add_idx
                ].count("]")
                if text[row_id + add_idx].startswith("[Dewan ditangguhkan") or text[
                    row_id + add_idx
                ].startswith("[Mesyuarat ditangguhkan"):
                    dewan_tangguh = True
                add_idx += 1
            row_id += add_idx - 1
            speeches += insert_speech(current)
            current["author"] = old_author
            current["speech"] = ""
            current["speech_bold"] = ""
            current["speech_italics"] = ""
            continue
        # now check if it is author or title etc
        if "1" not in bold[row_id]:
            # if there is no bold in a line
            # then most likely it is a continuation of speech
            current["speech"] += text[row_id]
            current["speech_bold"] += bold[row_id]
            current["speech_italics"] += italics[row_id]
            continue
        else:
            if text[row_id].strip().lower() == "lampiran":
                # end of Hansard
                if not dewan_tangguh:
                    print(f"Lampiran found without dewan tangguh: {text[row_id]}")
                break

            # either timestamp, new category, new author or the like
            if is_timestamp(text[row_id]):
                # timestamp
                speeches += insert_speech(current)
                current["speech"] = ""
                current["speech_bold"] = ""
                current["speech_italics"] = ""
                current["timestamp"] = text[row_id].strip()
                continue

            (
                author,
                speech,
                speech_bold,
                speech_italics,
                subtopic,
            ) = get_author_and_speech(text[row_id], bold[row_id], italics[row_id])
            if author != "":
                speeches += insert_speech(current)
                current["author"] = author
                assert speech[-1] == "\n", f"Speech does not end with newline: {speech}"
                current["speech"] = speech
                current["speech_bold"] = speech_bold
                current["speech_italics"] = speech_italics
                if subtopic:
                    current["level_2"] = subtopic
                    current["level_3"] = ""
                continue

            # sometimes the author has too long name and overflow to second line
            # but make sure this is not an annotation
            if row_id + 1 < num_rows and not (
                text[row_id + 1].startswith("[") and italics[row_id + 1][1] == "1"
            ):
                concat_rows = f"{text[row_id].strip()} {text[row_id + 1]}"
                concat_rows_bold = f"{bold[row_id].strip()} {bold[row_id + 1]}"
                concat_rows_italics = f"{italics[row_id].strip()} {italics[row_id + 1]}"
                (
                    author,
                    speech,
                    speech_bold,
                    speech_italics,
                    subtopic,
                ) = get_author_and_speech(
                    concat_rows, concat_rows_bold, concat_rows_italics
                )
                if author != "":
                    speeches += insert_speech(current)
                    current["author"] = author
                    current["speech"] = speech
                    current["speech_bold"] = speech_bold
                    current["speech_italics"] = speech_italics
                    if subtopic:
                        current["level_2"] = subtopic
                        current["level_3"] = ""
                    # add to the loop counter additionally
                    row_id += 1
                    continue

            if bold[row_id].count("1") < 4:
                # most likely it is just a stray bold
                num_bold = bold[row_id].count("1")
                current["speech"] += text[row_id]
                current["speech_bold"] += bold[row_id]
                current["speech_italics"] += italics[row_id]
                with open("warnings/stray_bolds.txt", "a") as f:
                    f.write(
                        f"{hansard_date} with num bold: {num_bold}\n{text[row_id]}{bold[row_id]}\n"
                    )
                continue

            if (
                current["author"] == ""
                and current["speech"] == ""
                and current["level_1"] != ""
                and current["level_2"] == ""
                and prop_of_1_among_binary(italics[row_id]) < 0.9
            ):
                # most likely a level_2 immediately following a level_1
                # usually a chain of bolds
                # make sure it is not the chain of italicised bolds typically following Titah
                add_idx = 1
                current["level_2"] = text[row_id]
                current["level_3"] = ""
                while (
                    row_id + add_idx < num_rows
                    and prop_of_1_among_binary(bold[row_id + add_idx]) > 0.8
                    and not is_timestamp(text[row_id + add_idx])
                    and not possible_author(
                        text, bold, italics, row_id + add_idx, num_rows
                    )
                    and not (
                        text[row_id + add_idx].startswith("[")
                        and italics[row_id + add_idx][1] == "1"
                    )
                ):
                    current["level_2"] += text[row_id + add_idx]
                    add_idx += 1
                row_id += add_idx - 1
                with open("warnings/level_2_following_level_1.txt", "a") as f:
                    f.write(f"{hansard_date}\n{current['level_2']}\n")
                continue

            if prop_of_1_among_binary(bold[row_id]) < 0.9:
                # categories shouldn't have mixed unbolds
                # treat them as stray bolds
                current["speech"] += text[row_id]
                current["speech_bold"] += bold[row_id]
                current["speech_italics"] += italics[row_id]
                with open("warnings/mixed_bolds.txt", "a") as f:
                    f.write(f"{hansard_date}\n{text[row_id]}{bold[row_id]}\n")
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
                # if text[row_id].strip() in categories:
                #     # direct match
                #     speeches += insert_speech(current)
                #     current['author'] = ""
                #     current['level_1'] = text[row_id].strip()
                #     current['level_2'] = ""
                #     current['level_3'] = ""
                #     current['speech'] = ""
                #     current['speech_bold'] = ""
                #     current['speech_italics'] = ""
                # keep elongating the category scope and try fuzzy matching until the category score goes down
                add_idx = 1
                current_category = text[row_id].strip()
                current_category_probability = category_probability(
                    current_category, categories
                )
                while (
                    row_id + add_idx < num_rows
                    and upper_lower_ratio(text[row_id + add_idx]) > 1
                    and category_probability(
                        current_category + " " + text[row_id + add_idx].strip(),
                        categories,
                    )
                    >= current_category_probability
                ):
                    current_category += " " + text[row_id + add_idx].strip()
                    current_category_probability = category_probability(
                        current_category, categories
                    )
                    add_idx += 1
                if current_category_probability > 0.9:
                    speeches += insert_speech(current)
                    current["author"] = ""
                    current["level_1"] = current_category
                    current["level_2"] = ""
                    current["level_3"] = ""
                    current["speech"] = ""
                    current["speech_bold"] = ""
                    current["speech_italics"] = ""
                    row_id += add_idx - 1
                    if current_category_probability < 1:
                        with open("warnings/matched_categories.csv", "a") as f:
                            f.write(
                                f"{hansard_date},{current_category},{current_category_probability}\n"
                            )
                    continue
                # could be a capitalised subtopic
                speeches += insert_speech(current)
                current["author"] = ""
                current["speech"] = ""
                current["speech_bold"] = ""
                current["speech_italics"] = ""
                current["level_3"] = ""
                add_idx = 1
                current["level_2"] = text[row_id]
                # allow empty lines as separator
                while (
                    row_id + add_idx < num_rows
                    and prop_of_1_among_binary(bold[row_id + add_idx]) > 0.8
                    and not is_timestamp(text[row_id + add_idx])
                    and get_author_and_speech(
                        text[row_id + add_idx],
                        bold[row_id + add_idx],
                        italics[row_id + add_idx],
                    )[0]
                    == ""
                    and not text[row_id + add_idx].startswith("Bismilla")
                    and (
                        row_id + add_idx + 1 >= num_rows
                        or get_author_and_speech(
                            f"{text[row_id + add_idx].strip()} {text[row_id + add_idx + 1]}",
                            f"{bold[row_id + add_idx].strip()} {bold[row_id + add_idx + 1]}",
                            f"{italics[row_id + add_idx].strip()} {italics[row_id + add_idx + 1]}",
                        )[0]
                        == ""
                    )
                ):
                    current["level_2"] += text[row_id + add_idx]
                    add_idx += 1
                row_id += add_idx - 1
                with open("warnings/capitalised_level_2.txt", "a") as f:
                    f.write(f"{hansard_date}\n{current['level_2']}\n")
                continue

            # these are lower-cased bold sentences
            # most likely a level_3 subtopic
            if re.search(
                r"Yang (Tidak )?((Bersetuju)|(Hadir)|(Mengundi)):", text[row_id]
            ) or re.search(r"^Bacaan Kali Yang", text[row_id]):
                speeches += insert_speech(current)
                current["author"] = ""
                current["speech"] = ""
                current["speech_bold"] = ""
                current["speech_italics"] = ""
                current["level_3"] = text[row_id].strip()
                if current["level_2"] == "":
                    print(
                        f"WARN: level_2 not taken but inserting level_3: {text[row_id]}"
                    )
                continue
            elif re.search(
                r"^(Maksud)|(Kepala)|(Fasal)|(Bab)|(Tajuk)|(Jadual)[A-Za-z0-9-[\], ]+[–-]",
                text[row_id],
            ):
                speeches += insert_speech(current)
                add_idx = 1
                current["author"] = ""
                current["speech"] = ""
                current["speech_bold"] = ""
                current["speech_italics"] = ""
                current["level_3"] = text[row_id]
                # it could be followed by similar level_3 markers
                while (
                    row_id + add_idx < num_rows
                    and prop_of_1_among_binary(bold[row_id + add_idx]) > 0.8
                    and (
                        re.search(
                            r"^(Maksud)|(Kepala)|(Fasal)|(Bab)|(Tajuk)|(Jadual)[A-Za-z0-9-[\], ]+[–-]",
                            text[row_id + add_idx],
                        )
                        or text[row_id + add_idx].strip()[-1] in ["–", "-"]
                    )
                ):
                    current["level_3"] += text[row_id + add_idx]
                    add_idx += 1
                row_id += add_idx - 1
                if current["level_2"] == "":
                    print(
                        f"WARN: level_2 not taken but inserting level_3: {text[row_id]}"
                    )
                continue

            # special cases
            if re.fullmatch(
                r"Perutusan [Dd]aripada Dewan Negara [kK]epada Dewan Rakyat",
                text[row_id].strip(),
            ) or re.search(
                r'^[“"]?((Bahawa)|(BAHAWA)|(DAN BAHAWA)|(Dengan ini)|(DENGAN INI))',
                text[row_id],
            ):
                # treat as continuation of speech
                current["speech"] += text[row_id]
                current["speech_bold"] += bold[row_id]
                current["speech_italics"] += italics[row_id]
                continue
            elif hansard_date == "02112018" and (
                re.search(r"^Strategi \d+:", text[row_id])
                or re.search(r" [–-]$", text[row_id].strip())
            ):
                # during the budget 02112018
                speeches += insert_speech(current)
                current["author"] = ""
                current["speech"] = ""
                current["speech_bold"] = ""
                current["speech_italics"] = ""
                current["level_3"] = text[row_id].strip()
                continue
            # unhandled case
            print(f"WARN IN-TEXT BOLD:\n{text[row_id]}{bold[row_id]}{italics[row_id]}")
            with open("warnings/in-text-bold.txt", "a") as f:
                f.write(
                    f"{hansard_date}\n{text[row_id]}{bold[row_id]}{italics[row_id]}\n"
                )
            current["speech"] += text[row_id]
            current["speech_bold"] += bold[row_id]
            current["speech_italics"] += italics[row_id]

    speeches += insert_speech(current)

    # remove trailing newlines
    for idx in range(len(speeches)):
        for idx2 in range(len(current)):
            speeches[idx][idx2] = speeches[idx][idx2].strip()

    # add in formatting for bold and italics
    for idx in range(len(speeches)):
        if speeches[idx][4] != "ANNOTATION":
            speeches[idx][5] = add_formatting(
                speeches[idx][5], speeches[idx][6], speeches[idx][7]
            )
        speeches[idx] = speeches[idx][:-2]

    # extract timestamps from annotations
    row_id = -1
    while row_id + 1 < len(speeches):
        row_id += 1
        if speeches[row_id][4] != "ANNOTATION":
            continue
        # the 5th item is the speech
        if has_timestamp_in_annotation(speeches[row_id][5]):
            old_timestamp = speeches[row_id][3]
            new_timestamp = get_timestamp_from_annotation(speeches[row_id][5])
            add_idx = 0
            while (
                row_id + add_idx < len(speeches)
                and speeches[row_id + add_idx][3] == old_timestamp
            ):
                speeches[row_id + add_idx][3] = new_timestamp
                add_idx += 1

    # get unique timestamps while preserving order
    # unique_timestamps = dict.fromkeys([speech[3] for speech in speeches]).keys()
    # with open('dump/all_timestamps.txt', 'a') as f:
    #     for timestamp in unique_timestamps:
    #         f.write(f'{timestamp}\n')
    # with open('dump/all_timestamps_dated.txt', 'a') as f:
    #     f.write(f'\n{hansard_date}\n')
    #     for timestamp in unique_timestamps:
    #         f.write(f'{timestamp}\n')
    # prop_bullet = sum([1 for timestamp in unique_timestamps if re.search(r'[■◼▪]', timestamp)]) / len(
    #     unique_timestamps)
    # standardised_unique_timestamps = [standardise_timestamp(timestamp) for timestamp in unique_timestamps]
    # if len(unique_timestamps) != len(set(standardised_unique_timestamps)):
    #     print(f'WARN: duplicate timestamps detected as different formats: {hansard_date}')
    # print(f'Prop of bullet timestamps: {prop_bullet}')

    old_timestamp_list = [speech[3] for speech in speeches]
    # standardise timestamps into 24 hour format
    for row_id in range(len(speeches)):
        # insert standardised timestamp after old timestamp
        speeches[row_id].insert(4, standardise_timestamp(speeches[row_id][3]))

    # post-tabulation warnings
    # check if annotation is too long, usually missing ].
    # if without error it is usually [Diputuskan,
    for speech in speeches:
        if speech[5] == "ANNOTATION" and speech[6].count("\n") > 5:
            with open("warnings/annotation_too_long.txt", "a") as f:
                f.write(f"{hansard_date}\n{speech[6]}\n\n")

    # check for uppercased misidentified non-authors
    for speech in speeches:
        if speech[5] != "ANNOTATION" and upper_lower_ratio(speech[5]) > 0.8:
            with open("warnings/uppercased_non_author.txt", "a") as f:
                f.write(f"{hansard_date}\n{speech[4]}\n\n")

    # check that timestamps are in order
    timestamps = [speech[4] for speech in speeches]
    unique_timestamps = set(timestamps)
    unique_timestamps_row = []
    for speech in speeches:
        if speech[4] not in unique_timestamps:
            unique_timestamps.add(speech[4])
            unique_timestamps_row.append(speech)

    for idx in range(len(unique_timestamps_row) - 1):
        # check if two strings in 24 hour format is within 30 minutes of each other
        if more_than_30_minutes_past(
            unique_timestamps_row[idx][4], unique_timestamps_row[idx + 1][4]
        ):
            with open("warnings/unsorted_timestamps.txt", "a") as f:
                f.write(
                    f"{hansard_date}\n{unique_timestamps_row[idx][3]} AND {unique_timestamps_row[idx][4]}\n"
                )
                f.write(
                    f"{unique_timestamps_row[idx + 1][3]} AND {unique_timestamps_row[idx + 1][4]}\n\n"
                )

    # export speeches to csv
    with open(f"{dir_path}result.csv", mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "level_1",
                "level_2",
                "level_3",
                "raw_timestamp",
                "timestamp",
                "author",
                "speech",
            ]
        )
        writer.writerows(speeches)

    # check if TOC matches
    actual_toc = sorted(list(set([x[0] for x in speeches])))
    categories = [
        x
        for x in categories
        if x not in ["KANDUNGAN (Samb)", "K A N D U N G A N (Samb.)"]
    ]
    actual_toc = [x for x in actual_toc if x not in [""]]
    actual_toc_original = actual_toc.copy()
    categories_original = categories.copy()

    # if both have usuls, then it is fine to take their variants
    if any(x.startswith("USUL") for x in categories) and any(
        x.startswith("USUL") for x in actual_toc
    ):
        categories = [x for x in categories if not x.startswith("USUL")]
        actual_toc = [x for x in actual_toc if not x.startswith("USUL")]

    if any(x.startswith("TITAH") for x in categories) and any(
        x.startswith("TITAH") for x in actual_toc
    ):
        categories = [x for x in categories if not x.startswith("TITAH")]
        actual_toc = [x for x in actual_toc if not x.startswith("TITAH")]

    if any(x.endswith("YANG DI-PERTUA") for x in categories) and any(
        x.endswith("YANG DI-PERTUA") for x in actual_toc
    ):
        categories = [x for x in categories if not x.endswith("YANG DI-PERTUA")]
        actual_toc = [x for x in actual_toc if not x.endswith("YANG DI-PERTUA")]

    if any(x in fuzzy_jawapan for x in categories) and any(
        x in fuzzy_jawapan for x in actual_toc
    ):
        categories = [x for x in categories if x not in fuzzy_jawapan]
        actual_toc = [x for x in actual_toc if x not in fuzzy_jawapan]

    if any(x.startswith("RANG UNDANG") for x in categories) and any(
        x.startswith("RANG UNDANG") for x in actual_toc
    ):
        categories = [x for x in categories if not x.startswith("RANG UNDANG")]
        actual_toc = [x for x in actual_toc if not x.startswith("RANG UNDANG")]

    if any("P.M" in x or "PERATURAN MESYUARAT" in x for x in categories) and any(
        "P.M" in x or "PERATURAN MESYUARAT" in x for x in actual_toc
    ):
        categories = [
            x for x in categories if not ("P.M" in x or "PERATURAN MESYUARAT" in x)
        ]
        actual_toc = [
            x for x in actual_toc if not ("P.M" in x or "PERATURAN MESYUARAT" in x)
        ]

    if actual_toc != categories:
        # get the categories but only their alphabets and numbers (e.g. remove spaces, punctuation etc)
        alphanumeric_categories = sorted(
            [re.sub(r"[^a-zA-Z0-9]", "", x) for x in categories]
        )
        alphanumeric_actual = sorted(
            [re.sub(r"[^a-zA-Z0-9]", "", x) for x in actual_toc]
        )
        if alphanumeric_categories != alphanumeric_actual:
            with open("warnings/toc_mismatch.txt", "a") as f:
                category_minus_actual = "\n".join(
                    [
                        x
                        for x in categories
                        if re.sub(r"[^a-zA-Z0-9]", "", x) not in alphanumeric_actual
                    ]
                )
                actual_minus_category = "\n".join(
                    [
                        x
                        for x in actual_toc
                        if re.sub(r"[^a-zA-Z0-9]", "", x) not in alphanumeric_categories
                    ]
                )
                category_string = "\n".join(categories_original)
                actual_toc_string = "\n".join(actual_toc_original)
                f.write(
                    f"{hansard_date}\nLength differences: {len(categories) - len(actual_toc)}\n"
                    f"actual_minus_category\n{actual_minus_category}\n\n"
                    f"category_minus_actual\n{category_minus_actual}\n\n"
                    f"Actual TOC\n{actual_toc_string}\n\n"
                    f"Expected TOC\n{category_string}\n\n"
                )

    # process attendance from parse_pdf
    parsed_input_dir = f"parsed_pdf/{house}/{year}/{sortable_date}/"
    with open(f"{parsed_input_dir}attendance.txt", "r") as f:
        attendance_txt = f.read()

    absent_text, attended_text = format_attendance(attendance_txt)

    with open(f"{dir_path}absent.txt", "w") as f:
        f.write(absent_text)
    with open(f"{dir_path}attended.txt", "w") as f:
        f.write(attended_text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "hansard_date", help="hansard_date eg. 23052023", default="02082017", nargs="?"
    )
    parser.add_argument(
        "house",
        help="parliament house. Possible values: 'dr' or 'dn'",
        choices=["dr", "dn"],
    )
    # Parse arguments
    args = parser.parse_args()
    tabulate(args.hansard_date, args.house)
