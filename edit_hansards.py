"""Directly edit specific Hansards to ease tabulation
"""
import re


def replace(hansard_date, old_text_snippet, new_text_snippet, new_bold_snippet, new_italics_snippet):
    if new_bold_snippet == "all":
        new_bold_snippet = re.sub(r'\S', '1', new_text_snippet)
    if new_italics_snippet == "all":
        new_italics_snippet = re.sub(r'\S', '1', new_text_snippet)
    if new_bold_snippet == "none":
        new_bold_snippet = re.sub(r'\S', '0', new_text_snippet)
    if new_italics_snippet == "none":
        new_italics_snippet = re.sub(r'\S', '0', new_text_snippet)

    assert re.fullmatch(r'[\s01]*', new_bold_snippet), \
        f'new_bold_snippet ({new_bold_snippet}) must only contain 0s and 1s'
    assert re.fullmatch(r'[\s01]*', new_italics_snippet), \
        f'new_italics_snippet ({new_italics_snippet}) must only contain 0s and 1s'
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
    dir_path = f"pretabulation/{year}/{sortable_date}/"
    with open(dir_path + 'plaintext.txt', 'r') as f:
        text = f.readlines()
    with open(dir_path + 'bold.txt', 'r') as f:
        bold = f.readlines()
    with open(dir_path + 'italics.txt', 'r') as f:
        italics = f.readlines()
    num_edits = 0
    for idx in range(len(text)):
        if old_text_snippet == text[idx]:
            # get the starting index where the match begins
            text[idx] = new_text_snippet
            bold[idx] = new_bold_snippet
            italics[idx] = new_italics_snippet
            num_edits += 1

    with open(dir_path + 'plaintext.txt', 'w') as f:
        f.writelines(text)
    with open(dir_path + 'bold.txt', 'w') as f:
        f.writelines(bold)
    with open(dir_path + 'italics.txt', 'w') as f:
        f.writelines(italics)
    print(f"{hansard_date} Num changes made: {num_edits}")


def edit_hansards():
    replace("20072022",
            "Tuan Pengerusi [Dato’ Ramli bin Dato’ Mohd Nor [Cameron Highlands)]: Ada\n",
            "Tuan Pengerusi [Dato’ Ramli bin Dato’ Mohd Nor (Cameron Highlands)]: Ada\n",
            "1111 111111111 111111 11111 111 11111 1111 111 11111111 111111111111 000\n",
            "0000 000000000 000000 00000 000 00000 0000 000 00000000 000000000000 000\n")
    replace("16082018",
            "Tuan Noor Amin bin Ahmad [Kangar] Tuan Noor Amin bin Ahmad [Kangar]:\n",
            "Tuan Noor Amin bin Ahmad [Kangar]:\n",
            "1111 1111 1111 111 11111 111111111\n",
            "0000 0000 0000 000 00000 000000000\n")
    replace("06082018",
            "Dato’ Dr. Noor Azmi bin Ghazali [Bagan Serai Ok.\n",
            "Dato’ Dr. Noor Azmi bin Ghazali [Bagan Serai]: Ok.\n",
            "11111 111 1111 1111 111 1111111 111111 1111111 000\n",
            "00000 000 0000 0000 000 0000000 000000 0000000 000\n")
    replace("16072019",
            "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa[ [Ketereh]: Yang\n",
            "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa [Ketereh]: Yang\n",
            "111 111 11111 1111 11111111 1111 111111 111 1111 1111 1111111111 0000\n",
            "000 000 00000 0000 00000000 0000 000000 000 0000 0000 0000000000 0000\n")
    replace("15102018",
            "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa[ [Ketereh]: Terima kasih\n",
            "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa [Ketereh]: Terima kasih\n",
            "111 111 11111 1111 11111111 1111 111111 111 1111 1111 1111111111 000000 00000\n",
            "000 000 00000 0000 00000000 0000 000000 000 0000 0000 0000000000 000000 00000\n")
    replace('17112021',
            'Timbalan Menteri Sumber Manusia [Tuan Haji Awang bin Hashim:]\n',
            'Timbalan Menteri Sumber Manusia [Tuan Haji Awang bin Hashim]:\n',
            '11111111 1111111 111111 1111111 11111 1111 11111 111 11111111\n',
            '00000000 0000000 000000 0000000 00000 0000 00000 000 00000000\n')
    replace('04082022',
            "Tuan Pengerusi [Dato' Ramli bin Dato’ Mohd Nor [Cameron Highlands)]:\n",
            "Tuan Pengerusi [Dato' Ramli bin Dato’ Mohd Nor (Cameron Highlands)]:\n",
            '1111 111111111 111111 11111 111 11111 1111 111 11111111 111111111111\n',
            '0000 000000000 000000 00000 000 00000 0000 000 00000000 000000000000\n')
    replace('14122021',
            "Menteri Tenaga dan Sumber Asli (Datuk Seri Takiyuddin bin Hassan)]: Saya\n",
            "Menteri Tenaga dan Sumber Asli [Datuk Seri Takiyuddin bin Hassan]: Saya\n",
            '1111111 111111 111 111111 1111 111111 1111 1111111111 111 11111111 0000\n',
            '0000000 000000 000 000000 0000 000000 0000 0000000000 000 00000000 0000\n')
    # was not italicised
    replace('03032022',
            "[Beberapa Ahli-ahli Yang Berhormat bangun]\n",
            "[Beberapa Ahli-ahli Yang Berhormat bangun]\n",
            'all',
            'all')
    replace('07032018',
            "[Timbalan Yang di-Pertua (Datuk Seri Dr. Ronald Kiandee)\n",
            "[Timbalan Yang di-Pertua (Datuk Seri Dr. Ronald Kiandee)\n",
            '000000000 0000 000000000 000000 0000 000 000000 00000000\n',
            'all')

    # the format should be Menteri [Name]
    replace('22072020',
            'Ustaz Haji Ahmad Marzuk bin Shaary [Timbalan Menteri di Jabatan\n',
            'Timbalan Menteri di Jabatan Perdana Menteri (Hal Ehwal Agama) [Ustaz\n',
            '11111111 1111111 11 1111111 1111111 1111111 1111 11111 111111 111111\n',
            'none')
    replace('22072020',
            'Perdana Menteri (Hal Ehwal Agama)]: Bismillahi Rahmani Rahim. Tuan Yang di-\n',
            'Haji Ahmad Marzuk bin Shaary]: Bismillahi Rahmani Rahim. Tuan Yang di-\n',
            '1111 11111 111111 111 11111111 0000000000 0000000 000000 0000 0000 000\n',
            '0000 00000 000000 000 00000000 1111111111 1111111 111111 0000 0000 000\n')
    replace('13082020',
            'Ustaz Haji Ahmad Marzuk bin Shaary [Timbalan Menteri di Jabatan\n',
            'Timbalan Menteri di Jabatan Perdana Menteri (Hal Ehwal Agama) [Ustaz\n',
            '11111111 1111111 11 1111111 1111111 1111111 1111 11111 111111 111111\n',
            'none')
    replace('13082020',
            'Perdana Menteri (Hal Ehwal Agama)]: Tuan Yang di-Pertua, saya menyokong.\n',
            'Haji Ahmad Marzuk bin Shaary]: Tuan Yang di-Pertua, saya menyokong.\n',
            '1111 11111 111111 111 11111111 0000 0000 0000000000 0000 0000000000\n',
            'none')

    replace('05112019',
            "Timbalan Yang di-Pertua (Dato' Mohd Rashid Hasnon) mempengerusikan\n",
            "[Timbalan Yang di-Pertua (Dato' Mohd Rashid Hasnon) mempengerusikan\n",
            '000000000 0000 000000000 000000 0000 000000 0000000 111111111111111\n',
            'all')

    replace('25052023',
            "Timbalan Yang di-Pe’tua [Dato' Raml’ bin Dato' Mohd Nor]: Sebentar Yang\n",
            "Timbalan Yang di-Pertua [Dato' Raml’ bin Dato' Mohd Nor]: Sebentar Yang\n",
            '11111111 1111 111111111 111111 11111 111 11111 1111 11111 00000000 0000\n',
            'none')
    replace('28112019',
            "[Tuan Yang di-Pertua mempengerusikan Jawatankuasa]\n",
            "[Tuan Yang di-Pertua mempengerusikan Jawatankuasa]\n",
            '00000 0000 000000000 111111111111111 1111111111111\n',
            'all')
    replace('03102022',
            "[Dato' Ramli bin Dato' Mohd Nor [Cameron Highlands]: Ada sesiapa Yang\n",
            "Dato' Ramli bin Dato' Mohd Nor [Cameron Highlands]: Ada sesiapa Yang\n",
            '11111 11111 111 11111 1111 111 11111111 11111111111 000 0000000 0000\n',
            'none')
    replace('21032022',
            "Mesyuarat disambung semula pada pukul 2.30 petang]\n",
            "[Mesyuarat disambung semula pada pukul 2.30 petang]\n",
            'all',
            'all')

    replace('09102019',
            "Menteri Sumber Manusia [Tuan M. Kulasegaran [Ipoh Barat]: Cukup Tuan Yang\n",
            "Menteri Sumber Manusia [Tuan M. Kulasegaran [Ipoh Barat]]: Cukup Tuan Yang\n",
            '1111111 111111 1111111 11111 11 11111111111 11111 11111111 00000 0000 0000\n',
            'none')

    replace('21022023',
            'Terima kasih, saya mohon menyokong. [Tepuk]\n',
            'Terima kasih, saya mohon menyokong. [Tepuk]\n',
            'none',
            '000000 000000 0000 00000 0000000000 1111111\n')

    replace('21022023',
            '10.  Datuk Wira Haji Mohd. Anuar Mohd. Tahir [Temerloh] Datuk Wira Haji Mohd.\n',
            '10.  Datuk Wira Haji Mohd. Anuar Mohd. Tahir [Temerloh] minta\n',
            '111  11111 1111 1111 11111 11111 11111 11111 1111111111 00000\n',
            'none')
    replace('09032022',
            '10.  Datuk Wira Haji Mohd. Anuar Mohd. Tahir [Temerloh] Datuk Wira Haji Mohd.\n',
            '10.  Datuk Wira Haji Mohd. Anuar Mohd. Tahir [Temerloh] minta\n',
            '111  11111 1111 1111 11111 11111 11111 11111 1111111111 00000\n',
            'none')
    replace('09032022',
            'Anuar Mohd. Tahir [Temerloh] minta Menteri Tenaga dan Sumber Asli menyatakan usaha\n',
            'Menteri Tenaga dan Sumber Asli menyatakan usaha\n',
            'none',
            'none')
    replace('04082022',
            'Dato’ Sri Tuan Ibrahim bin Tuan Man Untuk makluman Dewan yang mulia,\n',
            'Dato’ Sri Tuan Ibrahim bin Tuan Man: Untuk makluman Dewan yang mulia,\n',
            '11111 111 1111 1111111 111 1111 1111 00000 00000000 00000 0000 000000\n',
            'none')
    replace('18112021',
            'pembangkang. Timbalan Yang di-Pertua [Dato’ Mohd Rashid Hasnon]: Silakan\n',
            'pembangkang.\nTimbalan Yang di-Pertua [Dato’ Mohd Rashid Hasnon]: Silakan\n',
            '000000000000\n11111111 1111 111111111 111111 1111 111111 11111111 0000000\n',
            'none')


if __name__ == "__main__":
    edit_hansards()
