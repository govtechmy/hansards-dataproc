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
    modify_table('25112014', [
        139,
        139,
        [
            [
                [
                    "kaudang,",
                    "dangdang"
                ]
            ]
        ]
    ], None)
    modify_table('25112014', [
        38,
        25,
        [
            [
                [
                    "RM1,987,000,000",
                    "[na1]"
                ]
            ]
        ]
    ], None)
    modify_table('07042010', [
        19,
        6,
        [
            [
                [
                    "Negeri"
                ],
                [
                    "Perlis"
                ],
                [
                    "Kedah"
                ],
                [
                    "Pulau Pinang"
                ],
                [
                    "Perak"
                ],
                [
                    "Selangor"
                ],
                [
                    "Kuala Lumpur"
                ],
                [
                    "Negeri Sembilan"
                ],
                [
                    "Melaka"
                ],
                [
                    "Johor"
                ],
                [
                    "Pahang"
                ],
                [
                    "Terengganu"
                ],
                [
                    "Kelantan"
                ],
                [
                    "Sabah"
                ],
                [
                    "Sarawak"
                ],
                [
                    "Jumlah"
                ]
            ],
            [
                [
                    "Negeri",
                    "Bilangan penderaan  \nkanak-kanak & Bayi"
                ],
                [
                    "Perlis",
                    "245"
                ],
                [
                    "Kedah",
                    "420"
                ],
                [
                    "Pulau Pinang",
                    "891"
                ],
                [
                    "Perak",
                    "861"
                ],
                [
                    "Selangor",
                    "3,234"
                ],
                [
                    "Kuala Lumpur",
                    "2,221"
                ],
                [
                    "Negeri Sembilan",
                    "799"
                ],
                [
                    "Melaka",
                    "301"
                ],
                [
                    "Johor",
                    "599"
                ],
                [
                    "Pahang",
                    "440"
                ],
                [
                    "Terengganu",
                    "168"
                ],
                [
                    "Kelantan",
                    "105"
                ],
                [
                    "Sabah",
                    "34"
                ],
                [
                    "Sarawak",
                    "440"
                ],
                [
                    "Jumlah",
                    "10,758"
                ]
            ]
        ]
    ], [
                     19,
                     6,
                     [
                         [
                             [
                                 "Negeri",
                                 "Bilangan penderaan  \nkanak-kanak & Bayi"
                             ],
                             [
                                 "Perlis",
                                 "245"
                             ],
                             [
                                 "Kedah",
                                 "420"
                             ],
                             [
                                 "Pulau Pinang",
                                 "891"
                             ],
                             [
                                 "Perak",
                                 "861"
                             ],
                             [
                                 "Selangor",
                                 "3,234"
                             ],
                             [
                                 "Kuala Lumpur",
                                 "2,221"
                             ],
                             [
                                 "Negeri Sembilan",
                                 "799"
                             ],
                             [
                                 "Melaka",
                                 "301"
                             ],
                             [
                                 "Johor",
                                 "599"
                             ],
                             [
                                 "Pahang",
                                 "440"
                             ],
                             [
                                 "Terengganu",
                                 "168"
                             ],
                             [
                                 "Kelantan",
                                 "105"
                             ],
                             [
                                 "Sabah",
                                 "34"
                             ],
                             [
                                 "Sarawak",
                                 "440"
                             ],
                             [
                                 "Jumlah",
                                 "10,758"
                             ]
                         ]
                     ]
                 ]
                 )
    modify_table('12042010', [
        38,
        25,
        [
            [
                [
                    "RM1,987,000,000",
                    "[na1]"
                ]
            ]
        ]
    ], None)


if __name__ == "__main__":
    modify_tables()
