"""Insert tables, remove headers, replace double spaces with single spaces and other standardisations.
"""
import argparse
import os
from thefuzz import fuzz
import re
import list_to_markdown
import json
import utils


def is_header(text):
    # returns the page number if it is the following form, else None
    # DR.28.3.2023 1
    # 2                                                               DR 8.3.2018
    # DR 8.3.2018                                                                  1
    return re.fullmatch(r"[ .\d]*[D][R|N][ .\d]*\n", text)


def get_page_number(header_text):
    header_text = header_text.strip()
    # special case of 12.11.2019
    if "12.11.201 " in header_text:
        header_text = header_text.replace("12.11.201 ", "12.11.2019 ")
    if header_text.startswith("DR"):
        # some numbers might be in the form 1  1
        # some years are 2023.
        # some years missing end (2019 becomes 201)
        # get the page number after the year
        return re.split(r"\d{4}\.?", header_text)[-1].replace(" ", "")
    else:
        return header_text.split("DR")[0].replace(" ", "")


def mimic_table_as_plaintext(table):
    table_text = ""
    for row in table:
        # sometimes there are newlines inside cells
        # get the number of lines for this row
        max_lines = 1
        for cell in row:
            max_lines = max(max_lines, 1 + cell.count("\n"))
        for line_idx in range(max_lines):
            table_text += (
                " ".join(
                    [
                        cell.split("\n")[line_idx]
                        for cell in row
                        if line_idx < len(cell.split("\n"))
                    ]
                )
                + "\n"
            )
    return table_text


def format_table(text, bold, italics, table, hansard_date):
    # replace None with empty strings
    for row_idx in range(len(table)):
        for cell_idx in range(len(table[row_idx])):
            if table[row_idx][cell_idx] is None:
                table[row_idx][cell_idx] = ""
    # make table_text mimic the table structure as in plaintext.txt
    table_text = mimic_table_as_plaintext(table)
    # choose which row of the table as anchor
    table_anchor_idx = -1
    anchor_idx = -1
    anchor_row = ""
    table_text_rows = table_text.strip().split("\n")
    space_stripped_text = [re.sub(r"\s", "", t) for t in text]
    for idx in range(len(table_text_rows)):
        if len(table_text_rows[idx]) < 6:
            # too short to be anchor
            continue
        spaced_stripped_candidate_anchor = re.sub(r"\s", "", table_text_rows[idx])
        if space_stripped_text.count(spaced_stripped_candidate_anchor) != 1:
            # no exact match in text
            # prevent using a row that has duplicates in the table
            # so that anchor row will not get mismatched to another row
            continue
        table_anchor_idx = idx
        anchor_row = table_text_rows[idx]
        # find the row in the text corresponding to this anchor
        anchor_idx = space_stripped_text.index(spaced_stripped_candidate_anchor)
        break
    if anchor_idx == -1:
        # try again but now allow duplicates (the duplicated row can be in the next table, which is no problem)
        for idx in range(len(table_text_rows)):
            if len(table_text_rows[idx]) < 6:
                continue
            spaced_stripped_candidate_anchor = re.sub(r"\s", "", table_text_rows[idx])
            if space_stripped_text.count(spaced_stripped_candidate_anchor) < 1:
                continue
            table_anchor_idx = idx
            anchor_row = table_text_rows[idx]
            anchor_idx = space_stripped_text.index(spaced_stripped_candidate_anchor)
    assert anchor_idx != -1, f"Anchor not found for table {table_text}"
    # delete the text inside the text that corresponds to the table
    # since the content might be jumbled, particularly the header row,
    # we will only count by non-whitespace characters
    table_text_before_anchor = "\n".join(
        table_text.strip().split("\n")[:table_anchor_idx]
    )
    table_text_after_anchor = "\n".join(
        table_text.strip().split("\n")[table_anchor_idx + 1 :]
    )
    num_table_chars_before_anchor = len(re.sub(r"\s", "", table_text_before_anchor))
    num_table_chars_after_anchor = len(re.sub(r"\s", "", table_text_after_anchor))
    start_idx = anchor_idx - 1
    num_text_chars_included_before_anchor = 0
    text_included_before_anchor = ""
    while (
        start_idx >= 0
        and num_text_chars_included_before_anchor < num_table_chars_before_anchor
    ):
        text_included_before_anchor = text[start_idx] + text_included_before_anchor
        num_text_chars_included_before_anchor += len(re.sub(r"\s", "", text[start_idx]))
        start_idx -= 1

    end_idx = anchor_idx + 1
    num_text_chars_included_after_anchor = 0
    text_included_after_anchor = ""
    while (
        end_idx < len(text)
        and num_text_chars_included_after_anchor < num_table_chars_after_anchor
    ):
        text_included_after_anchor += text[end_idx]
        num_text_chars_included_after_anchor += len(re.sub(r"\s", "", text[end_idx]))
        end_idx += 1

    candidate_text = (
        text_included_before_anchor + text[anchor_idx] + text_included_after_anchor
    )
    table_text_similarity_score = fuzz.ratio(
        re.sub(r"\s", "", candidate_text), re.sub(r"\s", "", table_text)
    )
    # create a dictionary keeping count of alphanumeric characters
    table_alphanumeric_count = {}
    for char in re.sub(r"\s", "", table_text):
        if char.isalnum():
            table_alphanumeric_count[char] = table_alphanumeric_count.get(char, 0) + 1
    candidate_text_alphanumeric_count = {}
    for char in re.sub(r"\s", "", candidate_text):
        if char.isalnum():
            candidate_text_alphanumeric_count[char] = (
                candidate_text_alphanumeric_count.get(char, 0) + 1
            )
    if table_text_similarity_score < 90:
        print(
            f"WARN: table text similarity score is too low: {table_text_similarity_score}"
        )
        print(f"Anchor row is: {anchor_row}")
    with open(f"dump/matched_tables.txt", "a") as f:
        f.write(f"{hansard_date}\n")
        f.write(f"Anchor row is: {anchor_row}\n")
        f.write(f"Table text similarity score is: {table_text_similarity_score}\n")
        f.write(f"Table text is:\n___\n{table_text}\n___\n\n")
        f.write(f"Candidate text is:\n___\n{candidate_text}\n___\n\n")
    # get the key where the dictionaries differ
    for key in table_alphanumeric_count.keys():
        if table_alphanumeric_count[key] != candidate_text_alphanumeric_count[key]:
            print(
                f"Alphanumeric counts do not match: {table_alphanumeric_count[key]} vs "
                f"{candidate_text_alphanumeric_count[key]} for key {key}"
            )
    assert (
        num_text_chars_included_before_anchor == num_table_chars_before_anchor
        and num_text_chars_included_after_anchor == num_table_chars_after_anchor
    ), (
        f"Number of text chars included before and after anchor do not match number of table chars: "
        f"{num_text_chars_included_before_anchor} vs {num_table_chars_before_anchor} and "
        f"{num_text_chars_included_after_anchor} vs {num_table_chars_after_anchor}"
    )

    # replace the entire block between start_idx and end_idx with the table
    table = [[cell.replace("\n", "") for cell in row] for row in table]
    markdown_table = list_to_markdown.make_markdown_table(table).split("\n")[
        :-1
    ]  # remove trailing newline
    markdown_table = [
        row.replace("\n", "") + "\n" for row in markdown_table
    ]  # remove in-cell newlines
    plainly_formatted_table = [re.sub(r"\S", "0", row) for row in markdown_table]
    text = text[: start_idx + 1] + markdown_table + text[end_idx:]
    bold = bold[: start_idx + 1] + plainly_formatted_table + bold[end_idx:]
    italics = italics[: start_idx + 1] + plainly_formatted_table + italics[end_idx:]

    return text, bold, italics


def preprocess(hansard_date, house):
    print(hansard_date)
    year = hansard_date[-4:]
    output_dir_path = f"pretabulation/{house}/{year}/"
    if not os.path.isdir(output_dir_path):
        os.makedirs(output_dir_path, exist_ok=True)
    sortable_date = (
        f"{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}"  # YYYY-MM-DD
    )
    output_dir_path += f"{sortable_date}/"
    if not os.path.isdir(output_dir_path):
        os.makedirs(output_dir_path, exist_ok=True)
    # store the contents of the preprocessed text file in a list
    input_dir = f"parsed_pdf/{house}/{year}/{sortable_date}/"
    with open(f"{input_dir}plaintext.txt", "r") as f:
        text = f.readlines()
    with open(f"{input_dir}bold.txt", "r") as f:
        bold = f.readlines()
    with open(f"{input_dir}italics.txt", "r") as f:
        italics = f.readlines()
    assert (
        len(text) == len(bold) == len(italics)
    ), f"Length of text, bold and italics do not match: {len(text)} vs {len(bold)} vs {len(italics)}"
    assert len([1 for line in text if "|" in line]) == 0, f"Error: pipe found in {text}"

    # insert tables
    # load tables from file
    with open(f"{input_dir}tables.json", "r") as f:
        wrapped_tables_of_page = json.load(f)

    # 23032022 has highlighted misidentified table
    if hansard_date in ["23032022", "25102017"]:
        wrapped_tables_of_page = []
    # the items are page number, page number since DOA, and tables
    tables_of_page = [page[-1] for page in wrapped_tables_of_page]
    tables = []
    for _tables in tables_of_page:
        tables += _tables

    # 051022021 has vertical cells in its third table, need reassignment
    if hansard_date == "05102021":
        with open("edit_05102021.json", "r") as f:
            edit_05102021 = json.load(f)
        tables[3] = edit_05102021
    for table in tables:
        try:
            text, bold, italics = format_table(text, bold, italics, table, hansard_date)
        except AssertionError as e:
            print(e)
            print(f"Error in {hansard_date} table {table}")
            with open(f"errors/error_tables.txt", "a") as f:
                f.write(f"{hansard_date}\n")
                f.write(f"Error in table {table}\n")
                f.write(f"{e}\n\n")

    # Done with table parsing
    expected_page_num = -1
    for row_id in range(len(text)):
        # discard header rows
        if is_header(text[row_id]):
            expected_page_num += 1
            text[row_id] = "\n"
            bold[row_id] = "\n"
            italics[row_id] = "\n"
        # due to the nature of parsing the layout, sometimes single spaces are parsed as double
        # to reduce inconsistencies, we replace all double spaces with single spaces
        # unless it is a table
        while "  " in text[row_id] and text[row_id] != "" and text[row_id][0] != "|":
            text[row_id] = text[row_id].replace("  ", " ")
            bold[row_id] = bold[row_id].replace("  ", " ")
            italics[row_id] = italics[row_id].replace("  ", " ")

        # indentation is not uniform either, and can mess with author recognition
        text[row_id] = text[row_id].strip() + "\n"
        bold[row_id] = bold[row_id].strip() + "\n"
        italics[row_id] = italics[row_id].strip() + "\n"

        # ignore the horizontal line on the DOA page
        if re.fullmatch(r"^ *[_-]+ *$", text[row_id].strip()):
            text[row_id] = "\n"
            bold[row_id] = "\n"
            italics[row_id] = "\n"

    # delete excessive newlines
    text = [row for row in text if row != "\n"]
    bold = [row for row in bold if row != "\n"]
    italics = [row for row in italics if row != "\n"]

    with open(f"{output_dir_path}plaintext.txt", "w") as f:
        f.writelines(text)
    with open(f"{output_dir_path}bold.txt", "w") as f:
        f.writelines(bold)
    with open(f"{output_dir_path}italics.txt", "w") as f:
        f.writelines(italics)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "hansard_date", help="hansard_date eg. 12102021", default="02032023", nargs="?"
    )
    # Parse arguments
    args = parser.parse_args()
    preprocess(args.hansard_date)
