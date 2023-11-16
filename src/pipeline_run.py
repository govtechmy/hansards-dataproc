"""
This script is part of the ingestion pipeline for new hansards
as they are released by parliament daily when parliament is in session.
"""
import parse_pdf
import pretabulation_processing
import tabulate_hansard
import edit_hansards

import post_parsing_edits
import get_categories

import os
import re
import shutil
from tqdm import tqdm
from pathlib import Path


def get_filenames_in_folder(folder_path_):
    filenames_ = list(folder_path_.glob("*.pdf"))
    return filenames_


def rename_pdf_files(paths):
    for path in paths:
        match = re.search(
            r"(DR|DN)-(\d{2})(\d{2})(\d{4})\.pdf", path.name, re.IGNORECASE
        )
        if match:
            # Extract day, month, year from the match groups
            _, day, month, year = match.groups()
            # Format the new filename
            new_filename = f"dr_{year}-{month}-{day}.pdf"
            # Create a new 'upload' directory if it doesn't exist
            upload_dir = path.parent.parent / "upload"
            upload_dir.mkdir(exist_ok=True)
            # Create a new Path object for the renamed file within the 'upload' directory
            new_path = upload_dir / new_filename
            # Rename and move the file
            shutil.copy(path, new_path)


def preprocess():
    # for preprocessing
    with open("hansards_with_tables.txt", "w") as f:
        f.write("")
    with open("errors/hansards_with_parsing_errors.txt", "w") as f:
        f.write("")
    for hansard_date in tqdm(hansard_dates):
        try:
            parse_pdf.parse_hansard(hansard_date, house, ROOT_DATA_DIR)
        except Exception as e:
            print(e)
            # write this filename to file
            with open("errors/hansards_with_parsing_errors.txt", "a") as f:
                f.write(hansard_date + "\n")
            print("Error parsing " + hansard_date)
            continue


def parse_categories():
    # for preprocessing
    get_categories_files_for_deletion = [
        "warnings/empty_categories.txt",
        "errors/TOC_errors.txt",
        "warnings/long_toc_hansards.txt",
    ]
    for file in get_categories_files_for_deletion:
        if os.path.exists(file):
            os.remove(file)
    for hansard_date in tqdm(hansard_dates):
        try:
            get_categories.get_categories(hansard_date, house, ROOT_DATA_DIR)
        except:
            # write this filename to file
            with open("errors/TOC_errors.txt", "a") as f:
                f.write(hansard_date + "\n")
            print("Error parsing " + hansard_date)
            continue


def pre_tabulate():
    # for pre-tabulation
    pre_tabulation_files_for_deletion = [
        "dump/matched_tables.txt",
        "errors/error_tables.txt",
        "errors/pretabulation_errors.txt",
    ]
    for file in pre_tabulation_files_for_deletion:
        if os.path.exists(file):
            os.remove(file)
    for hansard_date in tqdm(hansard_dates):
        try:
            pretabulation_processing.preprocess(hansard_date, house)
        except Exception as e:
            print(e)
            print(f"Error in {hansard_date}")
            with open("errors/pretabulation_errors.txt", "a") as f:
                f.write(f"{hansard_date}\n")
                f.write(f"{e}\n\n")
            continue


# for tabulation
def tabulate():
    # clean these files for new logs
    tabulation_files_for_deletion = [
        "dump/autoclosed_annotation.txt",
        "dump/all_timestamps_dated.txt",
        "dump/all_timestamps.txt",
        "warnings/matched_categories.csv",
        "warnings/timestamp_in_annotation.txt",
        "warnings/autocorrected_authors.txt",
        "warnings/stray_bolds.txt",
        "warnings/capitalised_level_2.txt",
        "warnings/level_2_following_level_1.txt",
        "warnings/in-text-bold.txt",
        "warnings/annotation_too_long.txt",
        "warnings/uppercased_non_author.txt",
        "warnings/mixed_bolds.txt",
        "warnings/unsorted_timestamps.txt",
        "errors/tabulation_errors.txt",
        "warnings/toc_mismatch.txt",
    ]

    for file in tabulation_files_for_deletion:
        if os.path.exists(file):
            os.remove(file)
    for hansard_date in tqdm(hansard_dates):
        try:
            tabulate_hansard.tabulate(hansard_date, house)
        except Exception as e:
            print(e)
            print(f"Error in {hansard_date}")
            with open("errors/tabulation_errors.txt", "a") as f:
                f.write(f"{hansard_date}\n")
                f.write(f"{e}\n\n")
            continue


def clean_up():
    # copy files from 'new' folder to 'done' folder
    for filename in filenames:
        shutil.copy(filename, ROOT_DATA_DIR / "done" / filename.name)

    # copy tabulated files to 'tabulated_upload' folder
    for hansard_date in hansard_dates:
        new_hansard_date = f"{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}"

        # copy results.csv
        shutil.copy(
            Path.cwd() / "tabulated" / f"{new_hansard_date}" / "result.csv",
            ROOT_DATA_DIR / "tabulated_upload" / f"dr_{new_hansard_date}.csv",
        )
        # copy attendance files
        shutil.copy(
            Path.cwd() / "tabulated" / f"{new_hansard_date}" / "absent.txt",
            Path.cwd()
            / "tabulated_upload"
            / "new"
            / f"dr_absent_{new_hansard_date}.txt",
        )
        shutil.copy(
            Path.cwd() / "tabulated" / f"{new_hansard_date}" / "attended.txt",
            Path.cwd()
            / "tabulated_upload"
            / "new"
            / f"dr_attended_{new_hansard_date}.txt",
        )


if __name__ == "__main__":
    # Pipeline steps:
    # 1. Download new PDF files into 'new' folder
    # 2. Rename PDF files
    # 3. Run all steps
    # 4. If all good, clean up

    ROOT_DATA_DIR = Path.cwd().parent / "data"
    house = "DR"  # DR/DN

    # get list of new PDF files
    filenames = get_filenames_in_folder(ROOT_DATA_DIR)
    # rename a copy for uploading to S3
    rename_pdf_files(filenames)

    hansard_dates = [x.stem[3 : 3 + 8] for x in filenames]
    # preprocess()
    # parse_categories()
    # post_parsing_edits.post_parsing_edits()
    # pre_tabulate()
    # edit_hansards.edit_hansards()
    tabulate()

    # if all good, clean up by moving filenames to 'done' folder, and tabulated to tabulated_upload folder
    # clean_up()
