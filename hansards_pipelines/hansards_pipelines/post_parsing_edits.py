"""Modify tables"""

import json
import re

def ensure_json_string(data):
    """Ensure data is serialized to JSON string for downstream assets."""
    if data is None:
        return None
    if isinstance(data, (str, bytes, bytearray)):
        return data
    return json.dumps(data)


def read_and_modify_table(hansard_date, old_table, new_table, file_contents=None):

    if file_contents is None:
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
            tables = modify_table(tables, old_table, new_table)
            with open(file_name, "w") as f:
                json.dump(tables, f, indent=4)
        except FileNotFoundError:
            print(f"{hansard_date} not found, skipping")
    else:
        modified_tables = modify_table(file_contents, old_table, new_table)
        return modified_tables


def modify_table(tables, old_table, new_table):
    # find the table that matches the old table
    for i in range(len(tables)):
        if tables[i] == old_table:
            tables[i] = new_table
            break
    # remove any null tables
    tables = [table for table in tables if table is not None]
    return tables


def read_and_add_toc_entry(hansard_date, toc_entry, file_contents=None):
    if file_contents is None:
        year = hansard_date[-4:]
        sortable_date = (
            f"{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}"  # YYYY-MM-DD
        )
        dir_path = f"parsed_pdf/{year}/{sortable_date}"
        try:
            with open(f"{dir_path}/categories.json", "r") as f:
                toc = json.load(f)
            toc = add_toc_entry(toc, toc_entry)
            with open(f"{dir_path}/categories.json", "w") as f:
                json.dump(toc, f, indent=4)
        except FileNotFoundError:
            print(f"{hansard_date} not found, skipping")
    else:
        toc = add_toc_entry(file_contents, toc_entry)
        return toc


def add_toc_entry(toc, toc_entry):
    if not isinstance(toc, list):
        try:
            toc = json.loads(toc) if toc else []
        except Exception:
            print("Invalid JSON format for TOC, initializing as empty list")
            toc = []

    if toc_entry not in toc:
        toc.append(toc_entry)
    return toc


def post_parsing_edits(
    house, date=None, tablejson_file_contents=None, categories_file_contents=None
):
    if house.upper() == "DN":
        return post_parsing_edits_dn(
            date, tablejson_file_contents, categories_file_contents
        )
    elif house.upper() == "DR":
        return post_parsing_edits_dr(
            date, tablejson_file_contents, categories_file_contents
        )
    elif house.upper() == "KKDR":
        return post_parsing_edits_kk(
            date, tablejson_file_contents, categories_file_contents
        )


def post_parsing_edits_dn(
    date=None, tablejson_file_contents=None, categories_file_contents=None
):
    """Post parsing edits for Dewan Negara hansards"""
    table_modifications = {
        "28072010": [
            {
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
            }
        ],
        "18102021": [
            {
                "old_table": [49, 42, [[["inklusif", "dan", "Ma"]]]],
                "new_table": None,
            }
        ],
        "30062014": [
            {
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
            }
        ],
        "08102013": [
            {
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
                            [
                                "Tingkatan 6 dan Program \nMatrikulasi",
                                "16,300",
                                "14,700",
                            ],
                            [
                                "Program kemahiran kursus \ndan teknikal",
                                "7,900",
                                "10,200",
                            ],
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
                            [
                                "Tingkatan 6 dan Program \nMatrikulasi",
                                "16,300",
                                "14,700",
                            ],
                            [
                                "Program kemahiran kursus \ndan teknikal",
                                "7,900",
                                "10,200",
                            ],
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
            }
        ],
        "19042011": [
            {
                "old_table": [
                    20,
                    13,
                    [
                        [
                            ["Tahun"],
                            ["2008"],
                            ["2009"],
                            ["2010"],
                            ["2011 (hingga Mac)"],
                        ],
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
            }
        ],
        "28042010": [
            {
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
            }
        ],
    }
    # Normalize table_modifications into a flat list
    normalized_modifications = []

    if date:
        # Get modifications for specific date (or empty list if none)
        items = table_modifications.get(date, [])
        normalized_modifications = [
            {**item, "date": date}
            for item in items
        ]
    else:
        # Flatten all dates and inject date into each item
        for date_key, sublist in table_modifications.items():
            normalized_modifications.extend(
                {**item, "date": date_key}
                for item in sublist
            )

    table_modifications = normalized_modifications

    # Apply all table modifications
    for modification in table_modifications:
        tablejson_file_contents = read_and_modify_table(
            hansard_date=modification["date"],
            old_table=modification["old_table"],
            new_table=modification["new_table"],
            file_contents=tablejson_file_contents,
        )
    tablejson_file_contents = ensure_json_string(tablejson_file_contents)
    categories_file_contents = ensure_json_string(categories_file_contents)

    return tablejson_file_contents, categories_file_contents



def post_parsing_edits_dr(
    date=None, tablejson_file_contents=None, categories_file_contents=None
):
    """Post parsing edits for Dewan Rakyat hansards"""

    table_modifications = {
        "25112014": [
            {
                "old_table": [139, 139, [[["kaudang,", "dangdang"]]]],
                "new_table": None,
            },
            {
                "old_table": [38, 25, [[["RM1,987,000,000", "[na1]"]]]],
                "new_table": None,
            },
        ],
        "07042010": [
            {
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
            }
        ],
        "12042010": [
            {
                "old_table": [38, 25, [[["RM1,987,000,000", "[na1]"]]]],
                "new_table": None,
            }
        ],
    }
    # Normalize table_modifications into a flat list
    normalized_modifications = []

    if date:
        # Get modifications for specific date (or empty list if none)
        items = table_modifications.get(date, [])
        normalized_modifications = [
            {**item, "date": date}
            for item in items
        ]
    else:
        # Flatten all dates and inject date into each item
        for date_key, sublist in table_modifications.items():
            normalized_modifications.extend(
                {**item, "date": date_key}
                for item in sublist
            )

    table_modifications = normalized_modifications

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
        toc_entries = {k: v for k, v in toc_entries.items() if k == date}

    # Add all TOC entries
    for entry in toc_entries:
        categories_file_contents = read_and_add_toc_entry(
            date, entry, categories_file_contents
        )

    tablejson_file_contents = ensure_json_string(tablejson_file_contents)
    categories_file_contents = ensure_json_string(categories_file_contents)

    return tablejson_file_contents, categories_file_contents



def post_parsing_edits_kk(
    date=None, tablejson_file_contents=None, categories_file_contents=None
):
    # table_modifications = {
    #     "25112014": [
    #         {
    #             "old_table": [139, 139, [[["kaudang,", "dangdang"]]]],
    #             "new_table": None,
    #         },
    #         {
    #             "old_table": [38, 25, [[["RM1,987,000,000", "[na1]"]]]],
    #             "new_table": None,
    #         },
    #     ],
    #     "07042010": [
    #         {
    #             "old_table": [
    #                 19,
    #                 6,
    #                 [
    #                     [
    #                         ["Negeri"],
    #                         ["Perlis"],
    #                         ["Kedah"],
    #                         ["Pulau Pinang"],
    #                         ["Perak"],
    #                         ["Selangor"],
    #                         ["Kuala Lumpur"],
    #                         ["Negeri Sembilan"],
    #                         ["Melaka"],
    #                         ["Johor"],
    #                         ["Pahang"],
    #                         ["Terengganu"],
    #                         ["Kelantan"],
    #                         ["Sabah"],
    #                         ["Sarawak"],
    #                         ["Jumlah"],
    #                     ],
    #                     [
    #                         ["Negeri", "Bilangan penderaan  \nkanak-kanak & Bayi"],
    #                         ["Perlis", "245"],
    #                         ["Kedah", "420"],
    #                         ["Pulau Pinang", "891"],
    #                         ["Perak", "861"],
    #                         ["Selangor", "3,234"],
    #                         ["Kuala Lumpur", "2,221"],
    #                         ["Negeri Sembilan", "799"],
    #                         ["Melaka", "301"],
    #                         ["Johor", "599"],
    #                         ["Pahang", "440"],
    #                         ["Terengganu", "168"],
    #                         ["Kelantan", "105"],
    #                         ["Sabah", "34"],
    #                         ["Sarawak", "440"],
    #                         ["Jumlah", "10,758"],
    #                     ],
    #                 ],
    #             ],
    #             "new_table": [
    #                 19,
    #                 6,
    #                 [
    #                     [
    #                         ["Negeri", "Bilangan penderaan  \nkanak-kanak & Bayi"],
    #                         ["Perlis", "245"],
    #                         ["Kedah", "420"],
    #                         ["Pulau Pinang", "891"],
    #                         ["Perak", "861"],
    #                         ["Selangor", "3,234"],
    #                         ["Kuala Lumpur", "2,221"],
    #                         ["Negeri Sembilan", "799"],
    #                         ["Melaka", "301"],
    #                         ["Johor", "599"],
    #                         ["Pahang", "440"],
    #                         ["Terengganu", "168"],
    #                         ["Kelantan", "105"],
    #                         ["Sabah", "34"],
    #                         ["Sarawak", "440"],
    #                         ["Jumlah", "10,758"],
    #                     ]
    #                 ],
    #             ],
    #         }
    #     ],
    #     "12042010": [
    #         {
    #             "old_table": [38, 25, [[["RM1,987,000,000", "[na1]"]]]],
    #             "new_table": None,
    #         }
    #     ],
    # }
    
    table_modifications = {}
    
    if date and date not in table_modifications:
        tablejson_file_contents = None
        categories_file_contents = None
        table_modifications = []
    elif date and date in table_modifications:
        table_modifications = table_modifications[date]
    else:
        table_modifications = [
            item for sublist in table_modifications.values() for item in sublist
        ]

    # Apply all table modifications
    for modification in table_modifications:
        tablejson_file_contents = read_and_modify_table(
            hansard_date=modification["date"],
            old_table=modification["old_table"],
            new_table=modification["new_table"],
            file_contents=tablejson_file_contents,
        )
    tablejson_file_contents = ensure_json_string(tablejson_file_contents)
    categories_file_contents = ensure_json_string(categories_file_contents)

    return tablejson_file_contents, categories_file_contents



if __name__ == "__main__":
    post_parsing_edits("DN")
    post_parsing_edits("DR")
    post_parsing_edits("KKDR")
