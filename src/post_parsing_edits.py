"""Modify tables"""

import json
import re


def modify_table(hansard_date, old_table, new_table):
    year = hansard_date[-4:]
    sortable_date = (
        f"{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}"  # YYYY-MM-DD
    )
    dir_path = f"parsed_pdf/{year}/{sortable_date}/"
    file_name = dir_path + "tables.json"
    try:
        # read the list of tables from the file
        with open(file_name, "r") as f:
            tables = json.load(f)
        # find the table that matches the old table
        for i in range(len(tables)):
            if tables[i] == old_table:
                tables[i] = new_table
                break
        # remove any null tables
        tables = [table for table in tables if table is not None]
        # load this back into the file
        with open(file_name, "w") as f:
            json.dump(tables, f, indent=4)
    except FileNotFoundError:
        print(f"{hansard_date} not found, skipping")


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
    dir_path = f"parsed_pdf/{year}/{sortable_date}/"

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


def delete_toc_entry(hansard_date, toc_entry):
    year = hansard_date[-4:]
    sortable_date = (
        f"{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}"  # YYYY-MM-DD
    )
    dir_path = f"parsed_pdf/{year}/{sortable_date}/"
    with open(f"{dir_path}/categories.json", "r") as f:
        toc = json.load(f)
    toc = [line for line in toc if line != toc_entry]
    with open(f"{dir_path}/categories.json", "w") as f:
        json.dump(toc, f, indent=4)


def add_toc_entry(hansard_date, toc_entry):
    year = hansard_date[-4:]
    sortable_date = (
        f"{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}"  # YYYY-MM-DD
    )
    dir_path = f"parsed_pdf/{year}/{sortable_date}"
    try:
        with open(f"{dir_path}/categories.json", "r") as f:
            toc = json.load(f)
        if toc_entry not in toc:
            toc.append(toc_entry)
        with open(f"{dir_path}/categories.json", "w") as f:
            json.dump(toc, f, indent=4)
    except FileNotFoundError:
        print(f"{hansard_date} not found, skipping")


def post_parsing_edits(house, date=None):
    if house.upper() == "DN":
        post_parsing_edits_dn(date)
    elif house.upper() == "DR":
        post_parsing_edits_dr(date)


def post_parsing_edits_dn(date=None):
    """Post parsing edits for Dewan Negara hansards"""
    table_modifications = {
        "28072010": {
            "old_table": [
                34,
                29,
                [
                    [
                        ["Graduan"],
                        ["Pegawai perubatan"],
                        ["Pegawai pergigian"],
                        ["Farmasi"],
                    ],
                    [
                        [
                            "Jenis Perkhidmatan",
                            "Kadar Nisbah (2006)",
                            "Kadar Nisbah (2010)",
                        ],
                        ["Pegawai Perubatan", "1:1,383", "1:920"],
                        ["Pegawai Pergigian", "1:9,716", "1:8,153"],
                        ["Pegawai Farmasi", "1:4,895", "1:3,350"],
                    ],
                    [
                        ["Jenis Perkhidmatan", "Nisbah"],
                        ["Pegawai Perubatan", "1:600 penduduk"],
                    ],
                ],
            ],
            "new_table": [
                34,
                29,
                [
                    [
                        ["Graduan", "Jumlah (Orang)"],
                        ["Pegawai perubatan", "2,220"],
                        ["Pegawai pergigian", "210"],
                        ["Farmasi", "768"],
                    ],
                    [
                        [
                            "Jenis Perkhidmatan",
                            "Kadar Nisbah (2006)",
                            "Kadar Nisbah (2010)",
                        ],
                        ["Pegawai Perubatan", "1:1,383", "1:920"],
                        ["Pegawai Pergigian", "1:9,716", "1:8,153"],
                        ["Pegawai Farmasi", "1:4,895", "1:3,350"],
                    ],
                    [
                        ["Jenis Perkhidmatan", "Nisbah"],
                        ["Pegawai Perubatan", "1:600 penduduk"],
                    ],
                ],
            ],
        },
        "18102021": {
            "old_table": [49, 42, [[["inklusif", "dan", "Ma"]]]],
            "new_table": None,
        },
        "30062014": {
            "old_table": [
                39,
                34,
                [
                    [
                        ["Jenis kesalahan", "Jumlah Kes"],
                        ["Penipuan", "7,893"],
                        ["Penyeludupan", "2,155"],
                        ["Dadah", "1,435"],
                        ["Jenayah cukai", "1,046"],
                        ["Curi dan rompakan", "309"],
                        ["Lain-lain", "198"],
                    ],
                    [
                        ["Kertas Siasatan"],
                        ["219"],
                        ["119"],
                        ["115"],
                        ["14"],
                        ["5"],
                        ["5"],
                        ["1"],
                        ["568"],
                    ],
                ],
            ],
            "new_table": [
                39,
                34,
                [
                    [
                        ["Jenis kesalahan", "Jumlah Kes"],
                        ["Penipuan", "7,893"],
                        ["Penyeludupan", "2,155"],
                        ["Dadah", "1,435"],
                        ["Jenayah cukai", "1,046"],
                        ["Curi dan rompakan", "309"],
                        ["Lain-lain", "198"],
                    ],
                    [
                        ["Agensi Penguat kuasa", "Kertas Siasatan"],
                        ["PDRM", "219"],
                        ["SPRM", "119"],
                        ["LHDN", "115"],
                        ["Jabatan Kastam", "14"],
                        ["Bank Negara Malaysia (BNM)", "5"],
                        ["KPDNKK", "5"],
                        ["Suruhanjaya Sekuriti", "1"],
                        ["JUMLAH", "568"],
                    ],
                ],
            ],
        },
        "08102013": {
            "old_table": [
                13,
                8,
                [
                    [
                        ["Kadar Pengangguran [peratus]"],
                        ["26.3"],
                        ["12.0"],
                        ["7.4"],
                        ["5.7"],
                        ["3.8"],
                    ],
                    [
                        ["Tahap Pendidikan", "2012", "Suku Tahun Kedua 2013"],
                        ["Pendidikan rendah Tahun 6", "23,600", "28,000"],
                        [
                            "Pendidikan Menengah \nRendah [Tingkatan 1-3]",
                            "53,900",
                            "60,000",
                        ],
                        [
                            "Pendidikan Menengah Atas  1\n[Tingkatan 4 dan 5] & \nProgram Kemahiran Asas",
                            "83,800",
                            "193,000",
                        ],
                        ["Tingkatan 6 dan Program \nMatrikulasi", "16,300", "14,700"],
                        ["Program kemahiran kursus \ndan teknikal", "7,900", "10,200"],
                        ["Diploma", "", "44,200"],
                        ["Ijazah", "", "36,500"],
                        ["Pendidikan tidak formal", "", "1,700"],
                        ["Tiada pendidikan", "", "12,600"],
                        ["Jumlah", "", "411,400 orang =  \n3.0 peratus"],
                    ],
                    [
                        [
                            "Jenis Kaum",
                            "2012  \n(peratus)",
                            "Suku Tahun \nKedua 2013  \n(peratus)",
                        ],
                        ["", None, None],
                        ["Warganegara Malaysia", "3.2", "3.3"],
                        ["Bumiputera", "3.5", "3.4"],
                        ["Melayu", "3.1", "3.0"],
                        [
                            "Bumiputera lain termasuk negeri\nSabah, Sarawak dan Orang Asli",
                            "5.2",
                            "5.0",
                        ],
                        ["Cina", "2.2", "2.9"],
                        ["India", "4.4", "3.3"],
                        ["Lain-lain", "6.6", "3.6"],
                        ["Bukan warganegara Malaysia", "1.6", "1.5"],
                        ["Jumlah", "3", ""],
                    ],
                ],
            ],
            "new_table": [
                13,
                8,
                [
                    [
                        ["Negara", "Kadar Pengangguran [peratus]"],
                        ["Sepanyol", "26.3"],
                        ["Itali", "12.0"],
                        ["US", "7.4"],
                        ["Australia", "5.7"],
                        ["Jepun 3.8 peratus", "3.8"],
                    ],
                    [
                        ["Tahap Pendidikan", "2012", "Suku Tahun Kedua 2013"],
                        ["Pendidikan rendah Tahun 6", "23,600", "28,000"],
                        [
                            "Pendidikan Menengah \nRendah [Tingkatan 1-3]",
                            "53,900",
                            "60,000",
                        ],
                        [
                            "Pendidikan Menengah Atas  1\n[Tingkatan 4 dan 5] & \nProgram Kemahiran Asas",
                            "83,800",
                            "193,000",
                        ],
                        ["Tingkatan 6 dan Program \nMatrikulasi", "16,300", "14,700"],
                        ["Program kemahiran kursus \ndan teknikal", "7,900", "10,200"],
                        ["Diploma", "", "44,200"],
                        ["Ijazah", "", "36,500"],
                        ["Pendidikan tidak formal", "", "1,700"],
                        ["Tiada pendidikan", "", "12,600"],
                        ["Jumlah", "", "411,400 orang =  \n3.0 peratus"],
                    ],
                    [
                        [
                            "Jenis Kaum",
                            "2012  \n(peratus)",
                            "Suku Tahun \nKedua 2013  \n(peratus)",
                        ],
                        ["", None, None],
                        ["Warganegara Malaysia", "3.2", "3.3"],
                        ["Bumiputera", "3.5", "3.4"],
                        ["Melayu", "3.1", "3.0"],
                        [
                            "Bumiputera lain termasuk negeri\nSabah, Sarawak dan Orang Asli",
                            "5.2",
                            "5.0",
                        ],
                        ["Cina", "2.2", "2.9"],
                        ["India", "4.4", "3.3"],
                        ["Lain-lain", "6.6", "3.6"],
                        ["Bukan warganegara Malaysia", "1.6", "1.5"],
                        ["Jumlah", "3", ""],
                    ],
                ],
            ],
        },
        "19042011": {
            "old_table": [
                20,
                13,
                [
                    [["Tahun"], ["2008"], ["2009"], ["2010"], ["2011 (hingga Mac)"]],
                    [
                        ["Tahun", "Perbelanjaan (RM)"],
                        ["2008", "179,322,492.87"],
                        ["2009", "125,618,924.13"],
                        ["2010", "94,91,941.04"],
                    ],
                ],
            ],
            "new_table": [
                20,
                13,
                [
                    [
                        ["Tahun", "Bilangan Kes"],
                        ["2008", "408"],
                        ["2009", "352"],
                        ["2010", "582"],
                        ["2011 (hingga Mac)", "67"],
                    ],
                    [
                        ["Tahun", "Perbelanjaan (RM)"],
                        ["2008", "179,322,492.87"],
                        ["2009", "125,618,924.13"],
                        ["2010", "94,91,941.04"],
                    ],
                ],
            ],
        },
        "28042010": {
            "old_table": [
                20,
                13,
                [
                    [
                        ["AGIHAN KLINIK 1MALAYSIA MENGIKUT NEGERI", None],
                        ["Negeri", "Klinik 1Malaysia  \n(bil./buah)"],
                        ["Selangor", "5"],
                        ["Wilayah Persekutuan Kuala \nLumpur", "5"],
                        ["Pulau Pinang", "5"],
                        ["Johor", "5"],
                        ["Perak", "4"],
                        ["Sabah", "4"],
                        ["Sarawak", "4"],
                        ["Negeri Sembilan", "3"],
                        ["Melaka", "3"],
                        ["Pahang", "3"],
                        ["Terengganu", "3"],
                        ["Kelantan", "3"],
                        ["Kedah", "2"],
                        ["Perlis", "1"],
                    ],
                    [["Peratus ( peratus)"], ["56"], ["11"], ["8"], ["7"], ["5"]],
                ],
            ],
            "new_table": [
                20,
                13,
                [
                    [
                        ["AGIHAN KLINIK 1MALAYSIA MENGIKUT NEGERI", None],
                        ["Negeri", "Klinik 1Malaysia  \n(bil./buah)"],
                        ["Selangor", "5"],
                        ["Wilayah Persekutuan Kuala \nLumpur", "5"],
                        ["Pulau Pinang", "5"],
                        ["Johor", "5"],
                        ["Perak", "4"],
                        ["Sabah", "4"],
                        ["Sarawak", "4"],
                        ["Negeri Sembilan", "3"],
                        ["Melaka", "3"],
                        ["Pahang", "3"],
                        ["Terengganu", "3"],
                        ["Kelantan", "3"],
                        ["Kedah", "2"],
                        ["Perlis", "1"],
                    ],
                    [
                        ["KES-KES DIRAWAT DI KLINIK 1MALAYSIA", None],
                        ["Kes-kes Rawatan", "Peratus ( peratus)"],
                        ["Batuk selesema", "56"],
                        ["Badan tidak sihat", "11"],
                        ["Sakit perut", "8"],
                        ["Sakit kulit", "7"],
                        ["Sakit otot", "5"],
                    ],
                ],
            ],
        },
    }

    if date:
        # collect all table modifications for the date
        table_modifications = {
            k: v for k, v in table_modifications.items() if k == date
        }

    # Apply all table modifications
    for hansard_date, modification in table_modifications.items():
        modify_table(
            hansard_date=hansard_date,
            old_table=modification["old_table"],
            new_table=modification["new_table"],
        )


def post_parsing_edits_dr(date=None):
    """Post parsing edits for Dewan Rakyat hansards"""

    table_modifications = {
        "25112014": {
            "old_table": [139, 139, [[["kaudang,", "dangdang"]]]],
            "new_table": None,
        },
        "25112014": {
            "old_table": [38, 25, [[["RM1,987,000,000", "[na1]"]]]],
            "new_table": None,
        },
        "07042010": {
            "old_table": [
                19,
                6,
                [
                    [
                        ["Negeri"],
                        ["Perlis"],
                        ["Kedah"],
                        ["Pulau Pinang"],
                        ["Perak"],
                        ["Selangor"],
                        ["Kuala Lumpur"],
                        ["Negeri Sembilan"],
                        ["Melaka"],
                        ["Johor"],
                        ["Pahang"],
                        ["Terengganu"],
                        ["Kelantan"],
                        ["Sabah"],
                        ["Sarawak"],
                        ["Jumlah"],
                    ],
                    [
                        ["Negeri", "Bilangan penderaan  \nkanak-kanak & Bayi"],
                        ["Perlis", "245"],
                        ["Kedah", "420"],
                        ["Pulau Pinang", "891"],
                        ["Perak", "861"],
                        ["Selangor", "3,234"],
                        ["Kuala Lumpur", "2,221"],
                        ["Negeri Sembilan", "799"],
                        ["Melaka", "301"],
                        ["Johor", "599"],
                        ["Pahang", "440"],
                        ["Terengganu", "168"],
                        ["Kelantan", "105"],
                        ["Sabah", "34"],
                        ["Sarawak", "440"],
                        ["Jumlah", "10,758"],
                    ],
                ],
            ],
            "new_table": [
                19,
                6,
                [
                    [
                        ["Negeri", "Bilangan penderaan  \nkanak-kanak & Bayi"],
                        ["Perlis", "245"],
                        ["Kedah", "420"],
                        ["Pulau Pinang", "891"],
                        ["Perak", "861"],
                        ["Selangor", "3,234"],
                        ["Kuala Lumpur", "2,221"],
                        ["Negeri Sembilan", "799"],
                        ["Melaka", "301"],
                        ["Johor", "599"],
                        ["Pahang", "440"],
                        ["Terengganu", "168"],
                        ["Kelantan", "105"],
                        ["Sabah", "34"],
                        ["Sarawak", "440"],
                        ["Jumlah", "10,758"],
                    ]
                ],
            ],
        },
        "12042010": {
            "old_table": [38, 25, [[["RM1,987,000,000", "[na1]"]]]],
            "new_table": None,
        },
    }

    if date:
        # collect all table modifications for the date
        table_modifications = {
            k: v for k, v in table_modifications.items() if k == date
        }

    # Apply all table modifications
    for hansard_date, modification in table_modifications.items():
        modify_table(
            hansard_date=hansard_date,
            old_table=modification["old_table"],
            new_table=modification["new_table"],
        )

    # Handle TOC entries
    toc_entries = {
        "01082022": "UCAPAN TAKZIAH",
        "28022022": (
            "TITAH KEBAWAH DULI YANG MAHA MULIA SERI PADUKA BAGINDA YANG DI-PERTUAN AGONG XVI AL-SULTAN "
            "ABDULLAH RI’AYATUDDIN AL-MUSTAFA BILLAH SHAH IBNI ALMARHUM SULTAN HAJI AHMAD SHAH AL-MUSTA’IN "
            "BILLAH"
        ),
        "16072018": (
            "PROKLAMASI SERI PADUKA BAGINDA YANG DI-PERTUAN AGONG MEMANGGIL PARLIMEN UNTUK BERMESYUARAT"
        ),
        "02082018": "PETUA-PETUA TUAN YANG DI-PERTUA",
        "05032018": (
            "TITAH KEBAWAH DULI YANG MAHA MULIA SERI PADUKA BAGINDA YANG DI-PERTUAN AGONG XV, SULTAN MUHAMMAD V"
        ),
    }

    if date:
        # collect all table modifications for the date
        toc_entries = {k: v for k, v in toc_entries.items() if k == date}

    # Add all TOC entries
    for hansard_date, entry in toc_entries.items():
        add_toc_entry(hansard_date, entry)


if __name__ == "__main__":
    post_parsing_edits("DN")
    post_parsing_edits("DR")
