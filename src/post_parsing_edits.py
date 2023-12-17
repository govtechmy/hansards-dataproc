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


def post_parsing_edits():
    modify_table("25112014", [139, 139, [[["kaudang,", "dangdang"]]]], None)
    modify_table("25112014", [38, 25, [[["RM1,987,000,000", "[na1]"]]]], None)
    modify_table(
        "07042010",
        [
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
        [
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
    )
    modify_table("12042010", [38, 25, [[["RM1,987,000,000", "[na1]"]]]], None)

    add_toc_entry("01082022", "UCAPAN TAKZIAH")
    add_toc_entry(
        "28022022",
        f"TITAH KEBAWAH DULI YANG MAHA MULIA SERI PADUKA BAGINDA YANG DI-PERTUAN AGONG XVI AL-SULTAN "
        f"ABDULLAH RI’AYATUDDIN AL-MUSTAFA BILLAH SHAH IBNI ALMARHUM SULTAN HAJI AHMAD SHAH AL-MUSTA’IN "
        f"BILLAH",
    )
    add_toc_entry(
        "16072018",
        "PROKLAMASI SERI PADUKA BAGINDA YANG DI-PERTUAN AGONG MEMANGGIL PARLIMEN UNTUK BERMESYUARAT",
    )
    add_toc_entry("02082018", "PETUA-PETUA TUAN YANG DI-PERTUA")
    add_toc_entry(
        "05032018",
        "TITAH KEBAWAH DULI YANG MAHA MULIA SERI PADUKA BAGINDA YANG DI-PERTUAN AGONG XV, SULTAN MUHAMMAD V",
    )


if __name__ == "__main__":
    post_parsing_edits()
