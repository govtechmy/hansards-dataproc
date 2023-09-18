import pandas as pd
import pdfplumber
from markup_parser import parse_markup
import re
from titles import titles as titles


def remove_titles(speaker):
    speaker = speaker.strip()
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
    last_comma_index = speaker.rfind(',')
    if last_comma_index != -1:
        # the speaker has a role
        role = speaker[:last_comma_index].strip()
        speaker = speaker[last_comma_index+1:].strip()
        role = role.replace('Tuan Yang di-Pertua', 'Yang di-Pertua')
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


def get_speakers_from_toc(hansard_date):
    year = hansard_date[-4:]
    with pdfplumber.open('src_hansard/downloads/' + year + '/DN-' + hansard_date + '.pdf') as pdf:
        total_page_num = len(pdf.pages)
    started = False
    all_text = ''
    for idx in range(total_page_num):
        with open("preprocessed_hansard/" + hansard_date + f"/{idx + 1}.txt", 'r') as f:
            cur_text = ''.join(f.readlines()[1:])
        if not started:
            if "KEHADIRAN AHLI-AHLI PARLIMEN" in cur_text:
                started = True
            else:
                continue
        else:
            if "DEWAN RAKYAT" in cur_text:
                break
        all_text += cur_text

    # remove italics
    all_text = all_text.replace('___', '')
    segments = parse_markup(all_text)
    # remove empty spaces
    segments = [x for x in segments if x[0].strip()]
    # remove titles
    while segments[0][0].isupper():
        segments.pop(0)
    # to prevent overspilling like: KEHADIRAN AHLI-AHLI PARLIMEN 1 MAC 2023 Ahli-Ahli Yang Hadir
    if "ahli-ahli yang hadir" in segments[0][0].lower():
        segments[0][0] = "ahli-ahli yang hadir"

    # each bold from now is a new section
    sections = {}
    prev_title = ""
    cur_list = []
    for segment in segments:
        if segment[1]:
            if prev_title:
                sections[prev_title] = cur_list
                cur_list = []
            prev_title = re.sub(r'[:\- ]+$', '', segment[0]).lstrip().lower()
        else:
            cur_list.append(segment[0])
    # add last item
    assert not segments[-1][1]
    sections[prev_title] = cur_list

    for title, content in sections.items():
        assert len(content) == 1
        sections[title] = get_speaker_list_from_string(content[0])

    everyone_came = False
    if "ahli-ahli yang hadir" not in sections and "ahli-ahli yang tidak hadir" not in sections:
        print("WARN: No attendance title like 'ahli-ahli yang hadir' or 'ahli-ahli yang tidak hadir'")
        # assuming everyone came like 2023-19-12
        everyone_came = True
    if not ("senator yang hadir sama" in sections or "senator yang tidak hadir" in sections):
        print("WARN: No senators present")

    # print(sections)

    attendance = []
    if everyone_came:
        for mp in sections[""]:
            row = analyse_speaker(mp)
            row.append(1)
            row.append("mp")
            attendance.append(row)
    if "ahli-ahli yang hadir" in sections:
        for mp in sections["ahli-ahli yang hadir"]:
            row = analyse_speaker(mp)
            row.append(1)
            row.append("mp")
            attendance.append(row)
    if "ahli-ahli yang tidak hadir" in sections:
        for mp in sections["ahli-ahli yang tidak hadir"]:
            row = analyse_speaker(mp)
            row.append(0)
            row.append("mp")
            attendance.append(row)
    # assert len(attendance) == 222
    if "senator yang hadir sama" in sections or "senator yang turut hadir" in sections:
        section_name = "senator yang hadir sama"
        if section_name not in sections:
            section_name = "senator yang turut hadir"
        for mp in sections[section_name]:
            row = analyse_speaker(mp)
            row.append(1)
            row.append("senator")
            attendance.append(row)
    if "senator yang tidak hadir" in sections:
        for mp in sections["senator yang tidak hadir"]:
            row = analyse_speaker(mp)
            row.append(0)
            row.append("senator")
            attendance.append(row)

    # corrections
    for row in attendance:
        if row[2] == "Kulim Bandar Baharu":
            row[2] = "Kulim-Bandar Baharu"

    df = pd.DataFrame(attendance, columns=['name', 'honour_title', 'seat_name', 'role', 'attendance', 'membership'])
    return df


if __name__ == "__main__":
    pass
