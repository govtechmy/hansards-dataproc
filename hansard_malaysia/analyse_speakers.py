import pandas as pd
import pdfplumber

import generate_tabular
import re

titles = [
    "YB Tuan",
    "YB",
    "YAB",
    "Senator",
    "Tan Sri",
    "Dato' Seri Utama",
    "Dato Seri Utama",
    "Dato' Sri",
    "Dato Sri",
    "Dato' Seri",
    "Dato Seri",
    "Dato' Wira",
    "Dato Wira",
    "Dato'",
    "Dato",
    "Datuk Seri Panglima",
    "Datuk Seri",
    "Datuk Wira",
    "Datuk",
    "Haji",
    "Ir",
    "Dr",
    "Puan",
    "Tun",
    "Hajah"
]


def remove_titles(speaker):
    removal_request = 1
    speaker = speaker.replace('’', "'")
    speaker = speaker.replace('.', "")
    speaker = speaker.strip()
    while removal_request:
        removal_request = 0
        for title in titles:
            if speaker.startswith(title):
                speaker = speaker[len(title):].strip()
                removal_request = 1
    return speaker.strip()


def remove_role(speaker):
    if "–" not in speaker:
        return speaker
    return speaker.split("–")[0].strip()


def get_role(speaker):
    if "–" not in speaker:
        return ""
    return speaker.split("–")[1].strip()


def analyse_speaker(speaker):
    role = ''
    constituency = ''
    if '-' in speaker:
        speaker, role = speaker.split('–')
    speaker = speaker.strip()
    if ')' == speaker[-1]:
        constituency = re.search("\([A-Za-z ]+\)$", speaker).group(0)
        speaker = speaker[:-len(constituency)].strip()
        constituency = constituency[1:-1]
    honor_title = speaker
    speaker = remove_titles(speaker)
    constituency = constituency.strip()
    if constituency == "Petrajaya":
        constituency = "Petra Jaya"
    return [speaker.strip(), honor_title.strip(), constituency.strip(), role.strip()]


def remove_constituency(speaker):
    # for TOC list
    speaker = re.sub("\([A-Za-z ]+\)$", '', speaker)
    # for in-text
    return re.sub("\[[A-Za-z’\'()\-\. ]+\]$", '', speaker).strip()


def get_raw_name(speaker):
    speaker = remove_role(speaker)
    speaker = remove_titles(speaker)
    speaker = remove_constituency(speaker)
    return speaker.strip()


def get_role_intext(speaker):
    # for in-text use
    # there are multiple forms
    # Timbalan Yang di-Pertua [Dato’ Mohd Rashid Hasnon]
    # Tuan Noor Amin bin Ahmad [Kangar]
    # Timbalan Menteri di Jabatan Perdana Menteri (Parlimen dan Undang- undang) [Datuk Wira Hajah Mas Ermieyati binti Samsudin]
    if speaker == "Tuan Yang di-Pertua":
        return speaker
    assert '[' in speaker
    segments = speaker.split('[')
    # remove ]
    segments[1] = segments[1][-1:]
    segments = [segment.strip() for segment in segments]
    if "Menteri" or "Yang di-Pertua" in segments[0]:
        return segments[0]
    else:
        return segments[1]


def get_speaker_list_from_string(speakers_string):
    return [x.strip() for x in re.compile("[0-9]+.").split(speakers_string) if x.strip()]


def get_speakers_from_toc(hansard_code):
    with pdfplumber.open('src_hansard/hansard_' + hansard_code + '.pdf') as pdf:
        total_page_num = len(pdf.pages)
    started = False
    all_text = ''
    for idx in range(total_page_num):
        with open("preprocessed_hansard/" + hansard_code + f"/{idx + 1}.txt", 'r') as f:
            cur_text = ''.join(f.readlines()[1:])
        if not started:
            if "SENARAI KEHADIRAN AHLI-AHLI PARLIMEN" in cur_text:
                started = True
            else:
                continue
        else:
            if "DEWAN RAKYAT" in cur_text:
                break
        all_text += cur_text

    segments = generate_tabular.parse_markup(all_text)
    # remove empty spaces
    segments = [x for x in segments if x[0].strip()]
    # remove titles
    while segments[0][0].isupper():
        segments.pop(0)

    # each bold from now is a new section
    sections = {}
    prev_title = ""
    cur_list = []
    for segment in segments:
        if segment[1]:
            if prev_title:
                sections[prev_title] = cur_list
                cur_list = []
            prev_title = re.sub(r'[:\- ]+$', '', segment[0]).lstrip()
        else:
            cur_list.append(segment[0])
    # add last item
    assert not segments[-1][1]
    sections[prev_title] = cur_list

    for title, content in sections.items():
        assert len(content) == 1
        sections[title] = get_speaker_list_from_string(content[0])

    assert "Ahli-Ahli Yang Hadir" in sections or "Ahli-Ahli Yang Tidak Hadir" in sections
    assert "Senator Yang Hadir Sama" in sections or "Senator Yang Tidak Hadir" in sections

    attendance = []
    if "Ahli-Ahli Yang Hadir" in sections:
        for mp in sections["Ahli-Ahli Yang Hadir"]:
            row = analyse_speaker(mp)
            row.append(1)
            row.append("MP")
            attendance.append(row)
    if "Ahli-Ahli Yang Tidak Hadir" in sections:
        for mp in sections["Ahli-Ahli Yang Tidak Hadir"]:
            row = analyse_speaker(mp)
            row.append(0)
            row.append("MP")
            attendance.append(row)
    # assert len(attendance) == 222
    if "Senator Yang Hadir Sama" in sections:
        for mp in sections["Senator Yang Hadir Sama"]:
            row = analyse_speaker(mp)
            row.append(1)
            row.append("Senator")
            attendance.append(row)
    if "Senator Yang Tidak Hadir" in sections:
        for mp in sections["Senator Yang Tidak Hadir"]:
            row = analyse_speaker(mp)
            row.append(0)
            row.append("Senator")
            attendance.append(row)

    # corrections
    for row in attendance:
        if row[1] == "Kulim Bandar Baharu":
            row[1] = "Kulim-Bandar Baharu"

    df = pd.DataFrame(attendance, columns=['name', 'honour_title', 'seat_name', 'role', 'attendance', 'membership'])
    return df


if __name__ == "__main__":
    hansard_code = "14-04-01-17"
    get_speakers_from_toc(hansard_code)
