import pdfplumber
import generate_tabular


def get_speakers_from_toc(hansard_date):
    year = hansard_date[-4:]
    with pdfplumber.open('src_hansard/downloads/' + year + '/DR-' + hansard_date + '.pdf') as pdf:
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
    segments = generate_tabular.parse_markup(all_text)
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

    assert "ahli-ahli yang hadir" in sections or "ahli-ahli yang tidak hadir" in sections
    if not ("senator yang hadir sama" in sections or "senator yang tidak hadir" in sections):
        print("WARN: No senators present")

    # print(sections)

    attendance = []
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