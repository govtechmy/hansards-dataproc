"""Directly edit specific Hansards to ease tabulation
"""

import re


def read_and_replace(
    hansard_date,
    old_text_snippet,
    new_text_snippet,
    new_bold_snippet,
    new_italics_snippet,
    house,
    text,
    bold,
    italics,
    is_pipeline=False,
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
    if not is_pipeline:
        year = hansard_date[-4:]
        sortable_date = (
            f"{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}"  # YYYY-MM-DD
        )
        dir_path = f"pretabulation/{house}/{year}/{sortable_date}/"
        try:
            with open(dir_path + "plaintext.txt", "r") as f:
                text = f.readlines()
            with open(dir_path + "bold.txt", "r") as f:
                bold = f.readlines()
            with open(dir_path + "italics.txt", "r") as f:
                italics = f.readlines()

            text, bold, italics, num_edits = replace(
                old_text_snippet,
                new_text_snippet,
                new_bold_snippet,
                new_italics_snippet,
                text,
                bold,
                italics,
            )

            with open(dir_path + "plaintext.txt", "w") as f:
                f.writelines(text)
            with open(dir_path + "bold.txt", "w") as f:
                f.writelines(bold)
            with open(dir_path + "italics.txt", "w") as f:
                f.writelines(italics)
            print(f"{hansard_date} Num changes made: {num_edits}")

        except FileNotFoundError:
            print(f"{hansard_date} not found, skipping")
    else:
        text, bold, italics, num_edits = replace(
            old_text_snippet,
            new_text_snippet,
            new_bold_snippet,
            new_italics_snippet,
            text,
            bold,
            italics,
        )
        return text, bold, italics, num_edits


def replace(
    old_text_snippet,
    new_text_snippet,
    new_bold_snippet,
    new_italics_snippet,
    text,
    bold,
    italics,
):
    num_edits = 0
    for idx in range(len(text)):
        if old_text_snippet == text[idx]:
            # get the starting index where the match begins
            text[idx] = new_text_snippet
            bold[idx] = new_bold_snippet
            italics[idx] = new_italics_snippet
            num_edits += 1
    return text, bold, italics, num_edits


def edit_hansards(
    house, date=None, text=None, bold=None, italics=None, is_pipeline=False
):
    num_edits = 0
    if house.upper() == "DR":
        text, bold, italics, num_edits = edit_dr_hansards(
            house, date, text, bold, italics, is_pipeline
        )
    elif house.upper() == "DN":
        text, bold, italics, num_edits = edit_dn_hansards(
            house, date, text, bold, italics, is_pipeline
        )
    elif house.upper() == "KKDR":
        text, bold, italics, num_edits = edit_kk_hansards(
            house, date, text, bold, italics, is_pipeline
        )

    return text, bold, italics, num_edits


def edit_kk_hansards(
    house, date=None, text=None, bold=None, italics=None, is_pipeline=False
):

    modifications = {
        "31102023": [
            {
                "old_text_snippet": "Khususnya ꟷ selama ini kita mengusahakan tanaman kelapa sawit dan juga\n",
                "new_text_snippet": "Khususnya - selama ini kita mengusahakan tanaman kelapa sawit dan juga\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "none",
                "date": "31102023",
            }
        ],
        "02122021": [
            {
                "old_text_snippet": "Pertua, kalau saya hendak buatDato Sri Alexander Nanta Linggi: Tuan Yang di-\n",
                "new_text_snippet": "",
                "new_bold_snippet": "none",
                "new_italics_snippet": "none",
                "date": "02122021",
            }
        ],
        "15062023": [
            {
                "old_text_snippet": "Timbalan Menteri Sumber Asli, Alam Sekitar dan Perubahan Iklim, Dato’\n",
                "new_text_snippet": "Timbalan Menteri Sumber Asli, Alam Sekitar dan Perubahan Iklim [Dato'\n",
                "new_bold_snippet": "all",
                "new_italics_snippet": "none",
                "date": "15062023",
            },
            {
                "old_text_snippet": "Sri Huang Tiong Sii: Terima kasih Tuan Yang Di-Pertua dan terima kasih Yang\n",
                "new_text_snippet": "Sri Huang Tiong Sii]: Terima kasih Tuan Yang Di-Pertua dan terima kasih Yang\n",
                "new_bold_snippet": "111 11111 11111 11111 000000 00000 0000 0000 000000000 000 000000 00000 0000\n",
                "new_italics_snippet": "none",
                "date": "15062023",
            },
            {
                "old_text_snippet": "Timbalan Menteri Sumber Manusia, Tuan Mustapha @ Mohd Yunus bin\n",
                "new_text_snippet": "Timbalan Menteri Sumber Manusia [Tuan Mustapha @ Mohd Yunus bin\n",
                "new_bold_snippet": "all",
                "new_italics_snippet": "none",
                "date": "15062023",
            },
            {
                "old_text_snippet": "Sakmud: Terima kasih Tuan Yang di-Pertua. Bismillahi Rahmani Rahim,\n",
                "new_text_snippet": "Sakmud]: Terima kasih Tuan Yang di-Pertua. Bismillahi Rahmani Rahim,\n",
                "new_bold_snippet": "11111111 000000 00000 0000 0000 0000000000 0000000000 0000000 000000\n",
                "new_italics_snippet": "00000000 000000 00000 0000 0000 0000000000 1111111111 1111111 111111\n",
                "date": "15062023",
            },
            {
                "old_text_snippet": "Sakmud: Almarhum...\n",
                "new_text_snippet": "Sakmud]: Almarhum...\n",
                "new_bold_snippet": "11111111 00000000000\n",
                "new_italics_snippet": "none",
                "date": "15062023",
            },
            {
                "old_text_snippet": "Sakmud: Okey, jadi daripada peringkat Kementerian Sumber Manusia memang kita\n",
                "new_text_snippet": "Sakmud]: Okey, jadi daripada peringkat Kementerian Sumber Manusia memang kita\n",
                "new_bold_snippet": "11111111 00000 0000 00000000 000000000 00000000000 000000 0000000 000000 0000\n",
                "new_italics_snippet": "none",
                "date": "15062023",
            },
        ],
        "27112019": [
            {
                "old_text_snippet": "Timbalan Menteri Kewangan (Dato’ Haji Amiruddin bin Hamzah]: Terima kasih Tuan\n",
                "new_text_snippet": "Timbalan Menteri Kewangan [Dato’ Haji Amiruddin bin Hamzah]: Terima kasih Tuan\n",
                "new_bold_snippet": "11111111 1111111 11111111 111111 1111 111111111 111 11111111 000000 00000 0000\n",
                "new_italics_snippet": "none",
                "date": "27112019",
            }
        ],
        "12062023": [
            {
                "old_text_snippet": "Timbalan Menteri Dalam Negeri, Datuk Seri Dr. Shamsul Anuar bin\n",
                "new_text_snippet": "Timbalan Menteri Dalam Negeri [Datuk Seri Dr. Shamsul Anuar bin\n",
                "new_bold_snippet": "all",
                "new_italics_snippet": "none",
                "date": "12062023",
            },
            {
                "old_text_snippet": "Nasarah: Terima kasih Tuan Yang di-Pertua, terima Yang Berhormat Mersing.\n",
                "new_text_snippet": "Nasarah]: Terima kasih Tuan Yang di-Pertua, terima Yang Berhormat Mersing.\n",
                "new_bold_snippet": "111111111 000000 00000 0000 0000 0000000000 000000 0000 000000000 00000000\n",
                "new_italics_snippet": "none",
                "date": "12062023",
            },
        ],
        "04072024": [
            {
                "old_text_snippet": "Timbalan Menteri di Jabatan Perdana Menteri (Hal Ehwal Agama), Dr.\n",
                "new_text_snippet": "Timbalan Menteri di Jabatan Perdana Menteri (Hal Ehwal Agama) [Dr.\n",
                "new_bold_snippet": "all",
                "new_italics_snippet": "none",
                "date": "04072024",
            },
            {
                "old_text_snippet": "Zulkifli bin Hasan [Senator]: Assalamualaikum warahmatullahi wabarakatuh dan\n",
                "new_text_snippet": "Zulkifli bin Hasan]: Assalamualaikum warahmatullahi wabarakatuh dan\n",
                "new_bold_snippet": "11111111 111 1111111 000000000000000 00000000000000 00000000000 000\n",
                "new_italics_snippet": "none",
                "date": "04072024",
            },
        ],
        # "15072024": [
        #     {
        #         "old_text_snippet": "Berhormat Jasin.\n",
        #         "new_text_snippet": "Berhormat Jasin.\n",
        #         "new_bold_snippet": "none",
        #         "new_italics_snippet": "none",
        #         "date": "15072024",
        #     },
        # ],
    }

    if date:
        modifications = modifications.get(date, [])
    else:
        # flatten and run all
        modifications = [item for sublist in modifications.values() for item in sublist]

    num_edits = 0
    for modification in modifications:
        print(f"Editing hansards: {modification}")
        text, bold, italics, num_edits = read_and_replace(
            modification["date"],
            modification["old_text_snippet"],
            modification["new_text_snippet"],
            modification["new_bold_snippet"],
            modification["new_italics_snippet"],
            house,
            text,
            bold,
            italics,
            is_pipeline=is_pipeline,
        )

    return text, bold, italics, num_edits


def edit_dr_hansards(
    house, date=None, text=None, bold=None, italics=None, is_pipeline=False
):
    modifications = {
        "09122024": [
            {
                "old_text_snippet": "[Mesyuarat ditempohkan pada pukul 5.39 petang\n",
                "new_text_snippet": "[Mesyuarat ditempohkan pada pukul 5.39 petang]\n",
                "new_bold_snippet": "all",
                "new_italics_snippet": "all",
                "date": "09122024",
            }
        ],
        "08112023": [
            {
                "old_text_snippet": "Institusi) Tuan Ramkarpal Singh a/l Karpal Singh]: Terima kasih Tuan Yang di-Pertua.\n",
                "new_text_snippet": "Institusi) [Tuan Ramkarpal Singh a/l Karpal Singh]: Terima kasih Tuan Yang di-Pertua.\n",
                "new_bold_snippet": "1111111111 1111 111111111 11111 111 111111 11111111 000000 00000 0000 0000 0000000000\n",
                "new_italics_snippet": "none",
                "date": "08112023",
            }
        ],
        "02112023": [
            {
                "old_text_snippet": "Ahmad Fakhruddin bin Fakhrurazi [Kuala Kedah]: Dato' Yang di-Pertua, sebelum\n",
                "new_text_snippet": "Dr. Ahmad Fakhruddin bin Fakhrurazi [Kuala Kedah]: Dato' Yang di-Pertua, sebelum\n",
                "new_bold_snippet": "111 11111 1111111111 111 1111111111 111111 1111111 00000 0000 0000000000 0000000\n",
                "new_italics_snippet": "none",
                "date": "02112023",
            }
        ],
        "24102023": [
            {
                "old_text_snippet": "Seri Dr. Shahidan bin Kassim [Arau]: Okey, yang pertamanya ingin saya Tuan\n",
                "new_text_snippet": "Datuk Seri Dr. Shahidan bin Kassim [Arau]: Okey, yang pertamanya ingin saya Tuan\n",
                "new_bold_snippet": "11111 1111 111 11111111 111 111111 1111111 00000 0000 0000000000 00000 0000 0000\n",
                "new_italics_snippet": "none",
                "date": "24102023",
            }
        ],
        "06112023": [
            {
                "old_text_snippet": "Tugas-tugas Khas) Datuk Ugak anak Kumbong: Terima kasih Puan Timbalan Pengerusi.\n",
                "new_text_snippet": "Tugas-tugas Khas) [Datuk Ugak anak Kumbong]: Terima kasih Puan Timbalan Pengerusi.\n",
                "new_bold_snippet": "11111111111 11111 111111 1111 1111 111111111 000000 00000 0000 00000000 0000000000\n",
                "new_italics_snippet": "none",
                "date": "06112023",
            }
        ],
        "31102023": [
            {
                "old_text_snippet": "[Dato’ Seri Azalina Othman Said]: Bismillahi Rahmani Rahim, Tuan Yang di-Pertua,\n",
                "new_text_snippet": "",
                "new_bold_snippet": "none",
                "new_italics_snippet": "none",
                "date": "31102023",
            },
            {
                "old_text_snippet": "Menteri di Jabatan Perdana Menteri (Undang-undang dan Reformasi Institusi)\n",
                "new_text_snippet": "Menteri di Jabatan Perdana Menteri (Undang-undang dan Reformasi Institusi) [Dato’ Seri Azalina Othman Said]: Bismillahi Rahmani Rahim, Tuan Yang di-Pertua,\n",
                "new_bold_snippet": "1111111 11 1111111 1111111 1111111 11111111111111 111 111111111 1111111111 111111 1111 1111111 111111 111111 0000000000 0000000 000000 0000 0000 0000000000\n",
                "new_italics_snippet": "0000000 00 0000000 0000000 0000000 00000000000000 000 000000000 0000000000 000000 0000 0000000 000000 000000 1111111111 1111111 111110 0000 0000 0000000000\n",
                "date": "31102023",
            },
        ],
        "30102023": [
            {
                "old_text_snippet": "[Dato’ Sri Azalina Othman Said]: Terima kasih Tuan Speaker. Bismillahi Rahmani Rahim,\n",
                "new_text_snippet": "",
                "new_bold_snippet": "none",
                "new_italics_snippet": "none",
                "date": "30102023",
            },
            {
                "old_text_snippet": "Menteri di Jabatan Perdana Menteri (Undang-undang dan Reformasi Institusi)\n",
                "new_text_snippet": "Menteri di Jabatan Perdana Menteri (Undang-undang dan Reformasi Institusi) [Dato’ Seri Azalina Othman Said]: Terima kasih Tuan Speaker. Bismillahi Rahmani Rahim,\n",
                "new_bold_snippet": "1111111 11 1111111 1111111 1111111 11111111111111 111 111111111 1111111111 111111 1111 1111111 111111 111111 000000 00000 0000 00000000 0000000000 0000000 000000\n",
                "new_italics_snippet": "0000000 00 0000000 0000000 0000000 00000000000000 000 000000000 0000000000 000000 0000 0000000 000000 000000 000000 00000 0000 00000000 1111111111 1111111 111111\n",
                "date": "30102023",
            },
        ],
        "20072022": [
            {
                "old_text_snippet": "Tuan Pengerusi [Dato’ Ramli bin Dato’ Mohd Nor [Cameron Highlands)]: Ada\n",
                "new_text_snippet": "Tuan Pengerusi [Dato’ Ramli bin Dato’ Mohd Nor (Cameron Highlands)]: Ada\n",
                "new_bold_snippet": "1111 111111111 111111 11111 111 11111 1111 111 11111111 111111111111 000\n",
                "new_italics_snippet": "0000 000000000 000000 00000 000 00000 0000 000 00000000 000000000000 000\n",
                "date": "20072022",
            },
            {
                "old_text_snippet": "undang.\n",
                "new_text_snippet": "undang.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "20072022",
            },
        ],
        "16082018": [
            {
                "old_text_snippet": "Tuan Noor Amin bin Ahmad [Kangar] Tuan Noor Amin bin Ahmad [Kangar]:\n",
                "new_text_snippet": "Tuan Noor Amin bin Ahmad [Kangar]:\n",
                "new_bold_snippet": "1111 1111 1111 111 11111 111111111\n",
                "new_italics_snippet": "0000 0000 0000 000 00000 000000000\n",
                "date": "16082018",
            },
            {
                "old_text_snippet": "[[Mesyuarat ditempohkan pada pukul 1.00 tengah hari]\n",
                "new_text_snippet": "[Mesyuarat ditempohkan pada pukul 1.00 tengah hari]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "16082018",
            },
            {
                "old_text_snippet": "[“Bahawa mengikut Peraturan Mesyuarat 86(5), maka Penyata\n",
                "new_text_snippet": "“Bahawa mengikut Peraturan Mesyuarat 86(5), maka Penyata\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "16082018",
            },
        ],
        "06082018": [
            {
                "old_text_snippet": "Dato’ Dr. Noor Azmi bin Ghazali [Bagan Serai Ok.\n",
                "new_text_snippet": "Dato’ Dr. Noor Azmi bin Ghazali [Bagan Serai]: Ok.\n",
                "new_bold_snippet": "11111 111 1111 1111 111 1111111 111111 1111111 000\n",
                "new_italics_snippet": "00000 000 0000 0000 000 0000000 000000 0000000 000\n",
                "date": "06082018",
            },
            {
                "old_text_snippet": "Tuan Yang di-Pertua; Saya ingat Yang Berhormat Menteri sudah pun menjawab\n",
                "new_text_snippet": "Tuan Yang di-Pertua: Saya ingat Yang Berhormat Menteri sudah pun menjawab\n",
                "new_bold_snippet": "1111 1111 1111111111 0000 00000 0000 000000000 0000000 00000 000 00000000\n",
                "new_italics_snippet": "none",
                "date": "06082018",
            },
        ],
        "16072019": [
            {
                "old_text_snippet": "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa[ [Ketereh]: Yang\n",
                "new_text_snippet": "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa [Ketereh]: Yang\n",
                "new_bold_snippet": "111 111 11111 1111 11111111 1111 111111 111 1111 1111 1111111111 0000\n",
                "new_italics_snippet": "000 000 00000 0000 00000000 0000 000000 000 0000 0000 0000000000 0000\n",
                "date": "16072019",
            },
            {
                "old_text_snippet": "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa[ [Ketereh]: Apakah ini\n",
                "new_text_snippet": "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa [Ketereh]: Apakah ini\n",
                "new_bold_snippet": "111 111 11111 1111 11111111 1111 111111 111 1111 1111 1111111111 000000 000\n",
                "new_italics_snippet": "none",
                "date": "16072019",
            },
        ],
        "15102018": [
            {
                "old_text_snippet": "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa[ [Ketereh]: Terima kasih\n",
                "new_text_snippet": "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa [Ketereh]: Terima kasih\n",
                "new_bold_snippet": "111 111 11111 1111 11111111 1111 111111 111 1111 1111 1111111111 000000 00000\n",
                "new_italics_snippet": "000 000 00000 0000 00000000 0000 000000 000 0000 0000 0000000000 000000 00000\n",
                "date": "15102018",
            }
        ],
        "17112021": [
            {
                "old_text_snippet": "Timbalan Menteri Sumber Manusia [Tuan Haji Awang bin Hashim:]\n",
                "new_text_snippet": "Timbalan Menteri Sumber Manusia [Tuan Haji Awang bin Hashim]:\n",
                "new_bold_snippet": "11111111 1111111 111111 1111111 11111 1111 11111 111 11111111\n",
                "new_italics_snippet": "00000000 0000000 000000 0000000 00000 0000 00000 000 00000000\n",
                "date": "17112021",
            }
        ],
        "04082022": [
            {
                "old_text_snippet": "Tuan Pengerusi [Dato' Ramli bin Dato’ Mohd Nor [Cameron Highlands)]:\n",
                "new_text_snippet": "Tuan Pengerusi [Dato' Ramli bin Dato’ Mohd Nor (Cameron Highlands)]:\n",
                "new_bold_snippet": "1111 111111111 111111 11111 111 11111 1111 111 11111111 111111111111\n",
                "new_italics_snippet": "0000 000000000 000000 00000 000 00000 0000 000 00000000 000000000000\n",
                "date": "04082022",
            },
            {
                "old_text_snippet": "Dato’ Sri Tuan Ibrahim bin Tuan Man Untuk makluman Dewan yang mulia,\n",
                "new_text_snippet": "Dato’ Sri Tuan Ibrahim bin Tuan Man: Untuk makluman Dewan yang mulia,\n",
                "new_bold_snippet": "11111 111 1111 1111111 111 1111 1111 00000 00000000 00000 0000 000000\n",
                "new_italics_snippet": "none",
                "date": "04082022",
            },
            {
                "old_text_snippet": "RM500. Tuan Lim Guan Eng [Bagan]: Hanya itu cukai jualan sahaja?\n",
                "new_text_snippet": "RM500.\nTuan Lim Guan Eng [Bagan]: Hanya itu cukai jualan sahaja?\n",
                "new_bold_snippet": "000000\n1111 111 1111 111 11111111 00000 000 00000 000000 0000000\n",
                "new_italics_snippet": "none",
                "date": "04082022",
            },
        ],
        "14122021": [
            {
                "old_text_snippet": "Menteri Tenaga dan Sumber Asli (Datuk Seri Takiyuddin bin Hassan)]: Saya\n",
                "new_text_snippet": "Menteri Tenaga dan Sumber Asli [Datuk Seri Takiyuddin bin Hassan]: Saya\n",
                "new_bold_snippet": "1111111 111111 111 111111 1111 111111 1111 1111111111 111 11111111 0000\n",
                "new_italics_snippet": "0000000 000000 000 000000 0000 000000 0000 0000000000 000 00000000 0000\n",
                "date": "14122021",
            }
        ],
        "03032022": [
            {
                "old_text_snippet": "[Beberapa Ahli-ahli Yang Berhormat bangun]\n",
                "new_text_snippet": "[Beberapa Ahli-ahli Yang Berhormat bangun]\n",
                "new_bold_snippet": "all",
                "new_italics_snippet": "all",
                "date": "03032022",
            }
        ],
        "07032018": [
            {
                "old_text_snippet": "[Timbalan Yang di-Pertua (Datuk Seri Dr. Ronald Kiandee)\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua (Datuk Seri Dr. Ronald Kiandee)\n",
                "new_bold_snippet": "000000000 0000 000000000 000000 0000 000 000000 00000000\n",
                "new_italics_snippet": "all",
                "date": "07032018",
            }
        ],
        "22072020": [
            {
                "old_text_snippet": "Ustaz Haji Ahmad Marzuk bin Shaary [Timbalan Menteri di Jabatan\n",
                "new_text_snippet": "Timbalan Menteri di Jabatan Perdana Menteri (Hal Ehwal Agama) [Ustaz\n",
                "new_bold_snippet": "11111111 1111111 11 1111111 1111111 1111111 1111 11111 111111 111111\n",
                "new_italics_snippet": "none",
                "date": "22072020",
            },
            {
                "old_text_snippet": "Perdana Menteri (Hal Ehwal Agama)]: Bismillahi Rahmani Rahim. Tuan Yang di-\n",
                "new_text_snippet": "Haji Ahmad Marzuk bin Shaary]: Bismillahi Rahmani Rahim. Tuan Yang di-\n",
                "new_bold_snippet": "1111 11111 111111 111 11111111 0000000000 0000000 000000 0000 0000 000\n",
                "new_italics_snippet": "0000 00000 000000 000 00000000 1111111111 1111111 111111 0000 0000 000\n",
                "date": "22072020",
            },
            {
                "old_text_snippet": "Puan Teresa Kok [Puan Teresa Kok [Seputeh]: Yang Berhormat Arau mahu\n",
                "new_text_snippet": "Puan Teresa Kok [Seputeh]: Yang Berhormat Arau mahu\n",
                "new_bold_snippet": "1111 111111 111 1111111111 0000 000000000 0000 0000\n",
                "new_italics_snippet": "none",
                "date": "22072020",
            },
        ],
        "13082020": [
            {
                "old_text_snippet": "Ustaz Haji Ahmad Marzuk bin Shaary [Timbalan Menteri di Jabatan\n",
                "new_text_snippet": "Timbalan Menteri di Jabatan Perdana Menteri (Hal Ehwal Agama) [Ustaz\n",
                "new_bold_snippet": "11111111 1111111 11 1111111 1111111 1111111 1111 11111 111111 111111\n",
                "new_italics_snippet": "none",
                "date": "13082020",
            },
            {
                "old_text_snippet": "Perdana Menteri (Hal Ehwal Agama)]: Tuan Yang di-Pertua, saya menyokong.\n",
                "new_text_snippet": "Haji Ahmad Marzuk bin Shaary]: Tuan Yang di-Pertua, saya menyokong.\n",
                "new_bold_snippet": "1111 11111 111111 111 11111111 0000 0000 0000000000 0000 0000000000\n",
                "new_italics_snippet": "none",
                "date": "13082020",
            },
        ],
        "05112019": [
            {
                "old_text_snippet": "Timbalan Yang di-Pertua (Dato' Mohd Rashid Hasnon) mempengerusikan\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua (Dato' Mohd Rashid Hasnon) mempengerusikan\n",
                "new_bold_snippet": "000000000 0000 000000000 000000 0000 000000 0000000 111111111111111\n",
                "new_italics_snippet": "all",
                "date": "05112019",
            }
        ],
        "25052023": [
            {
                "old_text_snippet": "Timbalan Yang di-Pe’tua [Dato' Raml’ bin Dato' Mohd Nor]: Sebentar Yang\n",
                "new_text_snippet": "Timbalan Yang di-Pertua [Dato' Raml’ bin Dato' Mohd Nor]: Sebentar Yang\n",
                "new_bold_snippet": "11111111 1111 111111111 111111 11111 111 11111 1111 11111 00000000 0000\n",
                "new_italics_snippet": "none",
                "date": "25052023",
            }
        ],
        "28112019": [
            {
                "old_text_snippet": "[Tuan Yang di-Pertua mempengerusikan Jawatankuasa]\n",
                "new_text_snippet": "[Tuan Yang di-Pertua mempengerusikan Jawatankuasa]\n",
                "new_bold_snippet": "00000 0000 000000000 111111111111111 1111111111111\n",
                "new_italics_snippet": "all",
                "date": "28112019",
            },
            {
                "old_text_snippet": "Jasin. Tuan P. Prabakaran [Batu]: Banyak lagi hendak bahas.\n",
                "new_text_snippet": "Jasin.\nTuan P. Prabakaran [Batu]: Banyak lagi hendak bahas.\n",
                "new_bold_snippet": "000000\n1111 11 1111111111 1111111 000000 0000 000000 000000\n",
                "new_italics_snippet": "none",
                "date": "28112019",
            },
        ],
        "03102022": [
            {
                "old_text_snippet": "[Dato' Ramli bin Dato' Mohd Nor [Cameron Highlands]: Ada sesiapa Yang\n",
                "new_text_snippet": "Dato' Ramli bin Dato' Mohd Nor [Cameron Highlands]: Ada sesiapa Yang\n",
                "new_bold_snippet": "11111 11111 111 11111 1111 111 11111111 11111111111 000 0000000 0000\n",
                "new_italics_snippet": "none",
                "date": "03102022",
            }
        ],
        "21032022": [
            {
                "old_text_snippet": "Mesyuarat disambung semula pada pukul 2.30 petang]\n",
                "new_text_snippet": "[Mesyuarat disambung semula pada pukul 2.30 petang]\n",
                "new_bold_snippet": "all",
                "new_italics_snippet": "all",
                "date": "21032022",
            }
        ],
        "09102019": [
            {
                "old_text_snippet": "Menteri Sumber Manusia [Tuan M. Kulasegaran [Ipoh Barat]: Cukup Tuan Yang\n",
                "new_text_snippet": "Menteri Sumber Manusia [Tuan M. Kulasegaran [Ipoh Barat]]: Cukup Tuan Yang\n",
                "new_bold_snippet": "1111111 111111 1111111 11111 11 11111111111 11111 11111111 00000 0000 0000\n",
                "new_italics_snippet": "none",
                "date": "09102019",
            }
        ],
        "21022023": [
            {
                "old_text_snippet": "Terima kasih, saya mohon menyokong. [Tepuk]\n",
                "new_text_snippet": "Terima kasih, saya mohon menyokong. [Tepuk]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "000000 000000 0000 00000 0000000000 1111111\n",
                "date": "21022023",
            },
            {
                "old_text_snippet": "10.  Datuk Wira Haji Mohd. Anuar Mohd. Tahir [Temerloh] Datuk Wira Haji Mohd.\n",
                "new_text_snippet": "10.  Datuk Wira Haji Mohd. Anuar Mohd. Tahir [Temerloh] minta\n",
                "new_bold_snippet": "111  11111 1111 1111 11111 11111 11111 11111 1111111111 00000\n",
                "new_italics_snippet": "none",
                "date": "21022023",
            },
        ],
        "09032022": [
            {
                "old_text_snippet": "10.  Datuk Wira Haji Mohd. Anuar Mohd. Tahir [Temerloh] Datuk Wira Haji Mohd.\n",
                "new_text_snippet": "10.  Datuk Wira Haji Mohd. Anuar Mohd. Tahir [Temerloh] minta\n",
                "new_bold_snippet": "111  11111 1111 1111 11111 11111 11111 11111 1111111111 00000\n",
                "new_italics_snippet": "none",
                "date": "09032022",
            },
            {
                "old_text_snippet": "Anuar Mohd. Tahir [Temerloh] minta Menteri Tenaga dan Sumber Asli menyatakan usaha\n",
                "new_text_snippet": "Menteri Tenaga dan Sumber Asli menyatakan usaha\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "none",
                "date": "09032022",
            },
        ],
        "18112021": [
            {
                "old_text_snippet": "pembangkang. Timbalan Yang di-Pertua [Dato’ Mohd Rashid Hasnon]: Silakan\n",
                "new_text_snippet": "pembangkang.\nTimbalan Yang di-Pertua [Dato’ Mohd Rashid Hasnon]: Silakan\n",
                "new_bold_snippet": "000000000000\n11111111 1111 111111111 111111 1111 111111 11111111 0000000\n",
                "new_italics_snippet": "none",
                "date": "18112021",
            }
        ],
        "15122021": [
            {
                "old_text_snippet": "9. Datuk Zakaria bin Mohd. Edris @ Tubau [Libaran] mintra Menteri\n",
                "new_text_snippet": "9. Datuk Zakaria bin Mohd. Edris @ Tubau [Libaran] minta Menteri\n",
                "new_bold_snippet": "11 11111 1111111 111 11111 11111 1 11111 111111111 00000 0000000\n",
                "new_italics_snippet": "none",
                "date": "15122021",
            }
        ],
        "08032023": [
            {
                "old_text_snippet": "Mohd Rafizi bin Ramli: Itu DE asas sebanyak empat peratus untuk Kedah, tujuh\n",
                "new_text_snippet": "Tuan Mohd Rafizi bin Ramli: Itu DE asas sebanyak empat peratus untuk Kedah, tujuh\n",
                "new_bold_snippet": "1111 1111 111111 111 111111 000 00 0000 00000000 00000 0000000 00000 000000 00000\n",
                "new_italics_snippet": "none",
                "date": "08032023",
            }
        ],
        "07112019": [
            {
                "old_text_snippet": "Taun Pengerusi [Dato' Mohd Rashid Hasnon]: Ya, sila. Masa telah tamat terima\n",
                "new_text_snippet": "Tuan Pengerusi [Dato' Mohd Rashid Hasnon]: Ya, sila. Masa telah tamat terima\n",
                "new_bold_snippet": "1111 111111111 111111 1111 111111 11111111 000 00000 0000 00000 00000 000000\n",
                "new_italics_snippet": "none",
                "date": "07112019",
            }
        ],
        "21112019": [
            {
                "old_text_snippet": "Tuan Pengerusi [Dato’ Mohd Rashid Hasnon Tidak apa. Yang Berhormat\n",
                "new_text_snippet": "Tuan Pengerusi [Dato’ Mohd Rashid Hasnon]: Tidak apa. Yang Berhormat\n",
                "new_bold_snippet": "1111 111111111 111111 1111 111111 11111111 00000 0000 0000 000000000\n",
                "new_italics_snippet": "none",
                "date": "21112019",
            }
        ],
        "04072019": [
            {
                "old_text_snippet": "Tuan Yang di-Pertua; Yang Berhormat Parit Sulong, habis.\n",
                "new_text_snippet": "Tuan Yang di-Pertua: Yang Berhormat Parit Sulong, habis.\n",
                "new_bold_snippet": "1111 1111 1111111111 0000 000000000 00000 0000000 000000\n",
                "new_italics_snippet": "none",
                "date": "04072019",
            },
            {
                "old_text_snippet": "Tuan Yang di-Pertua; Yang Berhormat Kubang Kerian dulu.\n",
                "new_text_snippet": "Tuan Yang di-Pertua: Yang Berhormat Kubang Kerian dulu.\n",
                "new_bold_snippet": "1111 1111 1111111111 0000 000000000 000000 000000 00000\n",
                "new_italics_snippet": "none",
                "date": "04072019",
            },
            {
                "old_text_snippet": "[Timbalan Yang di-Pertua ([Dato’ Mohd Rashid Hasnon) mempengerusikan\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua (Dato’ Mohd Rashid Hasnon) mempengerusikan\n",
                "new_bold_snippet": "000000000 0000 000000000 000000 0000 000000 0000000 111111111111111\n",
                "new_italics_snippet": "all",
                "date": "04072019",
            },
        ],
        "29102019": [
            {
                "old_text_snippet": "Tan Sri Haji Noh bin Haji Omar [Tanjong Karang ...Kes terowong, saya hendak\n",
                "new_text_snippet": "Tan Sri Haji Noh bin Haji Omar [Tanjong Karang]: ...Kes terowong, saya hendak\n",
                "new_bold_snippet": "111 111 1111 111 111 1111 1111 11111111 11111111 000000 000000000 0000 000000\n",
                "new_italics_snippet": "none",
                "date": "29102019",
            }
        ],
        "23102019": [
            {
                "old_text_snippet": "Tuan Abdul Latiff bin Abdul Rahman [Kuala Krai Terima kasih Tuan Yang di-\n",
                "new_text_snippet": "Tuan Abdul Latiff bin Abdul Rahman [Kuala Krai]: Terima kasih Tuan Yang di-\n",
                "new_bold_snippet": "1111 11111 111111 111 11111 111111 111111 111111 000000 00000 0000 0000 000\n",
                "new_italics_snippet": "none",
                "date": "23102019",
            }
        ],
        "07122021": [
            {
                "old_text_snippet": "Tuan Pengeru’i [Dato' Mohd Rashid Hasnon]: Terima kasih Yang Berhormat\n",
                "new_text_snippet": "Tuan Pengerusi [Dato' Mohd Rashid Hasnon]: Terima kasih Yang Berhormat\n",
                "new_bold_snippet": "1111 111111111 111111 1111 111111 11111111 000000 00000 0000 000000000\n",
                "new_italics_snippet": "none",
                "date": "07122021",
            }
        ],
        "13122021": [
            {
                "old_text_snippet": "Tuan Pengrusi [Dato' Mohd Rashid Hasnon]: Baik, terima kasih Yang\n",
                "new_text_snippet": "Tuan Pengerusi [Dato' Mohd Rashid Hasnon]: Baik, terima kasih Yang\n",
                "new_bold_snippet": "1111 111111111 111111 1111 111111 11111111 00000 000000 00000 0000\n",
                "new_italics_snippet": "none",
                "date": "13122021",
            }
        ],
        "22112021": [
            {
                "old_text_snippet": "Menteri di Jabatan Perdana Menteri [Ekonomi) [Dato' Sri Mustapa bin\n",
                "new_text_snippet": "Menteri di Jabatan Perdana Menteri (Ekonomi) [Dato' Sri Mustapa bin\n",
                "new_bold_snippet": "1111111 11 1111111 1111111 1111111 111111111 111111 111 1111111 111\n",
                "new_italics_snippet": "none",
                "date": "22112021",
            },
            {
                "old_text_snippet": "Menteri di Jabatan Perdana Menteri (Hal Ehwal Agama) (Tuan Haji Idris bin\n",
                "new_text_snippet": "Menteri di Jabatan Perdana Menteri (Hal Ehwal Agama) [Tuan Haji Idris bin\n",
                "new_bold_snippet": "1111111 11 1111111 1111111 1111111 1111 11111 111111 11111 1111 11111 111\n",
                "new_italics_snippet": "none",
                "date": "22112021",
            },
            {
                "old_text_snippet": "Haji Ahmad): Assalamualaikum warahmatullahi wabarakatuh dan selamat petang...\n",
                "new_text_snippet": "Haji Ahmad]: Assalamualaikum warahmatullahi wabarakatuh dan selamat petang...\n",
                "new_bold_snippet": "1111 1111111 000000000000000 00000000000000 00000000000 000 0000000 000000000\n",
                "new_italics_snippet": "0000 0000000 111111111111111 11111111111111 11111111111 000 0000000 000000000\n",
                "date": "22112021",
            },
        ],
        "08112021": [
            {
                "old_text_snippet": "Tuan Yang di-Pertua; Terima kasih. Yang Berhormat Bintulu.\n",
                "new_text_snippet": "Tuan Yang di-Pertua: Terima kasih. Yang Berhormat Bintulu.\n",
                "new_bold_snippet": "1111 1111 1111111111 000000 000000 0000 000000000 00000000\n",
                "new_italics_snippet": "none",
                "date": "08112021",
            },
            {
                "old_text_snippet": "Tuan Yang di-Pertua; Terima kasih. Yang Berhormat Bintulu.\n",
                "new_text_snippet": "Tuan Yang di-Pertua: Terima kasih. Yang Berhormat Bintulu.\n",
                "new_bold_snippet": "1111 1111 1111111111 000000 000000 0000 000000000 00000000\n",
                "new_italics_snippet": "none",
                "date": "08112021",
            },
        ],
        "16102018": [
            {
                "old_text_snippet": "[Puan Zuraida binti Kamaruddin: Insya-Allah. Insya-Allah. Because a...\n",
                "new_text_snippet": "Puan Zuraida binti Kamaruddin: Insya-Allah. Insya-Allah. Because a...\n",
                "new_bold_snippet": "1111 1111111 11111 11111111111 000000000000 000000000000 0000000 0000\n",
                "new_italics_snippet": "0000 0000000 00000 00000000000 111111111111 111111111111 1111111 1111\n",
                "date": "16102018",
            }
        ],
        "26072018": [
            {
                "old_text_snippet": "Tuan Yang di-Pertua; Tidak bagi peluang?\n",
                "new_text_snippet": "Tuan Yang di-Pertua: Tidak bagi peluang?\n",
                "new_bold_snippet": "1111 1111 1111111111 00000 0000 00000000\n",
                "new_italics_snippet": "none",
                "date": "26072018",
            }
        ],
        "08122020": [
            {
                "old_text_snippet": "Tuan Yang di-Pertua; Terima kasih Yang Berhormat. Yang Berhormat-Yang\n",
                "new_text_snippet": "Tuan Yang di-Pertua: Terima kasih Yang Berhormat. Yang Berhormat-Yang\n",
                "new_bold_snippet": "1111 1111 1111111111 000000 00000 0000 0000000000 0000 00000000000000\n",
                "new_italics_snippet": "none",
                "date": "08122020",
            }
        ],
        "25082020": [
            {
                "old_text_snippet": "Menteri di Jabatan Perdana Menteri (Parlimen dan Undang-undang) Dato’\n",
                "new_text_snippet": "Menteri di Jabatan Perdana Menteri (Parlimen dan Undang-undang) [Dato’\n",
                "new_bold_snippet": "1111111 11 1111111 1111111 1111111 111111111 111 11111111111111 111111\n",
                "new_italics_snippet": "none",
                "date": "25082020",
            }
        ],
        "09072019": [
            {
                "old_text_snippet": "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa[ [Ketereh]: Terima kasih\n",
                "new_text_snippet": "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa [Ketereh]: Terima kasih\n",
                "new_bold_snippet": "111 111 11111 1111 11111111 1111 111111 111 1111 1111 1111111111 000000 00000\n",
                "new_italics_snippet": "none",
                "date": "09072019",
            },
            {
                "old_text_snippet": "Dato' Haji Salahuddin bin Ayub; Yang Berhormat Setiawangsa dan Yang\n",
                "new_text_snippet": "Dato' Haji Salahuddin bin Ayub: Yang Berhormat Setiawangsa dan Yang\n",
                "new_bold_snippet": "11111 1111 1111111111 111 11110 0000 000000000 00000000000 000 0000\n",
                "new_italics_snippet": "none",
                "date": "09072019",
            },
        ],
        "26032019": [
            {
                "old_text_snippet": "tidak? Tuan Khalid bin Abd Samad: Itu kurang bijak lah kalau guna macam itu.\n",
                "new_text_snippet": "tidak?\nTuan Khalid bin Abd Samad: Itu kurang bijak lah kalau guna macam itu.\n",
                "new_bold_snippet": "000000\n1111 111111 111 111 111111 000 000000 00000 000 00000 0000 00000 0000\n",
                "new_italics_snippet": "000000\n0000 000000 000 000 000000 000 000000 00000 000 00000 0000 00000 0000\n",
                "date": "26032019",
            }
        ],
        "18072019": [
            {
                "old_text_snippet": "Tuan Yang di-Pertua Yang Berhormat Arau, Yang Berhormat Arau sudah lebih\n",
                "new_text_snippet": "Tuan Yang di-Pertua: Yang Berhormat Arau, Yang Berhormat Arau sudah lebih\n",
                "new_bold_snippet": "1111 1111 1111111111 0000 000000000 00000 0000 000000000 0000 00000 00000\n",
                "new_italics_snippet": "none",
                "date": "18072019",
            }
        ],
        "11102019": [
            {
                "old_text_snippet": "[Tuan Yang di-Pertua mempengerusikan Mesyuarat]\n",
                "new_text_snippet": "[Tuan Yang di-Pertua mempengerusikan Mesyuarat]\n",
                "new_bold_snippet": "00000 0000 000000000 111111111111111 1111111110\n",
                "new_italics_snippet": "11111 1111 111111111 111111111111111 1111111111\n",
                "date": "11102019",
            }
        ],
        "28032019": [
            {
                "old_text_snippet": "Tuan Yang di-Pertua; Yang Berhormat Kubang Kerian dulu.\n",
                "new_text_snippet": "Tuan Yang di-Pertua: Yang Berhormat Kubang Kerian dulu.\n",
                "new_bold_snippet": "1111 1111 1111111111 0000 000000000 000000 000000 00000\n",
                "new_italics_snippet": "none",
                "date": "28032019",
            }
        ],
        "16102019": [
            {
                "old_text_snippet": "[ Timbalan Yang di-Pertua (Tuan Nga Kor Ming) mempengerusikan Mesyuarat]\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua (Tuan Nga Kor Ming) mempengerusikan Mesyuarat]\n",
                "new_bold_snippet": "000000000 0000 000000000 00000 000 000 00000 111111111111111 1111111110\n",
                "new_italics_snippet": "all",
                "date": "16102019",
            }
        ],
        "31102019": [
            {
                "old_text_snippet": "Datuk Seri Dr. Haji Dzulkefly bin Ahmad] Dalam hal perkara vape ya. Vape\n",
                "new_text_snippet": "Datuk Seri Dr. Haji Dzulkefly bin Ahmad]: Dalam hal perkara vape ya. Vape\n",
                "new_bold_snippet": "11111 1111 111 1111 111111111 111 1111111 00000 000 0000000 0000 000 0000\n",
                "new_italics_snippet": "00000 0000 000 0000 000000000 000 0000000 00000 000 0000000 1111 000 1111\n",
                "date": "31102019",
            }
        ],
        "03122019": [
            {
                "old_text_snippet": "[Dato’ Seri Dr. Shahidan bin Kassim [Arau]: No, Yang Berhormat Pasir Salak tarik\n",
                "new_text_snippet": "Dato’ Seri Dr. Shahidan bin Kassim [Arau]: No, Yang Berhormat Pasir Salak tarik\n",
                "new_bold_snippet": "11111 1111 111 11111111 111 111111 1111111 000 0000 000000000 00000 00000 00000\n",
                "new_italics_snippet": "00000 0000 000 00000000 000 000000 0000000 110 0000 000000000 00000 00000 00000\n",
                "date": "03122019",
            }
        ],
        "23072018": [
            {
                "old_text_snippet": "Timbalan Menteri Pendidikan [Puan Teo Nie Ching [Kulai]: Tuan Yang di-Pertua,\n",
                "new_text_snippet": "Timbalan Menteri Pendidikan [Puan Teo Nie Ching [Kulai]]: Tuan Yang di-Pertua,\n",
                "new_bold_snippet": "11111111 1111111 1111111111 11111 111 111 11111 111111111 0000 0000 0000000000\n",
                "new_italics_snippet": "none",
                "date": "23072018",
            }
        ],
        "12112018": [
            {
                "old_text_snippet": "Tuan Waytha Moorthy a/l Ponnusamy Terima kasih Yang Berhormat. Mengenai\n",
                "new_text_snippet": "Tuan Waytha Moorthy a/l Ponnusamy: Terima kasih Yang Berhormat. Mengenai\n",
                "new_bold_snippet": "1111 111111 1111111 111 1111111111 000000 00000 0000 0000000000 00000000\n",
                "new_italics_snippet": "none",
                "date": "12112018",
            }
        ],
        "21112018": [
            {
                "old_text_snippet": "Tuan Baru Bian Saya akan menjawab secara bertulis, Tuan Yang di-Pertua. Yang\n",
                "new_text_snippet": "Tuan Baru Bian: Saya akan menjawab secara bertulis, Tuan Yang di-Pertua. Yang\n",
                "new_bold_snippet": "1111 1111 11111 0000 0000 00000000 000000 000000000 0000 0000 0000000000 0000\n",
                "new_italics_snippet": "none",
                "date": "21112018",
            },
            {
                "old_text_snippet": "apabila saya nak tanya tentang 1MDB. [Dewan riuh\n",
                "new_text_snippet": "apabila saya nak tanya tentang 1MDB. [Dewan riuh]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "0000000 0000 000 00000 0000000 00000 111111 11111\n",
                "date": "21112018",
            },
            {
                "old_text_snippet": "senarai tersebut.”\n",
                "new_text_snippet": "senarai tersebut.”]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "21112018",
            },
        ],
        "08082018": [
            {
                "old_text_snippet": "Tuan Yang di-Pertua Yang Berhormat Johor Bahru, silakan.\n",
                "new_text_snippet": "Tuan Yang di-Pertua: Yang Berhormat Johor Bahru, silakan.\n",
                "new_bold_snippet": "1111 1111 1111111111 0000 000000000 00000 000000 00000000\n",
                "new_italics_snippet": "none",
                "date": "08082018",
            }
        ],
        "02032022": [
            {
                "old_text_snippet": "Timbalan Yang di-Pertua [Dato' Mohd Rashid Hasnon]: Timbalan Yang di-\n",
                "new_text_snippet": "Timbalan Yang di-",
                "new_bold_snippet": "11111111 1111 111",
                "new_italics_snippet": "none",
                "date": "02032022",
            }
        ],
        "26082020": [
            {
                "old_text_snippet": "[Timbalan Yang di-Pertua (Dato’ Sri Azalina Othman Said]) mempengerusikan\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua (Dato’ Sri Azalina Othman Said) mempengerusikan\n",
                "new_bold_snippet": "000000000 0000 000000000 000000 000 0000000 000000 00000 111111111111111\n",
                "new_italics_snippet": "all",
                "date": "26082020",
            }
        ],
        "12032018": [
            {
                "old_text_snippet": "[Timbalan Yang di-Pertua (Dato’ Sri Haji Ismail bin Haji Mohamed Said])\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua (Dato’ Sri Haji Ismail bin Haji Mohamed Said)\n",
                "new_bold_snippet": "000000000 0000 000000000 000000 000 0000 000000 000 0000 0000000 00000\n",
                "new_italics_snippet": "all",
                "date": "12032018",
            }
        ],
        "31072018": [
            {
                "old_text_snippet": "Dato’ Seri Dr. Wan Azizah Wan Ismail] Terima kasih Yang Berhormat Permatang\n",
                "new_text_snippet": "Dato’ Seri Dr. Wan Azizah Wan Ismail: Terima kasih Yang Berhormat Permatang\n",
                "new_bold_snippet": "11111 1111 111 111 111111 111 1111111 000000 00000 0000 000000000 000000000\n",
                "new_italics_snippet": "none",
                "date": "31072018",
            }
        ],
        "14032023": [
            {
                "old_text_snippet": "[Kepala P.14 jadi sebahagian daripada Anggaran Perbelanjaan\n",
                "new_text_snippet": "[Kepala P.14 jadi sebahagian daripada Anggaran Perbelanjaan]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "14032023",
            }
        ],
        "28032023": [
            {
                "old_text_snippet": "Mesyuarat\n",
                "new_text_snippet": "Mesyuarat]\n",
                "new_bold_snippet": "1111111110\n",
                "new_italics_snippet": "all",
                "date": "28032023",
            }
        ],
        "30032023": [
            {
                "old_text_snippet": "penyata tersebut.”\n",
                "new_text_snippet": "penyata tersebut.”]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "30032023",
            },
            {
                "old_text_snippet": "[Majlis bersidang dalam Jawatankuasa.\n",
                "new_text_snippet": "[Majlis bersidang dalam Jawatankuasa]\n",
                "new_bold_snippet": "all",
                "new_italics_snippet": "all",
                "date": "30032023",
            },
            {
                "old_text_snippet": "Dewan Rakyat. Kelvin Yii Lee Wuen [Bandar Kuching]: Bandar Kuching.\n",
                "new_text_snippet": "Dr. Kelvin Yii Lee Wuen [Bandar Kuching]: Bandar Kuching.\n",
                "new_bold_snippet": "111 111111 111 111 1111 1111111 111111111 000000 00000000\n",
                "new_italics_snippet": "none",
                "date": "30032023",
            },
        ],
        "17032022": [
            {
                "old_text_snippet": "Kelima, Parlimen yang Keempat Belas”.\n",
                "new_text_snippet": "Kelima, Parlimen yang Keempat Belas”.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "17032022",
            }
        ],
        "26072021": [
            {
                "old_text_snippet": "suara\n",
                "new_text_snippet": "suara]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "26072021",
            },
            {
                "old_text_snippet": "pembangkang. Tuan Sanisvara Nethaji Rayer a/l Rajaji [Jelutong]: Saya\n",
                "new_text_snippet": "pembangkang.\nTuan Sanisvara Nethaji Rayer a/l Rajaji [Jelutong]: Saya\n",
                "new_bold_snippet": "000000000000\n1111 111111111 1111111 11111 111 111111 11111111111 0000\n",
                "new_italics_snippet": "none",
                "date": "26072021",
            },
        ],
        "06082020": [
            {
                "old_text_snippet": "[Timbalan Yang di-Pertua [Dato’ Mohd Rashid Hasnon mempengerusikan\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua [Dato’ Mohd Rashid Hasnon] mempengerusikan\n",
                "new_bold_snippet": "000000000 0000 000000000 000000 0000 000000 0000000 111111111111111\n",
                "new_italics_snippet": "all",
                "date": "06082020",
            }
        ],
        "12082020": [
            {
                "old_text_snippet": "sebahagian daripada Jadual\n",
                "new_text_snippet": "sebahagian daripada Jadual]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "12082020",
            }
        ],
        "17082020": [
            {
                "old_text_snippet": 'kuasa pada 10 Mac 2020."\n',
                "new_text_snippet": 'kuasa pada 10 Mac 2020."]\n',
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "17082020",
            },
            {
                "old_text_snippet": "disifatkan telah berkuat kuasa pada 10 Mac 2020.”\n",
                "new_text_snippet": "disifatkan telah berkuat kuasa pada 10 Mac 2020.”]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "17082020",
            },
        ],
        "11082020": [
            {
                "old_text_snippet": 'tersebut."\n',
                "new_text_snippet": 'tersebut."]\n',
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "11082020",
            }
        ],
        "02112020": [
            {
                "old_text_snippet": "dalam firman-Nya, [Membaca Surah Quraisy) yang bermaksud, “Kerana kebiasaan aman\n",
                "new_text_snippet": "dalam firman-Nya, [Membaca Surah Quraisy] yang bermaksud, “Kerana kebiasaan aman\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "00000 00000000000 11111111 11111 11111111 0000 0000000000 1111111 111111111 1111\n",
                "date": "02112020",
            }
        ],
        "10082020": [
            {
                "old_text_snippet": "Penggal Ketiga, Parlimen Yang Keempat Belas.”\n",
                "new_text_snippet": "Penggal Ketiga, Parlimen Yang Keempat Belas.”]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "10082020",
            }
        ],
        "02042019": [
            {
                "old_text_snippet": "penyata tersebut.”\n",
                "new_text_snippet": "penyata tersebut.”]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "02042019",
            },
            {
                "old_text_snippet": "mempengerusikan Mesyuarat\n",
                "new_text_snippet": "mempengerusikan Mesyuarat]\n",
                "new_bold_snippet": "all",
                "new_italics_snippet": "all",
                "date": "02042019",
            },
        ],
        "09042019": [
            {
                "old_text_snippet": "mempengerusikan Mesyuarat\n",
                "new_text_snippet": "mempengerusikan Mesyuarat]\n",
                "new_bold_snippet": "all",
                "new_italics_snippet": "all",
                "date": "09042019",
            }
        ],
        "06122018": [
            {
                "old_text_snippet": "Tuan Yang di-Pertua: Dengan itu Ahli-ahli Yang Berhormat, Mesyuarat Dewan hari\n",
                "new_text_snippet": "]\nTuan Yang di-Pertua: Dengan itu Ahli-ahli Yang Berhormat, Mesyuarat Dewan hari\n",
                "new_bold_snippet": "0\n1111 1111 1111111111 000000 000 000000000 0000 0000000000 000000000 00000 0000\n",
                "new_italics_snippet": "none",
                "date": "06122018",
            }
        ],
        "27032018": [
            {
                "old_text_snippet": "[Masalah dikemuka bagi diputuskan, dan disetujukan.\n",
                "new_text_snippet": "[Masalah dikemuka bagi diputuskan, dan disetujukan.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "27032018",
            }
        ],
        "26032018": [
            {
                "old_text_snippet": "Timbalan Yang di-Pertua [Dato' Sri Haji Ismail bin Haji Mohamed Said]: Yang\n",
                "new_text_snippet": "]\nTimbalan Yang di-Pertua [Dato' Sri Haji Ismail bin Haji Mohamed Said]: Yang\n",
                "new_bold_snippet": "0\n11111111 1111 111111111 111111 111 1111 111111 111 1111 1111111 111111 0000\n",
                "new_italics_snippet": "none",
                "date": "26032018",
            }
        ],
        "21032023": [
            {
                "old_text_snippet": "Pertua. [Ketawa.\n",
                "new_text_snippet": "Pertua. [Ketawa]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "0000000 11111111\n",
                "date": "21032023",
            },
            {
                "old_text_snippet": "Timbalan Yang dan-Pertua [Puan Alice Lau Kiong Yieng]: Ahli-ahli Yang Berhormat,\n",
                "new_text_snippet": "Timbalan Yang di-Pertua [Puan Alice Lau Kiong Yieng]: Ahli-ahli Yang Berhormat,\n",
                "new_bold_snippet": "11111111 1111 111111111 11111 11111 111 11111 1111111 000000000 0000 0000000000\n",
                "new_italics_snippet": "none",
                "date": "21032023",
            },
        ],
        "09032023": [
            {
                "old_text_snippet": "hendaklah disahkan.”\n",
                "new_text_snippet": "hendaklah disahkan.”]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "09032023",
            }
        ],
        "28022023": [
            {
                "old_text_snippet": "Seorang Ahli Sahabat-sahabat kita.\n",
                "new_text_snippet": "Seorang Ahli: Sahabat-sahabat kita.\n",
                "new_bold_snippet": "1111111 11111 000000000000000 00000\n",
                "new_italics_snippet": "none",
                "date": "28022023",
            }
        ],
        "10122018": [
            {
                "old_text_snippet": "Pertua. Tuan Sanisvara Nethaji Rayer a/l Rajaji [Jelutong]: Yang Berhormat jangan\n",
                "new_text_snippet": "Pertua.\nTuan Sanisvara Nethaji Rayer a/l Rajaji [Jelutong]: Yang Berhormat jangan\n",
                "new_bold_snippet": "0000000\n1111 111111111 1111111 11111 111 111111 11111111111 0000 000000000 000000\n",
                "new_italics_snippet": "none",
                "date": "10122018",
            }
        ],
        "21102019": [
            {
                "old_text_snippet": "`Dato’ Sri Bung Moktar bin Radin [Kinabatangan]: Macam jadi sarapan pagi saya\n",
                "new_text_snippet": "Dato’ Sri Bung Moktar bin Radin [Kinabatangan]: Macam jadi sarapan pagi saya\n",
                "new_bold_snippet": "11111 111 1111 111111 111 11111 111111111111111 00000 0000 0000000 0000 0000\n",
                "new_italics_snippet": "none",
                "date": "21102019",
            }
        ],
        "22102019": [
            {
                "old_text_snippet": "Padang Tuan Karupaiya A/L Mutusami [Padang Serai]: Terima kasih Tuan Yang\n",
                "new_text_snippet": "Tuan Karupaiya A/L Mutusami [Padang Serai]: Terima kasih Tuan Yang\n",
                "new_bold_snippet": "1111 111111111 111 11111111 1111111 1111111 000000 00000 0000 0000\n",
                "new_italics_snippet": "none",
                "date": "22102019",
            }
        ],
        "04042019": [
            {
                "old_text_snippet": "Sri Haji Noh bin Haji Omar [Tanjong Karang]: Tuan Pengerusi, saya tidak\n",
                "new_text_snippet": "Tan Sri Haji Noh bin Haji Omar [Tanjong Karang]: Tuan Pengerusi, saya tidak\n",
                "new_bold_snippet": "111 111 1111 111 111 1111 1111 11111111 11111111 0000 0000000000 0000 00000\n",
                "new_italics_snippet": "none",
                "date": "04042019",
            }
        ],
        "21032018": [
            {
                "old_text_snippet": "sudah.Dato’ Haji Mahfuz bin Haji Omar [Pokok Sena]: ...Ini satu yang bertentangan\n",
                "new_text_snippet": "sudah.\nDato’ Haji Mahfuz bin Haji Omar [Pokok Sena]: ...Ini satu yang bertentangan\n",
                "new_bold_snippet": "000000\n11111 1111 111111 111 1111 1111 111111 111111 000000 0000 0000 000000000000\n",
                "new_italics_snippet": "none",
                "date": "21032018",
            }
        ],
        "13112018": [
            {
                "old_text_snippet": "Tuan Yang di-Pertua Yang Berhormat Kinabatangan. [Dewan riuh] Kita ikut\n",
                "new_text_snippet": "Tuan Yang di-Pertua: Yang Berhormat Kinabatangan. [Dewan riuh] Kita ikut\n",
                "new_bold_snippet": "1111 1111 1111111111 0000 000000000 0000000000000 000000 00000 0000 0000\n",
                "new_italics_snippet": "0000 0000 0000000000 0000 000000000 0000000000000 111111 11111 0000 0000\n",
                "date": "13112018",
            }
        ],
        "03122018": [
            {
                "old_text_snippet": "silakan. Datuk Seri Panglima Madius Tangau [Tuaran]: Subjek yang sama.\n",
                "new_text_snippet": "silakan.\nDatuk Seri Panglima Madius Tangau [Tuaran]: Subjek yang sama.\n",
                "new_bold_snippet": "00000000\n11111 1111 11111111 111111 111111 111111111 000000 0000 00000\n",
                "new_italics_snippet": "none",
                "date": "03122018",
            }
        ],
        "02042018": [
            {
                "old_text_snippet": "Menteri di Jabatan Perdana Menteri, Dato’ Sri Azalina Dato’ Othman Said\n",
                "new_text_snippet": "Menteri di Jabatan Perdana Menteri [Dato’ Sri Azalina Dato’ Othman Said\n",
                "new_bold_snippet": "all",
                "new_italics_snippet": "none",
                "date": "02042018",
            },
            {
                "old_text_snippet": "[Pengerang]: Terima kasih Tuan Pengerusi. Yang Berhormat Kulai, rang undang-undang ini\n",
                "new_text_snippet": "[Pengerang]]: Terima kasih Tuan Pengerusi. Yang Berhormat Kulai, rang undang-undang ini\n",
                "new_bold_snippet": "1111111111111 000000 00000 0000 0000000000 0000 000000000 000000 0000 0000000000000 000\n",
                "new_italics_snippet": "none",
                "date": "02042018",
            },
            {
                "old_text_snippet": "Menteri di Jabatan Perdana Menteri, Dato’ Sri Azalina Dato’ Othman Said\n",
                "new_text_snippet": "Menteri di Jabatan Perdana Menteri [Dato’ Sri Azalina Dato’ Othman Said\n",
                "new_bold_snippet": "all",
                "new_italics_snippet": "none",
                "date": "02042018",
            },
            {
                "old_text_snippet": "[Pengerang]: Terima kasih Tuan Pengerusi. Yang Berhormat Kulai, rang undang-undang ini\n",
                "new_text_snippet": "[Pengerang]]: Terima kasih Tuan Pengerusi. Yang Berhormat Kulai, rang undang-undang ini\n",
                "new_bold_snippet": "1111111111111 000000 00000 0000 0000000000 0000 000000000 000000 0000 0000000000000 000\n",
                "new_italics_snippet": "none",
                "date": "02042018",
            },
        ],
        "30032017": [
            {
                "old_text_snippet": "Haji Ahmad bin Haji Maslan) dan diluluskan)\n",
                "new_text_snippet": "Haji Ahmad bin Haji Maslan) dan diluluskan]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "30032017",
            },
            {
                "old_text_snippet": "Haji Ahmad bin Haji Maslan) dan diluluskan)\n",
                "new_text_snippet": "Haji Ahmad bin Haji Maslan) dan diluluskan]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "30032017",
            },
        ],
        "16112017": [
            {
                "old_text_snippet": "[Masalah dikemuka bagi diputuskan, dan disetujukan.\n",
                "new_text_snippet": "[Masalah dikemuka bagi diputuskan, dan disetujukan.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "16112017",
            },
            {
                "old_text_snippet": "[Masalah dikemuka bagi diputuskan, dan disetujukan.\n",
                "new_text_snippet": "[Masalah dikemuka bagi diputuskan, dan disetujukan.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "16112017",
            },
        ],
        "28112017": [
            {
                "old_text_snippet": "sebahagian daripada Anggaran Pembangunan 2018\n",
                "new_text_snippet": "sebahagian daripada Anggaran Pembangunan 2018]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "28112017",
            },
            {
                "old_text_snippet": "Fasal 1 hingga 2 diperintahkan jadi sebahagian daripada rang undang-undang.\n",
                "new_text_snippet": "[Fasal 1 hingga 2 diperintahkan jadi sebahagian daripada rang undang-undang.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "28112017",
            },
            {
                "old_text_snippet": "itu di ruangan enam dan tujuh senarai tersebut.”\n",
                "new_text_snippet": "itu di ruangan enam dan tujuh senarai tersebut.”]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "28112017",
            },
            {
                "old_text_snippet": "sebahagian daripada Anggaran Pembangunan 2018\n",
                "new_text_snippet": "sebahagian daripada Anggaran Pembangunan 2018]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "28112017",
            },
            {
                "old_text_snippet": "Fasal 1 hingga 2 diperintahkan jadi sebahagian daripada rang undang-undang.\n",
                "new_text_snippet": "[Fasal 1 hingga 2 diperintahkan jadi sebahagian daripada rang undang-undang.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "28112017",
            },
            {
                "old_text_snippet": "itu di ruangan enam dan tujuh senarai tersebut.”\n",
                "new_text_snippet": "itu di ruangan enam dan tujuh senarai tersebut.”]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "28112017",
            },
        ],
        "28032017": [
            {
                "old_text_snippet": "sembilan dan sepuluh penyata tersebut.” hendaklah disahkan.\n",
                "new_text_snippet": "sembilan dan sepuluh penyata tersebut.” hendaklah disahkan.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "28032017",
            },
            {
                "old_text_snippet": "sembilan dan sepuluh penyata tersebut.” hendaklah disahkan.\n",
                "new_text_snippet": "sembilan dan sepuluh penyata tersebut.” hendaklah disahkan.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "28032017",
            },
        ],
        "03042017": [
            {
                "old_text_snippet": "[Timbalan Yang di-Pertua [Datuk Seri Dr. Ronald Kiandee) mempengerusikan\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua (Datuk Seri Dr. Ronald Kiandee) mempengerusikan\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "03042017",
            },
            {
                "old_text_snippet": "[Timbalan Yang di-Pertua [Datuk Seri Dr. Ronald Kiandee) mempengerusikan\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua (Datuk Seri Dr. Ronald Kiandee) mempengerusikan\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "03042017",
            },
        ],
        "27032017": [
            {
                "old_text_snippet": "Sembilan dan sepuluh penyata tersebut.”\n",
                "new_text_snippet": "Sembilan dan sepuluh penyata tersebut.”]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "27032017",
            },
            {
                "old_text_snippet": "Sembilan dan sepuluh penyata tersebut.”\n",
                "new_text_snippet": "Sembilan dan sepuluh penyata tersebut.”]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "27032017",
            },
        ],
        "13112017": [
            {
                "old_text_snippet": "itu di ruangan enam dan tujuh senarai tersebut.”\n",
                "new_text_snippet": "itu di ruangan enam dan tujuh senarai tersebut.”]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "13112017",
            },
            {
                "old_text_snippet": "itu di ruangan enam dan tujuh senarai tersebut.”\n",
                "new_text_snippet": "itu di ruangan enam dan tujuh senarai tersebut.”]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "13112017",
            },
        ],
        "29032016": [
            {
                "old_text_snippet": "[Masalah dikemuka bagi diputuskan, dan disetujukan.\n",
                "new_text_snippet": "[Masalah dikemuka bagi diputuskan, dan disetujukan.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "29032016",
            },
            {
                "old_text_snippet": "[Masalah dikemuka bagi diputuskan, dan disetujukan.\n",
                "new_text_snippet": "[Masalah dikemuka bagi diputuskan, dan disetujukan.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "29032016",
            },
        ],
        "28032016": [
            {
                "old_text_snippet": 'penyata tersebut."\n',
                "new_text_snippet": 'penyata tersebut."]\n',
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "28032016",
            },
            {
                "old_text_snippet": 'penyata tersebut."\n',
                "new_text_snippet": 'penyata tersebut."]\n',
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "28032016",
            },
        ],
        "22112016": [
            {
                "old_text_snippet": "ditangguhkan sehingga jam 10 pagi, hari Rabu 23 November tahun 2016.\n",
                "new_text_snippet": "ditangguhkan sehingga jam 10 pagi, hari Rabu 23 November tahun 2016.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "22112016",
            },
            {
                "old_text_snippet": "ditangguhkan sehingga jam 10 pagi, hari Rabu 23 November tahun 2016.\n",
                "new_text_snippet": "ditangguhkan sehingga jam 10 pagi, hari Rabu 23 November tahun 2016.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "22112016",
            },
        ],
        "04042016": [
            {
                "old_text_snippet": "sebagai Jawatankuasa\n",
                "new_text_snippet": "sebagai Jawatankuasa]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "04042016",
            },
            {
                "old_text_snippet": "sebagai Jawatankuasa\n",
                "new_text_snippet": "sebagai Jawatankuasa]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "04042016",
            },
        ],
        "07112016": [
            {
                "old_text_snippet": "tersebut.”\n",
                "new_text_snippet": "tersebut.”]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "07112016",
            },
            {
                "old_text_snippet": "tersebut.”\n",
                "new_text_snippet": "tersebut.”]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "07112016",
            },
        ],
        "21032016": [
            {
                "old_text_snippet": "Tuan Gobind Singh Deo [Puchong]: [Bangun\n",
                "new_text_snippet": "Tuan Gobind Singh Deo [Puchong]: [Bangun]\n",
                "new_bold_snippet": "1111 111111 11111 111 1111111111 00000000\n",
                "new_italics_snippet": "0000 000000 00000 000 0000000000 11111111\n",
                "date": "21032016",
            },
            {
                "old_text_snippet": "Tuan Gobind Singh Deo [Puchong]: [Bangun\n",
                "new_text_snippet": "Tuan Gobind Singh Deo [Puchong]: [Bangun]\n",
                "new_bold_snippet": "1111 111111 11111 111 1111111111 00000000\n",
                "new_italics_snippet": "0000 000000 00000 000 0000000000 11111111\n",
                "date": "21032016",
            },
        ],
        "23112015": [
            {
                "old_text_snippet": "[Timbalan Yang di-Pertua ([Datuk Seri Dr. Ronald Kiandee)\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua (Datuk Seri Dr. Ronald Kiandee)\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "23112015",
            },
            {
                "old_text_snippet": "[Timbalan Yang di-Pertua ([Datuk Seri Dr. Ronald Kiandee)\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua (Datuk Seri Dr. Ronald Kiandee)\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "23112015",
            },
        ],
        "19112013": [
            {
                "old_text_snippet": "[Timbalan Yang di-Pertua ([Datuk Seri Dr. Ronald Kiandee)\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua (Datuk Seri Dr. Ronald Kiandee)\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "19112013",
            },
            {
                "old_text_snippet": "[Timbalan Yang di-Pertua [Datuk Ronald Kiandee) mempengerusikan\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua (Datuk Ronald Kiandee) mempengerusikan\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "19112013",
            },
            {
                "old_text_snippet": "[Timbalan Yang di-Pertua ([Datuk Seri Dr. Ronald Kiandee)\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua (Datuk Seri Dr. Ronald Kiandee)\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "19112013",
            },
            {
                "old_text_snippet": "[Timbalan Yang di-Pertua [Datuk Ronald Kiandee) mempengerusikan\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua (Datuk Ronald Kiandee) mempengerusikan\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "19112013",
            },
        ],
        "01102013": [
            {
                "old_text_snippet": "[Disampuk Jadi saya harap kita tidak payah hendak risau.\n",
                "new_text_snippet": "[Disampuk] Jadi saya harap kita tidak payah hendak risau.\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "1111111111 0000 0000 00000 0000 00000 00000 000000 000000\n",
                "date": "01102013",
            },
            {
                "old_text_snippet": "[Disampuk Jadi saya harap kita tidak payah hendak risau.\n",
                "new_text_snippet": "[Disampuk] Jadi saya harap kita tidak payah hendak risau.\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "1111111111 0000 0000 00000 0000 00000 00000 000000 000000\n",
                "date": "01102013",
            },
        ],
        "20112013": [
            {
                "old_text_snippet": "[Timbalan Yang di-Pertua [Datuk Ronald Kiandee) mempengerusikan\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua (Datuk Ronald Kiandee) mempengerusikan\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "20112013",
            },
            {
                "old_text_snippet": "[Timbalan Yang di-Pertua [Datuk Ronald Kiandee) mempengerusikan\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua (Datuk Ronald Kiandee) mempengerusikan\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "20112013",
            },
        ],
        "18042012": [
            {
                "old_text_snippet": "[[Fasal-fasal 1 hingga 34 dikemukakan kepada Jawatankuasa]\n",
                "new_text_snippet": "[Fasal-fasal 1 hingga 34 dikemukakan kepada Jawatankuasa]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "18042012",
            },
            {
                "old_text_snippet": "[[Fasal-fasal 1 hingga 34 dikemukakan kepada Jawatankuasa]\n",
                "new_text_snippet": "[Fasal-fasal 1 hingga 34 dikemukakan kepada Jawatankuasa]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "18042012",
            },
        ],
        "02102012": [
            {
                "old_text_snippet": "Tuan N. Gobalakrishnan [Padang Serai]: [Bangun\n",
                "new_text_snippet": "Tuan N. Gobalakrishnan [Padang Serai]: [Bangun]\n",
                "new_bold_snippet": "1111 11 11111111111111 1111111 1111111 00000000\n",
                "new_italics_snippet": "0000 00 00000000000000 0000000 0000000 11111111\n",
                "date": "02102012",
            },
            {
                "old_text_snippet": "Tuan N. Gobalakrishnan [Padang Serai]: [Bangun\n",
                "new_text_snippet": "Tuan N. Gobalakrishnan [Padang Serai]: [Bangun]\n",
                "new_bold_snippet": "1111 11 11111111111111 1111111 1111111 00000000\n",
                "new_italics_snippet": "0000 00 00000000000000 0000000 0000000 11111111\n",
                "date": "02102012",
            },
        ],
        "09042012": [
            {
                "old_text_snippet": "sebahagian daripada Jadual.\n",
                "new_text_snippet": "sebahagian daripada Jadual.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "09042012",
            },
            {
                "old_text_snippet": "sebahagian daripada Jadual.\n",
                "new_text_snippet": "sebahagian daripada Jadual.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "09042012",
            },
            {
                "old_text_snippet": "sebahagian daripada Jadual.\n",
                "new_text_snippet": "sebahagian daripada Jadual.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "09042012",
            },
            {
                "old_text_snippet": "sebahagian daripada Jadual.\n",
                "new_text_snippet": "sebahagian daripada Jadual.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "09042012",
            },
        ],
        "04042012": [
            {
                "old_text_snippet": "ini. [Dewan\n",
                "new_text_snippet": "ini. [Dewan]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "0000 1111111\n",
                "date": "04042012",
            },
            {
                "old_text_snippet": "ini. [Dewan\n",
                "new_text_snippet": "ini. [Dewan]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "0000 1111111\n",
                "date": "04042012",
            },
        ],
        "28102015": [
            {
                "old_text_snippet": "[Ketawa Yang Berhormat Kuala Terengganu.\n",
                "new_text_snippet": "[Ketawa] Yang Berhormat Kuala Terengganu.\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "11111111 0000 000000000 00000 00000000000\n",
                "date": "28102015",
            },
            {
                "old_text_snippet": "[Ketawa Yang Berhormat Kuala Terengganu.\n",
                "new_text_snippet": "[Ketawa] Yang Berhormat Kuala Terengganu.\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "11111111 0000 000000000 00000 00000000000\n",
                "date": "28102015",
            },
        ],
        "30032015": [
            {
                "old_text_snippet": "Jawatankuasa sebuah-buah Majlis”.\n",
                "new_text_snippet": "Jawatankuasa sebuah-buah Majlis”.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "30032015",
            },
            {
                "old_text_snippet": "Jawatankuasa sebuah-buah Majlis”.\n",
                "new_text_snippet": "Jawatankuasa sebuah-buah Majlis”.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "30032015",
            },
            {
                "old_text_snippet": "Jawatankuasa sebuah-buah Majlis”.\n",
                "new_text_snippet": "Jawatankuasa sebuah-buah Majlis”.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "30032015",
            },
            {
                "old_text_snippet": "Jawatankuasa sebuah-buah Majlis”.\n",
                "new_text_snippet": "Jawatankuasa sebuah-buah Majlis”.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "30032015",
            },
        ],
        "06042015": [
            {
                "old_text_snippet": "[Timbalan Yang di-Pertua ([Datuk Seri Dr. Ronald Kiandee) mempengerusikan\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua (Datuk Seri Dr. Ronald Kiandee) mempengerusikan\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "06042015",
            },
            {
                "old_text_snippet": "[Timbalan Yang di-Pertua ([Datuk Seri Dr. Ronald Kiandee) mempengerusikan\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua (Datuk Seri Dr. Ronald Kiandee) mempengerusikan\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "06042015",
            },
            {
                "old_text_snippet": "Beberapa Ahli: [Bercakap tanpa menggunakan pembesar suara\n",
                "new_text_snippet": "Beberapa Ahli: [Bercakap tanpa menggunakan pembesar suara]\n",
                "new_bold_snippet": "11111111 11111 000000000 00000 00000000000 00000000 000000\n",
                "new_italics_snippet": "00000000 00000 111111111 11111 11111111111 11111111 111111\n",
                "date": "06042015",
            },
            {
                "old_text_snippet": "[Timbalan Yang di-Pertua ([Datuk Seri Dr. Ronald Kiandee) mempengerusikan\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua (Datuk Seri Dr. Ronald Kiandee) mempengerusikan\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "06042015",
            },
            {
                "old_text_snippet": "[Timbalan Yang di-Pertua ([Datuk Seri Dr. Ronald Kiandee) mempengerusikan\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua (Datuk Seri Dr. Ronald Kiandee) mempengerusikan\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "06042015",
            },
            {
                "old_text_snippet": "Beberapa Ahli: [Bercakap tanpa menggunakan pembesar suara\n",
                "new_text_snippet": "Beberapa Ahli: [Bercakap tanpa menggunakan pembesar suara]\n",
                "new_bold_snippet": "11111111 11111 000000000 00000 00000000000 00000000 000000\n",
                "new_italics_snippet": "00000000 00000 111111111 11111 11111111111 11111111 111111\n",
                "date": "06042015",
            },
        ],
        "24112015": [
            {
                "old_text_snippet": "[Masalah dikemuka bagi diputuskan, dan disetujukan.\n",
                "new_text_snippet": "[Masalah dikemuka bagi diputuskan, dan disetujukan.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "24112015",
            },
            {
                "old_text_snippet": "[Masalah dikemuka bagi diputuskan, dan disetujukan.\n",
                "new_text_snippet": "[Masalah dikemuka bagi diputuskan, dan disetujukan.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "24112015",
            },
        ],
        "09042015": [
            {
                "old_text_snippet": "bahagian dia terangkan... [Disampuk Itu sekejap lagi saya akan sambut. Saya rasa benda\n",
                "new_text_snippet": "bahagian dia terangkan... [Disampuk] Itu sekejap lagi saya akan sambut. Saya rasa benda\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "00000000 000 000000000000 1111111111 000 0000000 0000 0000 0000 0000000 0000 0000 00000\n",
                "date": "09042015",
            },
            {
                "old_text_snippet": "12.35 pg\n",
                "new_text_snippet": "12.35 mlm\n",
                "new_bold_snippet": "all",
                "new_italics_snippet": "none",
                "date": "09042015",
            },
            {
                "old_text_snippet": "bahagian dia terangkan... [Disampuk Itu sekejap lagi saya akan sambut. Saya rasa benda\n",
                "new_text_snippet": "bahagian dia terangkan... [Disampuk] Itu sekejap lagi saya akan sambut. Saya rasa benda\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "00000000 000 000000000000 1111111111 000 0000000 0000 0000 0000 0000000 0000 0000 00000\n",
                "date": "09042015",
            },
            {
                "old_text_snippet": "12.35 pg\n",
                "new_text_snippet": "12.35 mlm\n",
                "new_bold_snippet": "all",
                "new_italics_snippet": "none",
                "date": "09042015",
            },
        ],
        "31032014": [
            {
                "old_text_snippet": "dan butiran projek dalam ruang sembilan dan sepuluh penyata tersebut”.\n",
                "new_text_snippet": "dan butiran projek dalam ruang sembilan dan sepuluh penyata tersebut”.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "31032014",
            },
            {
                "old_text_snippet": "dan butiran projek dalam ruang sembilan dan sepuluh penyata tersebut”.\n",
                "new_text_snippet": "dan butiran projek dalam ruang sembilan dan sepuluh penyata tersebut”.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "31032014",
            },
        ],
        "18112014": [
            {
                "old_text_snippet": "[Masalah dikemuka bagi diputuskan, dan disetujukan.\n",
                "new_text_snippet": "[Masalah dikemuka bagi diputuskan, dan disetujukan.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "18112014",
            },
            {
                "old_text_snippet": "[Masalah dikemuka bagi diputuskan, dan disetujukan.\n",
                "new_text_snippet": "[Masalah dikemuka bagi diputuskan, dan disetujukan.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "18112014",
            },
            {
                "old_text_snippet": "[Masalah dikemuka bagi diputuskan, dan disetujukan.\n",
                "new_text_snippet": "[Masalah dikemuka bagi diputuskan, dan disetujukan.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "18112014",
            },
            {
                "old_text_snippet": "[Masalah dikemuka bagi diputuskan, dan disetujukan.\n",
                "new_text_snippet": "[Masalah dikemuka bagi diputuskan, dan disetujukan.]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "18112014",
            },
        ],
        "25112013": [
            {
                "old_text_snippet": "[Tuan Pengerusi [Dato’ Haji Ismail bin Haji Mohamed Said) mempengerusikan\n",
                "new_text_snippet": "[Tuan Pengerusi (Dato’ Haji Ismail bin Haji Mohamed Said) mempengerusikan\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "25112013",
            },
            {
                "old_text_snippet": "[Tuan Pengerusi [Dato’ Haji Ismail bin Haji Mohamed Said) mempengerusikan\n",
                "new_text_snippet": "[Tuan Pengerusi (Dato’ Haji Ismail bin Haji Mohamed Said) mempengerusikan\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "25112013",
            },
        ],
        "03122013": [
            {
                "old_text_snippet": "itu di ruangan enam dan tujuh senarai tersebut.”\n",
                "new_text_snippet": "itu di ruangan enam dan tujuh senarai tersebut.”]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "03122013",
            },
            {
                "old_text_snippet": "itu di ruangan enam dan tujuh senarai tersebut.”\n",
                "new_text_snippet": "itu di ruangan enam dan tujuh senarai tersebut.”]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "03122013",
            },
        ],
        "04122013": [
            {
                "old_text_snippet": "[Timbalan Yang di-Pertua [Datuk Ronald Kiandee) mempengerusikan\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua (Datuk Ronald Kiandee) mempengerusikan\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "04122013",
            },
            {
                "old_text_snippet": "[Timbalan Yang di-Pertua [Datuk Ronald Kiandee) mempengerusikan\n",
                "new_text_snippet": "[Timbalan Yang di-Pertua (Datuk Ronald Kiandee) mempengerusikan\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "04122013",
            },
        ],
        "29102013": [
            {
                "old_text_snippet": "Dato’ Shamsul Anuar bin Haji Nasarah [Lenggong]: [Bangun\n",
                "new_text_snippet": "Dato’ Shamsul Anuar bin Haji Nasarah [Lenggong]: [Bangun]\n",
                "new_bold_snippet": "11111 1111111 11111 111 1111 1111111 11111111111 00000000\n",
                "new_italics_snippet": "00000 0000000 00000 000 0000 0000000 00000000000 11111111\n",
                "date": "29102013",
            },
            {
                "old_text_snippet": "Dato’ Shamsul Anuar bin Haji Nasarah [Lenggong]: [Bangun\n",
                "new_text_snippet": "Dato’ Shamsul Anuar bin Haji Nasarah [Lenggong]: [Bangun]\n",
                "new_bold_snippet": "11111 1111111 11111 111 1111 1111111 11111111111 00000000\n",
                "new_italics_snippet": "00000 0000000 00000 000 0000 0000000 00000000000 11111111\n",
                "date": "29102013",
            },
        ],
        "08112016": [
            {
                "old_text_snippet": "Tuan Mohamed Hanipa bin Maidin [Sepang]: [Bangun[\n",
                "new_text_snippet": "Tuan Mohamed Hanipa bin Maidin [Sepang]: [Bangun]\n",
                "new_bold_snippet": "1111 1111111 111111 111 111111 111111111 00000000\n",
                "new_italics_snippet": "0000 0000000 000000 000 000000 000000000 11111111\n",
                "date": "08112016",
            },
            {
                "old_text_snippet": "Tuan Mohamed Hanipa bin Maidin [Sepang]: [Bangun[\n",
                "new_text_snippet": "Tuan Mohamed Hanipa bin Maidin [Sepang]: [Bangun]\n",
                "new_bold_snippet": "1111 1111111 111111 111 111111 111111111 00000000\n",
                "new_italics_snippet": "0000 0000000 000000 000 000000 000000000 11111111\n",
                "date": "08112016",
            },
        ],
        "16032011": [
            {
                "old_text_snippet": "Beberapa Ahli: [Bangun[\n",
                "new_text_snippet": "Beberapa Ahli: [Bangun]\n",
                "new_bold_snippet": "11111111 11111 00000000\n",
                "new_italics_snippet": "00000000 00000 11111111\n",
                "date": "16032011",
            },
            {
                "old_text_snippet": "Beberapa Ahli: [Bangun[\n",
                "new_text_snippet": "Beberapa Ahli: [Bangun]\n",
                "new_bold_snippet": "11111111 11111 00000000\n",
                "new_italics_snippet": "00000000 00000 11111111\n",
                "date": "16032011",
            },
        ],
        "18022009": [
            {
                "old_text_snippet": "[Ketawa[\n",
                "new_text_snippet": "[Ketawa]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "18022009",
            },
            {
                "old_text_snippet": "[Ketawa[\n",
                "new_text_snippet": "[Ketawa]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "all",
                "date": "18022009",
            },
        ],
        "21102009": [
            {
                "old_text_snippet": "Tuan Masir Kujat [Sri Aman]: [Bangun[\n",
                "new_text_snippet": "Tuan Masir Kujat [Sri Aman]: [Bangun]\n",
                "new_bold_snippet": "1111 11111 11111 1111 111111 00000000\n",
                "new_italics_snippet": "0000 00000 00000 0000 000000 11111111\n",
                "date": "21102009",
            },
            {
                "old_text_snippet": "Tuan Masir Kujat [Sri Aman]: [Bangun[\n",
                "new_text_snippet": "Tuan Masir Kujat [Sri Aman]: [Bangun]\n",
                "new_bold_snippet": "1111 11111 11111 1111 111111 00000000\n",
                "new_italics_snippet": "0000 00000 00000 0000 000000 11111111\n",
                "date": "21102009",
            },
        ],
        "11102021": [
            {
                "old_text_snippet": "Menteri di Jabatan Perdana Menteri (Parlimen dan Undang-undang) Dato’\n",
                "new_text_snippet": "Menteri di Jabatan Perdana Menteri (Parlimen dan Undang-undang) [Dato’\n",
                "new_bold_snippet": "all",
                "new_italics_snippet": "none",
                "date": "11102021",
            },
            {
                "old_text_snippet": "Sri Dr. Haji Wan Junaidi bin Tuanku Jaafar: Tuan Yang di-Pertua, saya mohon\n",
                "new_text_snippet": "Sri Dr. Haji Wan Junaidi bin Tuanku Jaafar]: Tuan Yang di-Pertua, saya mohon\n",
                "new_bold_snippet": "111 111 1111 111 1111111 111 111111 11111111 0000 0000 0000000000 0000 00000\n",
                "new_italics_snippet": "none",
                "date": "11102021",
            },
        ],
        "07122020": [
            {
                "old_text_snippet": "Dato' Takiyuddin bin Hassan [Menteri di Jabatan Perdana Menteri\n",
                "new_text_snippet": "Menteri di Jabatan Perdana Menteri (Parlimen dan Undang-undang) [Dato' Takiyuddin bin Hassan]:\n'",
                "new_bold_snippet": "all",
                "new_italics_snippet": "none",
                "date": "07122020",
            },
            {
                "old_text_snippet": "(Parlimen dan Undang-undang)]: Yang Berhormat Tuan Yang di-Pertua;\n",
                "new_text_snippet": "Yang Berhormat Tuan Yang di-Pertua;\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "none",
                "date": "07122020",
            },
        ],
        "19102023": [
            {
                "old_text_snippet": "(Parlimen dan Undang-undang)]: Yang Berhormat Tuan Yang di-Pertua;\n",
                "new_text_snippet": "Yang Berhormat Tuan Yang di-Pertua;\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "none",
                "date": "19102023",
            },
            {
                "old_text_snippet": "Datuk Ahmad Marzuk bin Shaary [Pengkalan Chepa]: Yang Berhormat Speaker. Dato’\n",
                "new_text_snippet": "Datuk Ahmad Marzuk bin Shaary [Pengkalan Chepa]: Yang Berhormat Speaker.\nDato’\n",
                "new_bold_snippet": "11111 11111 111111 111 111111 1111111111 1111111 0000 000000000 00000000\n11111\n",
                "new_italics_snippet": "none",
                "date": "19102023",
            },
        ],
        "02082017": [
            {
                "old_text_snippet": "Datuk Noor Ehsanuddin bin Mohd. Harun Narrashid [Kota Tinggi Yang\n",
                "new_text_snippet": "Datuk Noor Ehsanuddin bin Mohd. Harun Narrashid [Kota Tinggi]: Yang\n",
                "new_bold_snippet": "11111 1111 1111111111 111 11111 11111 111111111 11111 11111111 0000\n",
                "new_italics_snippet": "none",
                "date": "02082017",
            }
        ],
        "04072024": [
            {
                "old_text_snippet": "[Mesyuarat ditempohkan pada pukul 1.00 tengah hari\n",
                "new_text_snippet": "[Mesyuarat ditempohkan pada pukul 1.00 tengah hari]\n",
                "new_bold_snippet": "none",
                "new_italics_snippet": "none",
                "date": "04072024",
            }
        ],
    }

    if date:
        modifications = modifications.get(date, [])
    else:
        # flatten and run all
        modifications = [item for sublist in modifications.values() for item in sublist]

    num_edits = 0
    for modification in modifications:
        print(f"Editing hansards: {modification}")
        text, bold, italics, num_edits = read_and_replace(
            modification["date"],
            modification["old_text_snippet"],
            modification["new_text_snippet"],
            modification["new_bold_snippet"],
            modification["new_italics_snippet"],
            house,
            text,
            bold,
            italics,
            is_pipeline=is_pipeline,
        )

    return text, bold, italics, num_edits


def edit_dn_hansards(
    house, date=None, text=None, bold=None, italics=None, is_pipeline=False
):
    modifications = {
        "04032025": [
            {
                "old_text_snippet": "Datuk Wira Dr. Mohd Hatta bin Md Ramli: [Bangun[\n",
                "new_text_snippet": "Datuk Wira Dr. Mohd Hatta bin Md Ramli: [Bangun]\n",
                "new_bold_snippet": "11111 1111 111 1111 11111 111 11 111111 00000000\n",
                "new_italics_snippet": "00000 0000 000 0000 00000 000 00 000000 11111111\n",
                "date": "04032025",
            }
        ],
        "18102021": [
            {
                "old_text_snippet": "Mesyuaratdimulakanpadapukul10.00pagi\n",
                "new_text_snippet": "Mesyuarat dimulakan pada pukul 10.00 pagi\n",
                "new_bold_snippet": "all",
                "new_italics_snippet": "none",
                "date": "18102021",
            },
        ],
        "23122008": [
            {
                "old_text_snippet": "(cid:2) 5.29 ptg.\n",
                "new_text_snippet": "5.29 ptg.\n",
                "new_bold_snippet": "all",
                "new_italics_snippet": "none",
                "date": "23122008",
            }
        ],
    }

    if date:
        modifications = modifications.get(date, [])
    else:
        # flatten and run all
        modifications = [item for sublist in modifications.values() for item in sublist]

    num_edits = 0
    for modification in modifications:
        print(f"Editing hansards: {modification}")
        text, bold, italics, num_edits = read_and_replace(
            modification["date"],
            modification["old_text_snippet"],
            modification["new_text_snippet"],
            modification["new_bold_snippet"],
            modification["new_italics_snippet"],
            house,
            text,
            bold,
            italics,
            is_pipeline=is_pipeline,
        )

    return text, bold, italics, num_edits


if __name__ == "__main__":
    edit_hansards("DR")
    edit_hansards("DN")
    edit_hansards("KKDR")
