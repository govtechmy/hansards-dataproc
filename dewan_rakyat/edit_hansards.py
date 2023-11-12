"""Directly edit specific Hansards to ease tabulation
"""
import re


def replace(
    hansard_date,
    old_text_snippet,
    new_text_snippet,
    new_bold_snippet,
    new_italics_snippet,
):
    if new_bold_snippet == "all":
        new_bold_snippet = re.sub(r"\S", "1", new_text_snippet)
    if new_italics_snippet == "all":
        new_italics_snippet = re.sub(r"\S", "1", new_text_snippet)
    if new_bold_snippet == "none":
        new_bold_snippet = re.sub(r"\S", "0", new_text_snippet)
    if new_italics_snippet == "none":
        new_italics_snippet = re.sub(r"\S", "0", new_text_snippet)

    assert re.fullmatch(
        r"[\s01]*", new_bold_snippet
    ), f"new_bold_snippet ({new_bold_snippet}) must only contain 0s and 1s"
    assert re.fullmatch(
        r"[\s01]*", new_italics_snippet
    ), f"new_italics_snippet ({new_italics_snippet}) must only contain 0s and 1s"
    assert len(new_text_snippet) == len(new_bold_snippet) == len(new_italics_snippet), (
        f"new_text_snippet ({new_text_snippet}), new_bold_snippet ({new_bold_snippet}), "
        f"and new_italics_snippet ({new_italics_snippet}) must be of the same length"
    )
    assert (
        len(new_text_snippet.replace(" ", ""))
        == len(new_bold_snippet.replace(" ", ""))
        == len(new_italics_snippet.replace(" ", ""))
    ), (
        f"Without spaces, new_text_snippet ({new_text_snippet.replace(' ', '')}), "
        f"new_bold_snippet ({new_bold_snippet.replace(' ', '')}), "
        f"and new_italics_snippet ({new_italics_snippet.replace(' ', '')}) must be of the same length"
    )
    year = hansard_date[-4:]
    sortable_date = (
        f"{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}"  # YYYY-MM-DD
    )
    dir_path = f"pretabulation/{sortable_date}/"
    try:
        with open(dir_path + "plaintext.txt", "r") as f:
            text = f.readlines()
        with open(dir_path + "bold.txt", "r") as f:
            bold = f.readlines()
        with open(dir_path + "italics.txt", "r") as f:
            italics = f.readlines()
        num_edits = 0
        for idx in range(len(text)):
            if old_text_snippet == text[idx]:
                # get the starting index where the match begins
                text[idx] = new_text_snippet
                bold[idx] = new_bold_snippet
                italics[idx] = new_italics_snippet
                num_edits += 1

        with open(dir_path + "plaintext.txt", "w") as f:
            f.writelines(text)
        with open(dir_path + "bold.txt", "w") as f:
            f.writelines(bold)
        with open(dir_path + "italics.txt", "w") as f:
            f.writelines(italics)
        print(f"{hansard_date} Num changes made: {num_edits}")

    except FileNotFoundError:
        print(f"{hansard_date} not found, skipping")


def edit_hansards():
    replace(
        "08112023",
        "Institusi) Tuan Ramkarpal Singh a/l Karpal Singh]: Terima kasih Tuan Yang di-Pertua.\n",
        "Institusi) [Tuan Ramkarpal Singh a/l Karpal Singh]: Terima kasih Tuan Yang di-Pertua.\n",
        "1111111111 1111 111111111 11111 111 111111 11111111 000000 00000 0000 0000 0000000000\n",
        "none",
    )
    replace(
        "02112023",
        "Ahmad Fakhruddin bin Fakhrurazi [Kuala Kedah]: Dato' Yang di-Pertua, sebelum\n",
        "Dr. Ahmad Fakhruddin bin Fakhrurazi [Kuala Kedah]: Dato' Yang di-Pertua, sebelum\n",
        "111 11111 1111111111 111 1111111111 111111 1111111 00000 0000 0000000000 0000000\n",
        "none",
    )
    replace(
        "24102023",
        "Seri Dr. Shahidan bin Kassim [Arau]: Okey, yang pertamanya ingin saya Tuan\n",
        "Datuk Seri Dr. Shahidan bin Kassim [Arau]: Okey, yang pertamanya ingin saya Tuan\n",
        "11111 1111 111 11111111 111 111111 1111111 00000 0000 0000000000 00000 0000 0000\n",
        "none",
    )
    replace(
        "06112023",
        "Tugas-tugas Khas) Datuk Ugak anak Kumbong: Terima kasih Puan Timbalan Pengerusi.\n",
        "Tugas-tugas Khas) [Datuk Ugak anak Kumbong]: Terima kasih Puan Timbalan Pengerusi.\n",
        "11111111111 11111 111111 1111 1111 111111111 000000 00000 0000 00000000 0000000000\n",
        "none",
    )
    replace(
        "31102023",
        "[Dato’ Seri Azalina Othman Said]: Bismillahi Rahmani Rahim, Tuan Yang di-Pertua,\n",
        "",
        "none",
        "none",
    )
    replace(
        "31102023",
        "Menteri di Jabatan Perdana Menteri (Undang-undang dan Reformasi Institusi)\n",
        "Menteri di Jabatan Perdana Menteri (Undang-undang dan Reformasi Institusi) [Dato’ Seri Azalina Othman Said]: Bismillahi Rahmani Rahim, Tuan Yang di-Pertua,\n",
        "1111111 11 1111111 1111111 1111111 11111111111111 111 111111111 1111111111 111111 1111 1111111 111111 111111 0000000000 0000000 000000 0000 0000 0000000000\n",
        "0000000 00 0000000 0000000 0000000 00000000000000 000 000000000 0000000000 000000 0000 0000000 000000 000000 1111111111 1111111 111110 0000 0000 0000000000\n",
    )
    replace(
        "30102023",
        "[Dato’ Sri Azalina Othman Said]: Terima kasih Tuan Speaker. Bismillahi Rahmani Rahim,\n",
        "",
        "none",
        "none",
    )
    replace(
        "30102023",
        "Menteri di Jabatan Perdana Menteri (Undang-undang dan Reformasi Institusi)\n",
        "Menteri di Jabatan Perdana Menteri (Undang-undang dan Reformasi Institusi) [Dato’ Seri Azalina Othman Said]: Terima kasih Tuan Speaker. Bismillahi Rahmani Rahim,\n",
        "1111111 11 1111111 1111111 1111111 11111111111111 111 111111111 1111111111 111111 1111 1111111 111111 111111 000000 00000 0000 00000000 0000000000 0000000 000000\n",
        "0000000 00 0000000 0000000 0000000 00000000000000 000 000000000 0000000000 000000 0000 0000000 000000 000000 000000 00000 0000 00000000 1111111111 1111111 111111\n",
    )
    replace(
        "20072022",
        "Tuan Pengerusi [Dato’ Ramli bin Dato’ Mohd Nor [Cameron Highlands)]: Ada\n",
        "Tuan Pengerusi [Dato’ Ramli bin Dato’ Mohd Nor (Cameron Highlands)]: Ada\n",
        "1111 111111111 111111 11111 111 11111 1111 111 11111111 111111111111 000\n",
        "0000 000000000 000000 00000 000 00000 0000 000 00000000 000000000000 000\n",
    )
    replace(
        "16082018",
        "Tuan Noor Amin bin Ahmad [Kangar] Tuan Noor Amin bin Ahmad [Kangar]:\n",
        "Tuan Noor Amin bin Ahmad [Kangar]:\n",
        "1111 1111 1111 111 11111 111111111\n",
        "0000 0000 0000 000 00000 000000000\n",
    )
    replace(
        "06082018",
        "Dato’ Dr. Noor Azmi bin Ghazali [Bagan Serai Ok.\n",
        "Dato’ Dr. Noor Azmi bin Ghazali [Bagan Serai]: Ok.\n",
        "11111 111 1111 1111 111 1111111 111111 1111111 000\n",
        "00000 000 0000 0000 000 0000000 000000 0000000 000\n",
    )
    replace(
        "16072019",
        "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa[ [Ketereh]: Yang\n",
        "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa [Ketereh]: Yang\n",
        "111 111 11111 1111 11111111 1111 111111 111 1111 1111 1111111111 0000\n",
        "000 000 00000 0000 00000000 0000 000000 000 0000 0000 0000000000 0000\n",
    )
    replace(
        "15102018",
        "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa[ [Ketereh]: Terima kasih\n",
        "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa [Ketereh]: Terima kasih\n",
        "111 111 11111 1111 11111111 1111 111111 111 1111 1111 1111111111 000000 00000\n",
        "000 000 00000 0000 00000000 0000 000000 000 0000 0000 0000000000 000000 00000\n",
    )
    replace(
        "17112021",
        "Timbalan Menteri Sumber Manusia [Tuan Haji Awang bin Hashim:]\n",
        "Timbalan Menteri Sumber Manusia [Tuan Haji Awang bin Hashim]:\n",
        "11111111 1111111 111111 1111111 11111 1111 11111 111 11111111\n",
        "00000000 0000000 000000 0000000 00000 0000 00000 000 00000000\n",
    )
    replace(
        "04082022",
        "Tuan Pengerusi [Dato' Ramli bin Dato’ Mohd Nor [Cameron Highlands)]:\n",
        "Tuan Pengerusi [Dato' Ramli bin Dato’ Mohd Nor (Cameron Highlands)]:\n",
        "1111 111111111 111111 11111 111 11111 1111 111 11111111 111111111111\n",
        "0000 000000000 000000 00000 000 00000 0000 000 00000000 000000000000\n",
    )
    replace(
        "14122021",
        "Menteri Tenaga dan Sumber Asli (Datuk Seri Takiyuddin bin Hassan)]: Saya\n",
        "Menteri Tenaga dan Sumber Asli [Datuk Seri Takiyuddin bin Hassan]: Saya\n",
        "1111111 111111 111 111111 1111 111111 1111 1111111111 111 11111111 0000\n",
        "0000000 000000 000 000000 0000 000000 0000 0000000000 000 00000000 0000\n",
    )
    # was not italicised
    replace(
        "03032022",
        "[Beberapa Ahli-ahli Yang Berhormat bangun]\n",
        "[Beberapa Ahli-ahli Yang Berhormat bangun]\n",
        "all",
        "all",
    )
    replace(
        "07032018",
        "[Timbalan Yang di-Pertua (Datuk Seri Dr. Ronald Kiandee)\n",
        "[Timbalan Yang di-Pertua (Datuk Seri Dr. Ronald Kiandee)\n",
        "000000000 0000 000000000 000000 0000 000 000000 00000000\n",
        "all",
    )

    # the format should be Menteri [Name]
    replace(
        "22072020",
        "Ustaz Haji Ahmad Marzuk bin Shaary [Timbalan Menteri di Jabatan\n",
        "Timbalan Menteri di Jabatan Perdana Menteri (Hal Ehwal Agama) [Ustaz\n",
        "11111111 1111111 11 1111111 1111111 1111111 1111 11111 111111 111111\n",
        "none",
    )
    replace(
        "22072020",
        "Perdana Menteri (Hal Ehwal Agama)]: Bismillahi Rahmani Rahim. Tuan Yang di-\n",
        "Haji Ahmad Marzuk bin Shaary]: Bismillahi Rahmani Rahim. Tuan Yang di-\n",
        "1111 11111 111111 111 11111111 0000000000 0000000 000000 0000 0000 000\n",
        "0000 00000 000000 000 00000000 1111111111 1111111 111111 0000 0000 000\n",
    )
    replace(
        "13082020",
        "Ustaz Haji Ahmad Marzuk bin Shaary [Timbalan Menteri di Jabatan\n",
        "Timbalan Menteri di Jabatan Perdana Menteri (Hal Ehwal Agama) [Ustaz\n",
        "11111111 1111111 11 1111111 1111111 1111111 1111 11111 111111 111111\n",
        "none",
    )
    replace(
        "13082020",
        "Perdana Menteri (Hal Ehwal Agama)]: Tuan Yang di-Pertua, saya menyokong.\n",
        "Haji Ahmad Marzuk bin Shaary]: Tuan Yang di-Pertua, saya menyokong.\n",
        "1111 11111 111111 111 11111111 0000 0000 0000000000 0000 0000000000\n",
        "none",
    )

    replace(
        "05112019",
        "Timbalan Yang di-Pertua (Dato' Mohd Rashid Hasnon) mempengerusikan\n",
        "[Timbalan Yang di-Pertua (Dato' Mohd Rashid Hasnon) mempengerusikan\n",
        "000000000 0000 000000000 000000 0000 000000 0000000 111111111111111\n",
        "all",
    )

    replace(
        "25052023",
        "Timbalan Yang di-Pe’tua [Dato' Raml’ bin Dato' Mohd Nor]: Sebentar Yang\n",
        "Timbalan Yang di-Pertua [Dato' Raml’ bin Dato' Mohd Nor]: Sebentar Yang\n",
        "11111111 1111 111111111 111111 11111 111 11111 1111 11111 00000000 0000\n",
        "none",
    )
    replace(
        "28112019",
        "[Tuan Yang di-Pertua mempengerusikan Jawatankuasa]\n",
        "[Tuan Yang di-Pertua mempengerusikan Jawatankuasa]\n",
        "00000 0000 000000000 111111111111111 1111111111111\n",
        "all",
    )
    replace(
        "03102022",
        "[Dato' Ramli bin Dato' Mohd Nor [Cameron Highlands]: Ada sesiapa Yang\n",
        "Dato' Ramli bin Dato' Mohd Nor [Cameron Highlands]: Ada sesiapa Yang\n",
        "11111 11111 111 11111 1111 111 11111111 11111111111 000 0000000 0000\n",
        "none",
    )
    replace(
        "21032022",
        "Mesyuarat disambung semula pada pukul 2.30 petang]\n",
        "[Mesyuarat disambung semula pada pukul 2.30 petang]\n",
        "all",
        "all",
    )

    replace(
        "09102019",
        "Menteri Sumber Manusia [Tuan M. Kulasegaran [Ipoh Barat]: Cukup Tuan Yang\n",
        "Menteri Sumber Manusia [Tuan M. Kulasegaran [Ipoh Barat]]: Cukup Tuan Yang\n",
        "1111111 111111 1111111 11111 11 11111111111 11111 11111111 00000 0000 0000\n",
        "none",
    )

    replace(
        "21022023",
        "Terima kasih, saya mohon menyokong. [Tepuk]\n",
        "Terima kasih, saya mohon menyokong. [Tepuk]\n",
        "none",
        "000000 000000 0000 00000 0000000000 1111111\n",
    )

    replace(
        "21022023",
        "10.  Datuk Wira Haji Mohd. Anuar Mohd. Tahir [Temerloh] Datuk Wira Haji Mohd.\n",
        "10.  Datuk Wira Haji Mohd. Anuar Mohd. Tahir [Temerloh] minta\n",
        "111  11111 1111 1111 11111 11111 11111 11111 1111111111 00000\n",
        "none",
    )
    replace(
        "09032022",
        "10.  Datuk Wira Haji Mohd. Anuar Mohd. Tahir [Temerloh] Datuk Wira Haji Mohd.\n",
        "10.  Datuk Wira Haji Mohd. Anuar Mohd. Tahir [Temerloh] minta\n",
        "111  11111 1111 1111 11111 11111 11111 11111 1111111111 00000\n",
        "none",
    )
    replace(
        "09032022",
        "Anuar Mohd. Tahir [Temerloh] minta Menteri Tenaga dan Sumber Asli menyatakan usaha\n",
        "Menteri Tenaga dan Sumber Asli menyatakan usaha\n",
        "none",
        "none",
    )
    replace(
        "04082022",
        "Dato’ Sri Tuan Ibrahim bin Tuan Man Untuk makluman Dewan yang mulia,\n",
        "Dato’ Sri Tuan Ibrahim bin Tuan Man: Untuk makluman Dewan yang mulia,\n",
        "11111 111 1111 1111111 111 1111 1111 00000 00000000 00000 0000 000000\n",
        "none",
    )
    replace(
        "18112021",
        "pembangkang. Timbalan Yang di-Pertua [Dato’ Mohd Rashid Hasnon]: Silakan\n",
        "pembangkang.\nTimbalan Yang di-Pertua [Dato’ Mohd Rashid Hasnon]: Silakan\n",
        "000000000000\n11111111 1111 111111111 111111 1111 111111 11111111 0000000\n",
        "none",
    )
    replace(
        "15122021",
        "9. Datuk Zakaria bin Mohd. Edris @ Tubau [Libaran] mintra Menteri\n",
        "9. Datuk Zakaria bin Mohd. Edris @ Tubau [Libaran] minta Menteri\n",
        "11 11111 1111111 111 11111 11111 1 11111 111111111 00000 0000000\n",
        "none",
    )
    replace(
        "08032023",
        "Mohd Rafizi bin Ramli: Itu DE asas sebanyak empat peratus untuk Kedah, tujuh\n",
        "Tuan Mohd Rafizi bin Ramli: Itu DE asas sebanyak empat peratus untuk Kedah, tujuh\n",
        "1111 1111 111111 111 111111 000 00 0000 00000000 00000 0000000 00000 000000 00000\n",
        "none",
    )
    replace(
        "04082022",
        "RM500. Tuan Lim Guan Eng [Bagan]: Hanya itu cukai jualan sahaja?\n",
        "RM500.\nTuan Lim Guan Eng [Bagan]: Hanya itu cukai jualan sahaja?\n",
        "000000\n1111 111 1111 111 11111111 00000 000 00000 000000 0000000\n",
        "none",
    )
    replace(
        "07112019",
        "Taun Pengerusi [Dato' Mohd Rashid Hasnon]: Ya, sila. Masa telah tamat terima\n",
        "Tuan Pengerusi [Dato' Mohd Rashid Hasnon]: Ya, sila. Masa telah tamat terima\n",
        "1111 111111111 111111 1111 111111 11111111 000 00000 0000 00000 00000 000000\n",
        "none",
    )
    replace(
        "21112019",
        "Tuan Pengerusi [Dato’ Mohd Rashid Hasnon Tidak apa. Yang Berhormat\n",
        "Tuan Pengerusi [Dato’ Mohd Rashid Hasnon]: Tidak apa. Yang Berhormat\n",
        "1111 111111111 111111 1111 111111 11111111 00000 0000 0000 000000000\n",
        "none",
    )
    replace(
        "04072019",
        "Tuan Yang di-Pertua; Yang Berhormat Parit Sulong, habis.\n",
        "Tuan Yang di-Pertua: Yang Berhormat Parit Sulong, habis.\n",
        "1111 1111 1111111111 0000 000000000 00000 0000000 000000\n",
        "none",
    )
    replace(
        "04072019",
        "Tuan Yang di-Pertua; Yang Berhormat Kubang Kerian dulu.\n",
        "Tuan Yang di-Pertua: Yang Berhormat Kubang Kerian dulu.\n",
        "1111 1111 1111111111 0000 000000000 000000 000000 00000\n",
        "none",
    )
    replace(
        "29102019",
        "Tan Sri Haji Noh bin Haji Omar [Tanjong Karang ...Kes terowong, saya hendak\n",
        "Tan Sri Haji Noh bin Haji Omar [Tanjong Karang]: ...Kes terowong, saya hendak\n",
        "111 111 1111 111 111 1111 1111 11111111 11111111 000000 000000000 0000 000000\n",
        "none",
    )
    replace(
        "23102019",
        "Tuan Abdul Latiff bin Abdul Rahman [Kuala Krai Terima kasih Tuan Yang di-\n",
        "Tuan Abdul Latiff bin Abdul Rahman [Kuala Krai]: Terima kasih Tuan Yang di-\n",
        "1111 11111 111111 111 11111 111111 111111 111111 000000 00000 0000 0000 000\n",
        "none",
    )
    replace(
        "07122021",
        "Tuan Pengeru’i [Dato' Mohd Rashid Hasnon]: Terima kasih Yang Berhormat\n",
        "Tuan Pengerusi [Dato' Mohd Rashid Hasnon]: Terima kasih Yang Berhormat\n",
        "1111 111111111 111111 1111 111111 11111111 000000 00000 0000 000000000\n",
        "none",
    )
    replace(
        "13122021",
        "Tuan Pengrusi [Dato' Mohd Rashid Hasnon]: Baik, terima kasih Yang\n",
        "Tuan Pengerusi [Dato' Mohd Rashid Hasnon]: Baik, terima kasih Yang\n",
        "1111 111111111 111111 1111 111111 11111111 00000 000000 00000 0000\n",
        "none",
    )
    replace(
        "22112021",
        "Menteri di Jabatan Perdana Menteri [Ekonomi) [Dato' Sri Mustapa bin\n",
        "Menteri di Jabatan Perdana Menteri (Ekonomi) [Dato' Sri Mustapa bin\n",
        "1111111 11 1111111 1111111 1111111 111111111 111111 111 1111111 111\n",
        "none",
    )
    replace(
        "22112021",
        "Menteri di Jabatan Perdana Menteri (Hal Ehwal Agama) (Tuan Haji Idris bin\n",
        "Menteri di Jabatan Perdana Menteri (Hal Ehwal Agama) [Tuan Haji Idris bin\n",
        "1111111 11 1111111 1111111 1111111 1111 11111 111111 11111 1111 11111 111\n",
        "none",
    )
    replace(
        "22112021",
        "Haji Ahmad): Assalamualaikum warahmatullahi wabarakatuh dan selamat petang...\n",
        "Haji Ahmad]: Assalamualaikum warahmatullahi wabarakatuh dan selamat petang...\n",
        "1111 1111111 000000000000000 00000000000000 00000000000 000 0000000 000000000\n",
        "0000 0000000 111111111111111 11111111111111 11111111111 000 0000000 000000000\n",
    )
    replace(
        "08112021",
        "Tuan Yang di-Pertua; Terima kasih. Yang Berhormat Bintulu.\n",
        "Tuan Yang di-Pertua: Terima kasih. Yang Berhormat Bintulu.\n",
        "1111 1111 1111111111 000000 000000 0000 000000000 00000000\n",
        "none",
    )
    replace(
        "08112021",
        "Tuan Yang di-Pertua; Terima kasih. Yang Berhormat Bintulu.\n",
        "Tuan Yang di-Pertua: Terima kasih. Yang Berhormat Bintulu.\n",
        "1111 1111 1111111111 000000 000000 0000 000000000 00000000\n",
        "none",
    )
    replace(
        "16102018",
        "[Puan Zuraida binti Kamaruddin: Insya-Allah. Insya-Allah. Because a...\n",
        "Puan Zuraida binti Kamaruddin: Insya-Allah. Insya-Allah. Because a...\n",
        "1111 1111111 11111 11111111111 000000000000 000000000000 0000000 0000\n",
        "0000 0000000 00000 00000000000 111111111111 111111111111 1111111 1111\n",
    )
    replace(
        "26072018",
        "Tuan Yang di-Pertua; Tidak bagi peluang?\n",
        "Tuan Yang di-Pertua: Tidak bagi peluang?\n",
        "1111 1111 1111111111 00000 0000 00000000\n",
        "none",
    )
    replace(
        "22072020",
        "Puan Teresa Kok [Puan Teresa Kok [Seputeh]: Yang Berhormat Arau mahu\n",
        "Puan Teresa Kok [Seputeh]: Yang Berhormat Arau mahu\n",
        "1111 111111 111 1111111111 0000 000000000 0000 0000\n",
        "none",
    )
    replace(
        "08122020",
        "Tuan Yang di-Pertua; Terima kasih Yang Berhormat. Yang Berhormat-Yang\n",
        "Tuan Yang di-Pertua: Terima kasih Yang Berhormat. Yang Berhormat-Yang\n",
        "1111 1111 1111111111 000000 00000 0000 0000000000 0000 00000000000000\n",
        "none",
    )
    replace(
        "25082020",
        "Menteri di Jabatan Perdana Menteri (Parlimen dan Undang-undang) Dato’\n",
        "Menteri di Jabatan Perdana Menteri (Parlimen dan Undang-undang) [Dato’\n",
        "1111111 11 1111111 1111111 1111111 111111111 111 11111111111111 111111\n",
        "none",
    )
    replace(
        "16072019",
        "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa[ [Ketereh]: Apakah ini\n",
        "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa [Ketereh]: Apakah ini\n",
        "111 111 11111 1111 11111111 1111 111111 111 1111 1111 1111111111 000000 000\n",
        "none",
    )
    replace(
        "09072019",
        "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa[ [Ketereh]: Terima kasih\n",
        "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa [Ketereh]: Terima kasih\n",
        "111 111 11111 1111 11111111 1111 111111 111 1111 1111 1111111111 000000 00000\n",
        "none",
    )
    replace(
        "09072019",
        "Dato' Haji Salahuddin bin Ayub; Yang Berhormat Setiawangsa dan Yang\n",
        "Dato' Haji Salahuddin bin Ayub: Yang Berhormat Setiawangsa dan Yang\n",
        "11111 1111 1111111111 111 11110 0000 000000000 00000000000 000 0000\n",
        "none",
    )
    replace(
        "26032019",
        "tidak? Tuan Khalid bin Abd Samad: Itu kurang bijak lah kalau guna macam itu.\n",
        "tidak?\nTuan Khalid bin Abd Samad: Itu kurang bijak lah kalau guna macam itu.\n",
        "000000\n1111 111111 111 111 111111 000 000000 00000 000 00000 0000 00000 0000\n",
        "000000\n0000 000000 000 000 000000 000 000000 00000 000 00000 0000 00000 0000\n",
    )
    replace(
        "18072019",
        "Tuan Yang di-Pertua Yang Berhormat Arau, Yang Berhormat Arau sudah lebih\n",
        "Tuan Yang di-Pertua: Yang Berhormat Arau, Yang Berhormat Arau sudah lebih\n",
        "1111 1111 1111111111 0000 000000000 00000 0000 000000000 0000 00000 00000\n",
        "none",
    )
    # Yang di-Pertua wasn't italicised
    replace(
        "11102019",
        "[Tuan Yang di-Pertua mempengerusikan Mesyuarat]\n",
        "[Tuan Yang di-Pertua mempengerusikan Mesyuarat]\n",
        "00000 0000 000000000 111111111111111 1111111110\n",
        "11111 1111 111111111 111111111111111 1111111111\n",
    )

    replace(
        "28032019",
        "Tuan Yang di-Pertua; Yang Berhormat Kubang Kerian dulu.\n",
        "Tuan Yang di-Pertua: Yang Berhormat Kubang Kerian dulu.\n",
        "1111 1111 1111111111 0000 000000000 000000 000000 00000\n",
        "none",
    )
    replace(
        "16102019",
        "[ Timbalan Yang di-Pertua (Tuan Nga Kor Ming) mempengerusikan Mesyuarat]\n",
        "[Timbalan Yang di-Pertua (Tuan Nga Kor Ming) mempengerusikan Mesyuarat]\n",
        "000000000 0000 000000000 00000 000 000 00000 111111111111111 1111111110\n",
        "all",
    )
    replace(
        "31102019",
        "Datuk Seri Dr. Haji Dzulkefly bin Ahmad] Dalam hal perkara vape ya. Vape\n",
        "Datuk Seri Dr. Haji Dzulkefly bin Ahmad]: Dalam hal perkara vape ya. Vape\n",
        "11111 1111 111 1111 111111111 111 1111111 00000 000 0000000 0000 000 0000\n",
        "00000 0000 000 0000 000000000 000 0000000 00000 000 0000000 1111 000 1111\n",
    )
    replace(
        "03122019",
        "[Dato’ Seri Dr. Shahidan bin Kassim [Arau]: No, Yang Berhormat Pasir Salak tarik\n",
        "Dato’ Seri Dr. Shahidan bin Kassim [Arau]: No, Yang Berhormat Pasir Salak tarik\n",
        "11111 1111 111 11111111 111 111111 1111111 000 0000 000000000 00000 00000 00000\n",
        "00000 0000 000 00000000 000 000000 0000000 110 0000 000000000 00000 00000 00000\n",
    )
    replace(
        "06082018",
        "Tuan Yang di-Pertua; Saya ingat Yang Berhormat Menteri sudah pun menjawab\n",
        "Tuan Yang di-Pertua: Saya ingat Yang Berhormat Menteri sudah pun menjawab\n",
        "1111 1111 1111111111 0000 00000 0000 000000000 0000000 00000 000 00000000\n",
        "none",
    )
    replace(
        "23072018",
        "Timbalan Menteri Pendidikan [Puan Teo Nie Ching [Kulai]: Tuan Yang di-Pertua,\n",
        "Timbalan Menteri Pendidikan [Puan Teo Nie Ching [Kulai]]: Tuan Yang di-Pertua,\n",
        "11111111 1111111 1111111111 11111 111 111 11111 111111111 0000 0000 0000000000\n",
        "none",
    )
    replace(
        "12112018",
        "Tuan Waytha Moorthy a/l Ponnusamy Terima kasih Yang Berhormat. Mengenai\n",
        "Tuan Waytha Moorthy a/l Ponnusamy: Terima kasih Yang Berhormat. Mengenai\n",
        "1111 111111 1111111 111 1111111111 000000 00000 0000 0000000000 00000000\n",
        "none",
    )
    replace(
        "21112018",
        "Tuan Baru Bian Saya akan menjawab secara bertulis, Tuan Yang di-Pertua. Yang\n",
        "Tuan Baru Bian: Saya akan menjawab secara bertulis, Tuan Yang di-Pertua. Yang\n",
        "1111 1111 11111 0000 0000 00000000 000000 000000000 0000 0000 0000000000 0000\n",
        "none",
    )
    replace(
        "08082018",
        "Tuan Yang di-Pertua Yang Berhormat Johor Bahru, silakan.\n",
        "Tuan Yang di-Pertua: Yang Berhormat Johor Bahru, silakan.\n",
        "1111 1111 1111111111 0000 000000000 00000 000000 00000000\n",
        "none",
    )
    replace(
        "02032022",
        "Timbalan Yang di-Pertua [Dato' Mohd Rashid Hasnon]: Timbalan Yang di-\n",
        "Timbalan Yang di-",
        "11111111 1111 111",
        "none",
    )
    replace(
        "26082020",
        "[Timbalan Yang di-Pertua (Dato’ Sri Azalina Othman Said]) mempengerusikan\n",
        "[Timbalan Yang di-Pertua (Dato’ Sri Azalina Othman Said) mempengerusikan\n",
        "000000000 0000 000000000 000000 000 0000000 000000 00000 111111111111111\n",
        "all",
    )
    replace(
        "12032018",
        "[Timbalan Yang di-Pertua (Dato’ Sri Haji Ismail bin Haji Mohamed Said])\n",
        "[Timbalan Yang di-Pertua (Dato’ Sri Haji Ismail bin Haji Mohamed Said)\n",
        "000000000 0000 000000000 000000 000 0000 000000 000 0000 0000000 00000\n",
        "all",
    )
    replace(
        "31072018",
        "Dato’ Seri Dr. Wan Azizah Wan Ismail] Terima kasih Yang Berhormat Permatang\n",
        "Dato’ Seri Dr. Wan Azizah Wan Ismail: Terima kasih Yang Berhormat Permatang\n",
        "11111 1111 111 111 111111 111 1111111 000000 00000 0000 000000000 000000000\n",
        "none",
    )
    replace(
        "14032023",
        "[Kepala P.14 jadi sebahagian daripada Anggaran Perbelanjaan\n",
        "[Kepala P.14 jadi sebahagian daripada Anggaran Perbelanjaan]\n",
        "none",
        "all",
    )
    replace("28032023", "Mesyuarat\n", "Mesyuarat]\n", "1111111110\n", "all")
    replace("30032023", "penyata tersebut.”\n", "penyata tersebut.”]\n", "none", "all")
    replace(
        "30032023",
        "[Majlis bersidang dalam Jawatankuasa.\n",
        "[Majlis bersidang dalam Jawatankuasa]\n",
        "all",
        "all",
    )
    replace("20072022", "undang.\n", "undang.]\n", "none", "all")
    replace(
        "17032022",
        "Kelima, Parlimen yang Keempat Belas”.\n",
        "Kelima, Parlimen yang Keempat Belas”.]\n",
        "none",
        "all",
    )
    replace("26072021", "suara\n", "suara]\n", "none", "all")
    replace(
        "06082020",
        "[Timbalan Yang di-Pertua [Dato’ Mohd Rashid Hasnon mempengerusikan\n",
        "[Timbalan Yang di-Pertua [Dato’ Mohd Rashid Hasnon] mempengerusikan\n",
        "000000000 0000 000000000 000000 0000 000000 0000000 111111111111111\n",
        "all",
    )
    replace(
        "12082020",
        "sebahagian daripada Jadual\n",
        "sebahagian daripada Jadual]\n",
        "none",
        "all",
    )
    replace(
        "17082020",
        'kuasa pada 10 Mac 2020."\n',
        'kuasa pada 10 Mac 2020."]\n',
        "none",
        "all",
    )
    replace("11082020", 'tersebut."\n', 'tersebut."]\n', "none", "all")
    replace(
        "02112020",
        "dalam firman-Nya, [Membaca Surah Quraisy) yang bermaksud, “Kerana kebiasaan aman\n",
        "dalam firman-Nya, [Membaca Surah Quraisy] yang bermaksud, “Kerana kebiasaan aman\n",
        "none",
        "00000 00000000000 11111111 11111 11111111 0000 0000000000 1111111 111111111 1111\n",
    )
    replace(
        "10082020",
        "Penggal Ketiga, Parlimen Yang Keempat Belas.”\n",
        "Penggal Ketiga, Parlimen Yang Keempat Belas.”]\n",
        "none",
        "all",
    )
    replace("02042019", "penyata tersebut.”\n", "penyata tersebut.”]\n", "none", "all")
    replace(
        "02042019",
        "mempengerusikan Mesyuarat\n",
        "mempengerusikan Mesyuarat]\n",
        "all",
        "all",
    )
    replace(
        "09042019",
        "mempengerusikan Mesyuarat\n",
        "mempengerusikan Mesyuarat]\n",
        "all",
        "all",
    )
    replace(
        "04072019",
        "[Timbalan Yang di-Pertua ([Dato’ Mohd Rashid Hasnon) mempengerusikan\n",
        "[Timbalan Yang di-Pertua (Dato’ Mohd Rashid Hasnon) mempengerusikan\n",
        "000000000 0000 000000000 000000 0000 000000 0000000 111111111111111\n",
        "all",
    )
    # there is many matches for the editing phrase, so we edit the next line instead
    replace(
        "06122018",
        "Tuan Yang di-Pertua: Dengan itu Ahli-ahli Yang Berhormat, Mesyuarat Dewan hari\n",
        "]\nTuan Yang di-Pertua: Dengan itu Ahli-ahli Yang Berhormat, Mesyuarat Dewan hari\n",
        "0\n1111 1111 1111111111 000000 000 000000000 0000 0000000000 000000000 00000 0000\n",
        "none",
    )

    replace(
        "27032018",
        "[Masalah dikemuka bagi diputuskan, dan disetujukan.\n",
        "[Masalah dikemuka bagi diputuskan, dan disetujukan.]\n",
        "none",
        "all",
    )
    replace(
        "21112018",
        "apabila saya nak tanya tentang 1MDB. [Dewan riuh\n",
        "apabila saya nak tanya tentang 1MDB. [Dewan riuh]\n",
        "none",
        "0000000 0000 000 00000 0000000 00000 111111 11111\n",
    )

    replace("21112018", "senarai tersebut.”\n", "senarai tersebut.”]\n", "none", "all")

    # there is many matches for the editing phrase, so we edit the next line instead
    replace(
        "26032018",
        "Timbalan Yang di-Pertua [Dato' Sri Haji Ismail bin Haji Mohamed Said]: Yang\n",
        "]\nTimbalan Yang di-Pertua [Dato' Sri Haji Ismail bin Haji Mohamed Said]: Yang\n",
        "0\n11111111 1111 111111111 111111 111 1111 111111 111 1111 1111111 111111 0000\n",
        "none",
    )

    replace(
        "16082018",
        "[[Mesyuarat ditempohkan pada pukul 1.00 tengah hari]\n",
        "[Mesyuarat ditempohkan pada pukul 1.00 tengah hari]\n",
        "none",
        "all",
    )
    replace(
        "21032023",
        "Pertua. [Ketawa.\n",
        "Pertua. [Ketawa]\n",
        "none",
        "0000000 11111111\n",
    )

    replace(
        "17082020",
        "disifatkan telah berkuat kuasa pada 10 Mac 2020.”\n",
        "disifatkan telah berkuat kuasa pada 10 Mac 2020.”]\n",
        "none",
        "all",
    )

    replace(
        "09032023", "hendaklah disahkan.”\n", "hendaklah disahkan.”]\n", "none", "all"
    )

    replace(
        "16082018",
        "[“Bahawa mengikut Peraturan Mesyuarat 86(5), maka Penyata\n",
        "“Bahawa mengikut Peraturan Mesyuarat 86(5), maka Penyata\n",
        "none",
        "all",
    )

    replace(
        "21032023",
        "Timbalan Yang dan-Pertua [Puan Alice Lau Kiong Yieng]: Ahli-ahli Yang Berhormat,\n",
        "Timbalan Yang di-Pertua [Puan Alice Lau Kiong Yieng]: Ahli-ahli Yang Berhormat,\n",
        "11111111 1111 111111111 11111 11111 111 11111 1111111 000000000 0000 0000000000\n",
        "none",
    )

    replace(
        "28022023",
        "Seorang Ahli Sahabat-sahabat kita.\n",
        "Seorang Ahli: Sahabat-sahabat kita.\n",
        "1111111 11111 000000000000000 00000\n",
        "none",
    )

    replace(
        "30032023",
        "Dewan Rakyat. Kelvin Yii Lee Wuen [Bandar Kuching]: Bandar Kuching.\n",
        "Dr. Kelvin Yii Lee Wuen [Bandar Kuching]: Bandar Kuching.\n",
        "111 111111 111 111 1111 1111111 111111111 000000 00000000\n",
        "none",
    )

    replace(
        "10122018",
        "Pertua. Tuan Sanisvara Nethaji Rayer a/l Rajaji [Jelutong]: Yang Berhormat jangan\n",
        "Pertua.\nTuan Sanisvara Nethaji Rayer a/l Rajaji [Jelutong]: Yang Berhormat jangan\n",
        "0000000\n1111 111111111 1111111 11111 111 111111 11111111111 0000 000000000 000000\n",
        "none",
    )

    replace(
        "26072021",
        "pembangkang. Tuan Sanisvara Nethaji Rayer a/l Rajaji [Jelutong]: Saya\n",
        "pembangkang.\nTuan Sanisvara Nethaji Rayer a/l Rajaji [Jelutong]: Saya\n",
        "000000000000\n1111 111111111 1111111 11111 111 111111 11111111111 0000\n",
        "none",
    )

    replace(
        "21102019",
        "`Dato’ Sri Bung Moktar bin Radin [Kinabatangan]: Macam jadi sarapan pagi saya\n",
        "Dato’ Sri Bung Moktar bin Radin [Kinabatangan]: Macam jadi sarapan pagi saya\n",
        "11111 111 1111 111111 111 11111 111111111111111 00000 0000 0000000 0000 0000\n",
        "none",
    )

    replace(
        "22102019",
        "Padang Tuan Karupaiya A/L Mutusami [Padang Serai]: Terima kasih Tuan Yang\n",
        "Tuan Karupaiya A/L Mutusami [Padang Serai]: Terima kasih Tuan Yang\n",
        "1111 111111111 111 11111111 1111111 1111111 000000 00000 0000 0000\n",
        "none",
    )

    replace(
        "04042019",
        "Sri Haji Noh bin Haji Omar [Tanjong Karang]: Tuan Pengerusi, saya tidak\n",
        "Tan Sri Haji Noh bin Haji Omar [Tanjong Karang]: Tuan Pengerusi, saya tidak\n",
        "111 111 1111 111 111 1111 1111 11111111 11111111 0000 0000000000 0000 00000\n",
        "none",
    )

    replace(
        "28112019",
        "Jasin. Tuan P. Prabakaran [Batu]: Banyak lagi hendak bahas.\n",
        "Jasin.\nTuan P. Prabakaran [Batu]: Banyak lagi hendak bahas.\n",
        "000000\n1111 11 1111111111 1111111 000000 0000 000000 000000\n",
        "none",
    )

    replace(
        "21032018",
        "sudah.Dato’ Haji Mahfuz bin Haji Omar [Pokok Sena]: ...Ini satu yang bertentangan\n",
        "sudah.\nDato’ Haji Mahfuz bin Haji Omar [Pokok Sena]: ...Ini satu yang bertentangan\n",
        "000000\n11111 1111 111111 111 1111 1111 111111 111111 000000 0000 0000 000000000000\n",
        "none",
    )

    replace(
        "13112018",
        "Tuan Yang di-Pertua Yang Berhormat Kinabatangan. [Dewan riuh] Kita ikut\n",
        "Tuan Yang di-Pertua: Yang Berhormat Kinabatangan. [Dewan riuh] Kita ikut\n",
        "1111 1111 1111111111 0000 000000000 0000000000000 000000 00000 0000 0000\n",
        "0000 0000 0000000000 0000 000000000 0000000000000 111111 11111 0000 0000\n",
    )

    replace(
        "03122018",
        "silakan. Datuk Seri Panglima Madius Tangau [Tuaran]: Subjek yang sama.\n",
        "silakan.\nDatuk Seri Panglima Madius Tangau [Tuaran]: Subjek yang sama.\n",
        "00000000\n11111 1111 11111111 111111 111111 111111111 000000 0000 00000\n",
        "none",
    )

    replace(
        "02042018",
        "Menteri di Jabatan Perdana Menteri, Dato’ Sri Azalina Dato’ Othman Said\n",
        "Menteri di Jabatan Perdana Menteri [Dato’ Sri Azalina Dato’ Othman Said\n",
        "all",
        "none",
    )
    replace(
        "02042018",
        "[Pengerang]: Terima kasih Tuan Pengerusi. Yang Berhormat Kulai, rang undang-undang ini\n",
        "[Pengerang]]: Terima kasih Tuan Pengerusi. Yang Berhormat Kulai, rang undang-undang ini\n",
        "1111111111111 000000 00000 0000 0000000000 0000 000000000 000000 0000 0000000000000 000\n",
        "none",
    )
    replace(
        "30032017",
        "Haji Ahmad bin Haji Maslan) dan diluluskan)\n",
        "Haji Ahmad bin Haji Maslan) dan diluluskan]\n",
        "none",
        "all",
    )
    replace(
        "16112017",
        "[Masalah dikemuka bagi diputuskan, dan disetujukan.\n",
        "[Masalah dikemuka bagi diputuskan, dan disetujukan.]\n",
        "none",
        "all",
    )
    replace(
        "28112017",
        "sebahagian daripada Anggaran Pembangunan 2018\n",
        "sebahagian daripada Anggaran Pembangunan 2018]\n",
        "none",
        "all",
    )
    replace(
        "28112017",
        "Fasal 1 hingga 2 diperintahkan jadi sebahagian daripada rang undang-undang.\n",
        "[Fasal 1 hingga 2 diperintahkan jadi sebahagian daripada rang undang-undang.]\n",
        "none",
        "all",
    )
    replace(
        "28112017",
        "itu di ruangan enam dan tujuh senarai tersebut.”\n",
        "itu di ruangan enam dan tujuh senarai tersebut.”]\n",
        "none",
        "all",
    )
    replace(
        "28032017",
        "sembilan dan sepuluh penyata tersebut.” hendaklah disahkan.\n",
        "sembilan dan sepuluh penyata tersebut.” hendaklah disahkan.]\n",
        "none",
        "all",
    )
    replace(
        "03042017",
        "[Timbalan Yang di-Pertua [Datuk Seri Dr. Ronald Kiandee) mempengerusikan\n",
        "[Timbalan Yang di-Pertua (Datuk Seri Dr. Ronald Kiandee) mempengerusikan\n",
        "none",
        "all",
    )
    replace(
        "27032017",
        "Sembilan dan sepuluh penyata tersebut.”\n",
        "Sembilan dan sepuluh penyata tersebut.”]\n",
        "none",
        "all",
    )
    replace(
        "13112017",
        "itu di ruangan enam dan tujuh senarai tersebut.”\n",
        "itu di ruangan enam dan tujuh senarai tersebut.”]\n",
        "none",
        "all",
    )
    replace(
        "29032016",
        "[Masalah dikemuka bagi diputuskan, dan disetujukan.\n",
        "[Masalah dikemuka bagi diputuskan, dan disetujukan.]\n",
        "none",
        "all",
    )
    replace("28032016", 'penyata tersebut."\n', 'penyata tersebut."]\n', "none", "all")
    replace(
        "22112016",
        "ditangguhkan sehingga jam 10 pagi, hari Rabu 23 November tahun 2016.\n",
        "ditangguhkan sehingga jam 10 pagi, hari Rabu 23 November tahun 2016.]\n",
        "none",
        "all",
    )
    replace(
        "04042016", "sebagai Jawatankuasa\n", "sebagai Jawatankuasa]\n", "none", "all"
    )
    replace("07112016", "tersebut.”\n", "tersebut.”]\n", "none", "all")
    replace(
        "21032016",
        "Tuan Gobind Singh Deo [Puchong]: [Bangun\n",
        "Tuan Gobind Singh Deo [Puchong]: [Bangun]\n",
        "1111 111111 11111 111 1111111111 00000000\n",
        "0000 000000 00000 000 0000000000 11111111\n",
    )
    replace(
        "23112015",
        "[Timbalan Yang di-Pertua ([Datuk Seri Dr. Ronald Kiandee)\n",
        "[Timbalan Yang di-Pertua (Datuk Seri Dr. Ronald Kiandee)\n",
        "none",
        "all",
    )
    replace(
        "19112013",
        "[Timbalan Yang di-Pertua ([Datuk Seri Dr. Ronald Kiandee)\n",
        "[Timbalan Yang di-Pertua (Datuk Seri Dr. Ronald Kiandee)\n",
        "none",
        "all",
    )
    replace(
        "01102013",
        "[Disampuk Jadi saya harap kita tidak payah hendak risau.\n",
        "[Disampuk] Jadi saya harap kita tidak payah hendak risau.\n",
        "none",
        "1111111111 0000 0000 00000 0000 00000 00000 000000 000000\n",
    )
    replace(
        "20112013",
        "[Timbalan Yang di-Pertua [Datuk Ronald Kiandee) mempengerusikan\n",
        "[Timbalan Yang di-Pertua (Datuk Ronald Kiandee) mempengerusikan\n",
        "none",
        "all",
    )
    replace(
        "18042012",
        "[[Fasal-fasal 1 hingga 34 dikemukakan kepada Jawatankuasa]\n",
        "[Fasal-fasal 1 hingga 34 dikemukakan kepada Jawatankuasa]\n",
        "none",
        "all",
    )
    replace(
        "02102012",
        "Tuan N. Gobalakrishnan [Padang Serai]: [Bangun\n",
        "Tuan N. Gobalakrishnan [Padang Serai]: [Bangun]\n",
        "1111 11 11111111111111 1111111 1111111 00000000\n",
        "0000 00 00000000000000 0000000 0000000 11111111\n",
    )
    replace(
        "09042012",
        "sebahagian daripada Jadual.\n",
        "sebahagian daripada Jadual.]\n",
        "none",
        "all",
    )
    replace(
        "09042012",
        "sebahagian daripada Jadual.\n",
        "sebahagian daripada Jadual.]\n",
        "none",
        "all",
    )
    replace("04042012", "ini. [Dewan\n", "ini. [Dewan]\n", "none", "0000 1111111\n")
    replace(
        "28102015",
        "[Ketawa Yang Berhormat Kuala Terengganu.\n",
        "[Ketawa] Yang Berhormat Kuala Terengganu.\n",
        "none",
        "11111111 0000 000000000 00000 00000000000\n",
    )
    replace(
        "30032015",
        "Jawatankuasa sebuah-buah Majlis”.\n",
        "Jawatankuasa sebuah-buah Majlis”.]\n",
        "none",
        "all",
    )
    replace(
        "30032015",
        "Jawatankuasa sebuah-buah Majlis”.\n",
        "Jawatankuasa sebuah-buah Majlis”.]\n",
        "none",
        "all",
    )
    replace(
        "06042015",
        "[Timbalan Yang di-Pertua ([Datuk Seri Dr. Ronald Kiandee) mempengerusikan\n",
        "[Timbalan Yang di-Pertua (Datuk Seri Dr. Ronald Kiandee) mempengerusikan\n",
        "none",
        "all",
    )
    replace(
        "06042015",
        "[Timbalan Yang di-Pertua ([Datuk Seri Dr. Ronald Kiandee) mempengerusikan\n",
        "[Timbalan Yang di-Pertua (Datuk Seri Dr. Ronald Kiandee) mempengerusikan\n",
        "none",
        "all",
    )
    replace(
        "06042015",
        "Beberapa Ahli: [Bercakap tanpa menggunakan pembesar suara\n",
        "Beberapa Ahli: [Bercakap tanpa menggunakan pembesar suara]\n",
        "11111111 11111 000000000 00000 00000000000 00000000 000000\n",
        "00000000 00000 111111111 11111 11111111111 11111111 111111\n",
    )
    replace(
        "24112015",
        "[Masalah dikemuka bagi diputuskan, dan disetujukan.\n",
        "[Masalah dikemuka bagi diputuskan, dan disetujukan.]\n",
        "none",
        "all",
    )
    replace(
        "09042015",
        "bahagian dia terangkan... [Disampuk Itu sekejap lagi saya akan sambut. Saya rasa benda\n",
        "bahagian dia terangkan... [Disampuk] Itu sekejap lagi saya akan sambut. Saya rasa benda\n",
        "none",
        "00000000 000 000000000000 1111111111 000 0000000 0000 0000 0000 0000000 0000 0000 00000\n",
    )
    replace(
        "31032014",
        "dan butiran projek dalam ruang sembilan dan sepuluh penyata tersebut”.\n",
        "dan butiran projek dalam ruang sembilan dan sepuluh penyata tersebut”.]\n",
        "none",
        "all",
    )
    replace(
        "18112014",
        "[Masalah dikemuka bagi diputuskan, dan disetujukan.\n",
        "[Masalah dikemuka bagi diputuskan, dan disetujukan.]\n",
        "none",
        "all",
    )
    replace(
        "18112014",
        "[Masalah dikemuka bagi diputuskan, dan disetujukan.\n",
        "[Masalah dikemuka bagi diputuskan, dan disetujukan.]\n",
        "none",
        "all",
    )
    replace(
        "25112013",
        "[Tuan Pengerusi [Dato’ Haji Ismail bin Haji Mohamed Said) mempengerusikan\n",
        "[Tuan Pengerusi (Dato’ Haji Ismail bin Haji Mohamed Said) mempengerusikan\n",
        "none",
        "all",
    )
    replace(
        "03122013",
        "itu di ruangan enam dan tujuh senarai tersebut.”\n",
        "itu di ruangan enam dan tujuh senarai tersebut.”]\n",
        "none",
        "all",
    )
    replace(
        "04122013",
        "[Timbalan Yang di-Pertua [Datuk Ronald Kiandee) mempengerusikan\n",
        "[Timbalan Yang di-Pertua (Datuk Ronald Kiandee) mempengerusikan\n",
        "none",
        "all",
    )
    replace(
        "29102013",
        "Dato’ Shamsul Anuar bin Haji Nasarah [Lenggong]: [Bangun\n",
        "Dato’ Shamsul Anuar bin Haji Nasarah [Lenggong]: [Bangun]\n",
        "11111 1111111 11111 111 1111 1111111 11111111111 00000000\n",
        "00000 0000000 00000 000 0000 0000000 00000000000 11111111\n",
    )
    replace(
        "19112013",
        "[Timbalan Yang di-Pertua [Datuk Ronald Kiandee) mempengerusikan\n",
        "[Timbalan Yang di-Pertua (Datuk Ronald Kiandee) mempengerusikan\n",
        "none",
        "all",
    )
    replace(
        "08112016",
        "Tuan Mohamed Hanipa bin Maidin [Sepang]: [Bangun[\n",
        "Tuan Mohamed Hanipa bin Maidin [Sepang]: [Bangun]\n",
        "1111 1111111 111111 111 111111 111111111 00000000\n",
        "0000 0000000 000000 000 000000 000000000 11111111\n",
    )
    replace(
        "16032011",
        "Beberapa Ahli: [Bangun[\n",
        "Beberapa Ahli: [Bangun]\n",
        "11111111 11111 00000000\n",
        "00000000 00000 11111111\n",
    )
    replace("18022009", "[Ketawa[\n", "[Ketawa]\n", "none", "all")
    replace(
        "21102009",
        "Tuan Masir Kujat [Sri Aman]: [Bangun[\n",
        "Tuan Masir Kujat [Sri Aman]: [Bangun]\n",
        "1111 11111 11111 1111 111111 00000000\n",
        "0000 00000 00000 0000 000000 11111111\n",
    )
    replace("09042015", "12.35 pg\n", "12.35 mlm\n", "all", "none")


if __name__ == "__main__":
    edit_hansards()
