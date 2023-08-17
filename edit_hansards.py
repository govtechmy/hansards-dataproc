"""Directly edit specific Hansards to ease tabulation
"""


def replace(hansard_date, old_text_snippet, new_text_snippet, new_bold_snippet, new_italics_snippet):
    assert len(new_text_snippet) == len(new_bold_snippet) == len(new_italics_snippet), \
        f"new_text_snippet ({new_text_snippet}), new_bold_snippet ({new_bold_snippet}), " \
        f"and new_italics_snippet ({new_italics_snippet}) must be of the same length"
    assert len(new_text_snippet.replace(' ', '')) == len(new_bold_snippet.replace(' ', '')) == len(
        new_italics_snippet.replace(' ', '')), \
        f"Without spaces, new_text_snippet ({new_text_snippet.replace(' ', '')}), " \
        f"new_bold_snippet ({new_bold_snippet.replace(' ', '')}), " \
        f"and new_italics_snippet ({new_italics_snippet.replace(' ', '')}) must be of the same length"
    year = hansard_date[-4:]
    sortable_date = f'{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}'  # YYYY-MM-DD
    dir_path = f"parsed_pdf/{year}/{sortable_date}/"
    with open(dir_path + 'plaintext.txt', 'r') as f:
        text = f.readlines()
    with open(dir_path + 'bold.txt', 'r') as f:
        bold = f.readlines()
    with open(dir_path + 'italics.txt', 'r') as f:
        italics = f.readlines()
    num_edits = 0
    for idx in range(len(text)):
        if old_text_snippet in text[idx].replace('  ', ' ').strip():
            # get the starting index where the match begins
            start_idx = text[idx].index(old_text_snippet)
            text[idx] = text[idx][:start_idx] + new_text_snippet + text[idx][start_idx + len(old_text_snippet):]
            bold[idx] = bold[idx][:start_idx] + new_bold_snippet + bold[idx][start_idx + len(old_text_snippet):]
            italics[idx] = italics[idx][:start_idx] + new_italics_snippet + \
                           italics[idx][start_idx + len(old_text_snippet):]
            num_edits += 1

    with open(dir_path + 'plaintext.txt', 'w') as f:
        f.writelines(text)
    with open(dir_path + 'bold.txt', 'w') as f:
        f.writelines(bold)
    with open(dir_path + 'italics.txt', 'w') as f:
        f.writelines(italics)
    print(f"{hansard_date} Num changes made: {num_edits}")


if __name__ == "__main__":
    replace("12112019",
            "DR 12.11.201 ",
            "DR 12.11.2019 ",
            "00 0000000000 ",
            "00 0000000000 ")
    replace("20072022",
            "Tuan Pengerusi [Dato’ Ramli bin Dato’ Mohd Nor [Cameron Highlands)]:",
            "Tuan Pengerusi [Dato’ Ramli bin Dato’ Mohd Nor (Cameron Highlands)]:",
            "1111 111111111 111111 11111 111 11111 1111 111 11111111 111111111111",
            "0000 000000000 000000 00000 000 00000 0000 000 00000000 000000000000")
    replace("16082018",
            "Tuan Noor Amin bin Ahmad [Kangar] Tuan Noor Amin bin Ahmad [Kangar]:",
            "Tuan Noor Amin bin Ahmad [Kangar]:",
            "1111 1111 1111 111 11111 111111111",
            "0000 0000 0000 000 00000 000000000")
    replace("19112018",
            "Tuan Ahmad Fahmi bin Mohamed Fadzil [Lembah Pantai] Ya.",
            "Tuan Ahmad Fahmi bin Mohamed Fadzil [Lembah Pantai]: Ya.",
            "1111 11111 11111 111 1111111 111111 1111111 11111111 000",
            "0000 00000 00000 000 0000000 000000 0000000 00000000 000")
    replace("06082018",
            "Dato’ Dr. Noor Azmi bin Ghazali [Bagan Serai Ok.",
            "Dato’ Dr. Noor Azmi bin Ghazali [Bagan Serai]: Ok.",
            "11111 111 1111 1111 111 1111111 111111 1111111 000",
            "00000 000 0000 0000 000 0000000 000000 0000000 000")
    replace("16072019",
            "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa[ [Ketereh]: Yang",
            "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa [Ketereh]: Yang",
            "111 111 11111 1111 11111111 1111 111111 111 1111 1111 1111111111 0000",
            "000 000 00000 0000 00000000 0000 000000 000 0000 0000 0000000000 0000")
    replace("16072020",
            "Khairuddin bin Aman Razali] Terima kasih Tuan yang di-Pertua. Terima kasih Yang",
            "Khairuddin bin Aman Razali]: Terima kasih Tuan yang di-Pertua. Terima kasih Yang",
            "1111111111 111 1111 11111111 000000 00000 0000 0000 0000000000 000000 00000 0000",
            "0000000000 000 0000 00000000 000000 00000 0000 0000 0000000000 000000 00000 0000")
