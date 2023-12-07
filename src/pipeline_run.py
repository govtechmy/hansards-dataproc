"""
This script is part of the ingestion pipeline for new hansards
as they are released by parliament daily when parliament is in session.
"""
import edit_hansards

import post_parsing_edits

from run import preprocess, parse_categories, pre_tabulate, tabulate
from config import INPUT_PIPELINE_DIR, BASE_PATH

import re
import shutil
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


def clean_up():
    # copy files from 'new' folder to 'done' folder
    for filename in filenames:
        shutil.move(filename, INPUT_PIPELINE_DIR.parent / "done" / filename.name)

    # copy tabulated files to 'tabulated_upload' folder
    for hansard_date in hansard_dates:
        new_hansard_date = f"{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}"

        # copy results.csv
        shutil.copy(
            Path.cwd() / "tabulated" / house / f"{new_hansard_date}" / "result.csv",
            INPUT_PIPELINE_DIR.parent
            / "tabulated_upload"
            / "new"
            / f"dr_{new_hansard_date}.csv",
        )
        # copy attendance files
        shutil.copy(
            Path.cwd() / "tabulated" / house / f"{new_hansard_date}" / "absent.txt",
            INPUT_PIPELINE_DIR.parent
            / "tabulated_upload"
            / "new"
            / f"dr_absent_{new_hansard_date}.txt",
        )
        shutil.copy(
            Path.cwd() / "tabulated" / house / f"{new_hansard_date}" / "attended.txt",
            INPUT_PIPELINE_DIR.parent
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

    house = "DR"  # DR/DN

    # get list of new PDF files
    filenames = get_filenames_in_folder(INPUT_PIPELINE_DIR)
    # rename a copy for uploading to S3
    rename_pdf_files(filenames)

    hansard_dates = [x.stem[3 : 3 + 8] for x in filenames]
    preprocess(hansard_dates, house)
    parse_categories(hansard_dates, house)
    post_parsing_edits.post_parsing_edits()
    pre_tabulate(hansard_dates, house)
    edit_hansards.edit_hansards()
    tabulate(hansard_dates, house)

    # if all good, clean up by moving filenames to 'done' folder, and tabulated to tabulated_upload folder
    # clean_up()
