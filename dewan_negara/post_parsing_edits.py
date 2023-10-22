"""Modify tables"""
import json


def modify_table(hansard_date, old_table, new_table):
    year = hansard_date[-4:]
    sortable_date = f'{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}'  # YYYY-MM-DD
    dir_path = f"parsed_pdf/{year}/{sortable_date}/"
    file_name = dir_path + 'tables.json'
    # read the list of tables from the file
    with open(file_name, 'r') as f:
        tables = json.load(f)
    # find the table that matches the old table
    for i in range(len(tables)):
        if tables[i] == old_table:
            tables[i] = new_table
            break
    # remove any null tables
    tables = [table for table in tables if table is not None]
    # load this back into the file
    with open(file_name, 'w') as f:
        json.dump(tables, f, indent=4)


def modify_tables():
    modify_table("28072010",[
        34,
        29,
        [
            [
                [
                    "Graduan"
                ],
                [
                    "Pegawai perubatan"
                ],
                [
                    "Pegawai pergigian"
                ],
                [
                    "Farmasi"
                ]
            ],
            [
                [
                    "Jenis Perkhidmatan",
                    "Kadar Nisbah (2006)",
                    "Kadar Nisbah (2010)"
                ],
                [
                    "Pegawai Perubatan",
                    "1:1,383",
                    "1:920"
                ],
                [
                    "Pegawai Pergigian",
                    "1:9,716",
                    "1:8,153"
                ],
                [
                    "Pegawai Farmasi",
                    "1:4,895",
                    "1:3,350"
                ]
            ],
            [
                [
                    "Jenis Perkhidmatan",
                    "Nisbah"
                ],
                [
                    "Pegawai Perubatan",
                    "1:600 penduduk"
                ]
            ]
        ]
    ],[
        34,
        29,
        [
            [
                [
                    "Graduan", "Jumlah (Orang)"
                ],
                [
                    "Pegawai perubatan", "2,220"
                ],
                [
                    "Pegawai pergigian", "210"
                ],
                [
                    "Farmasi", "768"
                ]
            ],
            [
                [
                    "Jenis Perkhidmatan",
                    "Kadar Nisbah (2006)",
                    "Kadar Nisbah (2010)"
                ],
                [
                    "Pegawai Perubatan",
                    "1:1,383",
                    "1:920"
                ],
                [
                    "Pegawai Pergigian",
                    "1:9,716",
                    "1:8,153"
                ],
                [
                    "Pegawai Farmasi",
                    "1:4,895",
                    "1:3,350"
                ]
            ],
            [
                [
                    "Jenis Perkhidmatan",
                    "Nisbah"
                ],
                [
                    "Pegawai Perubatan",
                    "1:600 penduduk"
                ]
            ]
        ]
    ],)
    modify_table('18102021',[
        49,
        42,
        [
            [
                [
                    "inklusif",
                    "dan",
                    "Ma"
                ]
            ]
        ]
    ],None)
    modify_table('30062014',[
        39,
        34,
        [
            [
                [
                    "Jenis kesalahan",
                    "Jumlah Kes"
                ],
                [
                    "Penipuan",
                    "7,893"
                ],
                [
                    "Penyeludupan",
                    "2,155"
                ],
                [
                    "Dadah",
                    "1,435"
                ],
                [
                    "Jenayah cukai",
                    "1,046"
                ],
                [
                    "Curi dan rompakan",
                    "309"
                ],
                [
                    "Lain-lain",
                    "198"
                ]
            ],
            [
                [
                    "Kertas Siasatan"
                ],
                [
                    "219"
                ],
                [
                    "119"
                ],
                [
                    "115"
                ],
                [
                    "14"
                ],
                [
                    "5"
                ],
                [
                    "5"
                ],
                [
                    "1"
                ],
                [
                    "568"
                ]
            ]
        ]
    ],[
        39,
        34,
        [
            [
                [
                    "Jenis kesalahan",
                    "Jumlah Kes"
                ],
                [
                    "Penipuan",
                    "7,893"
                ],
                [
                    "Penyeludupan",
                    "2,155"
                ],
                [
                    "Dadah",
                    "1,435"
                ],
                [
                    "Jenayah cukai",
                    "1,046"
                ],
                [
                    "Curi dan rompakan",
                    "309"
                ],
                [
                    "Lain-lain",
                    "198"
                ]
            ],
            [
                [
                    "Agensi Penguat kuasa",
                    "Kertas Siasatan"
                ],
                [
                    "PDRM",
                    "219"
                ],
                [
                    "SPRM",
                    "119"
                ],
                [
                    "LHDN",
                    "115"
                ],
                [
                    "Jabatan Kastam",
                    "14"
                ],
                [
                    "Bank Negara Malaysia (BNM)",
                    "5"
                ],
                [
                    "KPDNKK",
                    "5"
                ],
                [
                    "Suruhanjaya Sekuriti",
                    "1"
                ],
                [
                    "JUMLAH",
                    "568"
                ]
            ]
        ]
    ])
    modify_table('08102013',[
        13,
        8,
        [
            [
                [
                    "Kadar Pengangguran [peratus]"
                ],
                [
                    "26.3"
                ],
                [
                    "12.0"
                ],
                [
                    "7.4"
                ],
                [
                    "5.7"
                ],
                [
                    "3.8"
                ]
            ],
            [
                [
                    "Tahap Pendidikan",
                    "2012",
                    "Suku Tahun Kedua 2013"
                ],
                [
                    "Pendidikan rendah Tahun 6",
                    "23,600",
                    "28,000"
                ],
                [
                    "Pendidikan Menengah \nRendah [Tingkatan 1-3]",
                    "53,900",
                    "60,000"
                ],
                [
                    "Pendidikan Menengah Atas  1\n[Tingkatan 4 dan 5] & \nProgram Kemahiran Asas",
                    "83,800",
                    "193,000"
                ],
                [
                    "Tingkatan 6 dan Program \nMatrikulasi",
                    "16,300",
                    "14,700"
                ],
                [
                    "Program kemahiran kursus \ndan teknikal",
                    "7,900",
                    "10,200"
                ],
                [
                    "Diploma",
                    "",
                    "44,200"
                ],
                [
                    "Ijazah",
                    "",
                    "36,500"
                ],
                [
                    "Pendidikan tidak formal",
                    "",
                    "1,700"
                ],
                [
                    "Tiada pendidikan",
                    "",
                    "12,600"
                ],
                [
                    "Jumlah",
                    "",
                    "411,400 orang =  \n3.0 peratus"
                ]
            ],
            [
                [
                    "Jenis Kaum",
                    "2012  \n(peratus)",
                    "Suku Tahun \nKedua 2013  \n(peratus)"
                ],
                [
                    "",
                    None,
                    None
                ],
                [
                    "Warganegara Malaysia",
                    "3.2",
                    "3.3"
                ],
                [
                    "Bumiputera",
                    "3.5",
                    "3.4"
                ],
                [
                    "Melayu",
                    "3.1",
                    "3.0"
                ],
                [
                    "Bumiputera lain termasuk negeri\nSabah, Sarawak dan Orang Asli",
                    "5.2",
                    "5.0"
                ],
                [
                    "Cina",
                    "2.2",
                    "2.9"
                ],
                [
                    "India",
                    "4.4",
                    "3.3"
                ],
                [
                    "Lain-lain",
                    "6.6",
                    "3.6"
                ],
                [
                    "Bukan warganegara Malaysia",
                    "1.6",
                    "1.5"
                ],
                [
                    "Jumlah",
                    "3",
                    ""
                ]
            ]
        ]
    ],[
        13,
        8,
        [
            [
                [
                    "Negara",
                    "Kadar Pengangguran [peratus]"
                ],
                [
                    "Sepanyol",
                    "26.3"
                ],
                [
                    "Itali",
                    "12.0"
                ],
                [
                    "US",
                    "7.4"
                ],
                [
                    "Australia",
                    "5.7"
                ],
                [
                    "Jepun 3.8 peratus",
                    "3.8"
                ]
            ],
            [
                [
                    "Tahap Pendidikan",
                    "2012",
                    "Suku Tahun Kedua 2013"
                ],
                [
                    "Pendidikan rendah Tahun 6",
                    "23,600",
                    "28,000"
                ],
                [
                    "Pendidikan Menengah \nRendah [Tingkatan 1-3]",
                    "53,900",
                    "60,000"
                ],
                [
                    "Pendidikan Menengah Atas  1\n[Tingkatan 4 dan 5] & \nProgram Kemahiran Asas",
                    "83,800",
                    "193,000"
                ],
                [
                    "Tingkatan 6 dan Program \nMatrikulasi",
                    "16,300",
                    "14,700"
                ],
                [
                    "Program kemahiran kursus \ndan teknikal",
                    "7,900",
                    "10,200"
                ],
                [
                    "Diploma",
                    "",
                    "44,200"
                ],
                [
                    "Ijazah",
                    "",
                    "36,500"
                ],
                [
                    "Pendidikan tidak formal",
                    "",
                    "1,700"
                ],
                [
                    "Tiada pendidikan",
                    "",
                    "12,600"
                ],
                [
                    "Jumlah",
                    "",
                    "411,400 orang =  \n3.0 peratus"
                ]
            ],
            [
                [
                    "Jenis Kaum",
                    "2012  \n(peratus)",
                    "Suku Tahun \nKedua 2013  \n(peratus)"
                ],
                [
                    "",
                    None,
                    None
                ],
                [
                    "Warganegara Malaysia",
                    "3.2",
                    "3.3"
                ],
                [
                    "Bumiputera",
                    "3.5",
                    "3.4"
                ],
                [
                    "Melayu",
                    "3.1",
                    "3.0"
                ],
                [
                    "Bumiputera lain termasuk negeri\nSabah, Sarawak dan Orang Asli",
                    "5.2",
                    "5.0"
                ],
                [
                    "Cina",
                    "2.2",
                    "2.9"
                ],
                [
                    "India",
                    "4.4",
                    "3.3"
                ],
                [
                    "Lain-lain",
                    "6.6",
                    "3.6"
                ],
                [
                    "Bukan warganegara Malaysia",
                    "1.6",
                    "1.5"
                ],
                [
                    "Jumlah",
                    "3",
                    ""
                ]
            ]
        ]
    ])
    modify_table('19042011',[
        20,
        13,
        [
            [
                [
                    "Tahun"
                ],
                [
                    "2008"
                ],
                [
                    "2009"
                ],
                [
                    "2010"
                ],
                [
                    "2011 (hingga Mac)"
                ]
            ],
            [
                [
                    "Tahun",
                    "Perbelanjaan (RM)"
                ],
                [
                    "2008",
                    "179,322,492.87"
                ],
                [
                    "2009",
                    "125,618,924.13"
                ],
                [
                    "2010",
                    "94,91,941.04"
                ]
            ]
        ]
    ],[
        20,
        13,
        [
            [
                [
                    "Tahun",
                    "Bilangan Kes"
                ],
                [
                    "2008",
                    "408"
                ],
                [
                    "2009",
                    "352"
                ],
                [
                    "2010",
                    "582"
                ],
                [
                    "2011 (hingga Mac)",
                    "67"
                ]
            ],
            [
                [
                    "Tahun",
                    "Perbelanjaan (RM)"
                ],
                [
                    "2008",
                    "179,322,492.87"
                ],
                [
                    "2009",
                    "125,618,924.13"
                ],
                [
                    "2010",
                    "94,91,941.04"
                ]
            ]
        ]
    ])
    modify_table('28042010',[
        20,
        13,
        [
            [
                [
                    "AGIHAN KLINIK 1MALAYSIA MENGIKUT NEGERI",
                    None
                ],
                [
                    "Negeri",
                    "Klinik 1Malaysia  \n(bil./buah)"
                ],
                [
                    "Selangor",
                    "5"
                ],
                [
                    "Wilayah Persekutuan Kuala \nLumpur",
                    "5"
                ],
                [
                    "Pulau Pinang",
                    "5"
                ],
                [
                    "Johor",
                    "5"
                ],
                [
                    "Perak",
                    "4"
                ],
                [
                    "Sabah",
                    "4"
                ],
                [
                    "Sarawak",
                    "4"
                ],
                [
                    "Negeri Sembilan",
                    "3"
                ],
                [
                    "Melaka",
                    "3"
                ],
                [
                    "Pahang",
                    "3"
                ],
                [
                    "Terengganu",
                    "3"
                ],
                [
                    "Kelantan",
                    "3"
                ],
                [
                    "Kedah",
                    "2"
                ],
                [
                    "Perlis",
                    "1"
                ]
            ],
            [
                [
                    "Peratus ( peratus)"
                ],
                [
                    "56"
                ],
                [
                    "11"
                ],
                [
                    "8"
                ],
                [
                    "7"
                ],
                [
                    "5"
                ]
            ]
        ]
    ],[
        20,
        13,
        [
            [
                [
                    "AGIHAN KLINIK 1MALAYSIA MENGIKUT NEGERI",
                    None
                ],
                [
                    "Negeri",
                    "Klinik 1Malaysia  \n(bil./buah)"
                ],
                [
                    "Selangor",
                    "5"
                ],
                [
                    "Wilayah Persekutuan Kuala \nLumpur",
                    "5"
                ],
                [
                    "Pulau Pinang",
                    "5"
                ],
                [
                    "Johor",
                    "5"
                ],
                [
                    "Perak",
                    "4"
                ],
                [
                    "Sabah",
                    "4"
                ],
                [
                    "Sarawak",
                    "4"
                ],
                [
                    "Negeri Sembilan",
                    "3"
                ],
                [
                    "Melaka",
                    "3"
                ],
                [
                    "Pahang",
                    "3"
                ],
                [
                    "Terengganu",
                    "3"
                ],
                [
                    "Kelantan",
                    "3"
                ],
                [
                    "Kedah",
                    "2"
                ],
                [
                    "Perlis",
                    "1"
                ]
            ],
            [
                [
                    "KES-KES DIRAWAT DI KLINIK 1MALAYSIA",
                    None
                ],
                [
                    "Kes-kes Rawatan",
                    "Peratus ( peratus)"
                ],
                [
                    "Batuk selesema",
                    "56"
                ],
                [
                    "Badan tidak sihat",
                    "11"
                ],
                [
                    "Sakit perut",
                    "8"
                ],
                [
                    "Sakit kulit",
                    "7"
                ],
                [
                    "Sakit otot",
                    "5"
                ]
            ]
        ]
    ])


if __name__ == "__main__":
    modify_tables()
