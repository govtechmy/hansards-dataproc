"""
Use this script to re-run the pipeline on a batch of hansards.
"""
import os
import pandas as pd
from tqdm import tqdm
from pathlib import Path

import parse_pdf
import pretabulation_processing
import tabulate_hansard
import edit_hansards
import post_parsing_edits
import get_categories


def get_filenames_in_folder(folder_path_):
    filenames_ = os.listdir(folder_path_)
    return filenames_


def get_files_in_folder(folder_path_, year=None, house=None):
    folder_path_ = Path(folder_path_)
    filenames_ = folder_path_.rglob("*.pdf")
    df = pd.DataFrame({"path": filenames_})
    df["house"] = df["path"].apply(lambda x: x.stem[:2])
    df["date"] = df["path"].apply(lambda x: x.stem[3 : 3 + 8])
    df["date"] = pd.to_datetime(df["date"], format="%d%m%Y")
    if year:
        df = df[df.date.dt.year == year]
    if house:
        df = df[df.house == house.upper()]
    return df


def preprocess():
    # for preprocessing
    with open("hansards_with_tables.txt", "w") as f:
        f.write("")
    with open("errors/hansards_with_parsing_errors.txt", "w") as f:
        f.write("")
    for hansard_date in tqdm(hansard_dates):
        try:
            parse_pdf.parse_hansard(hansard_date, house, ROOT_DATA_DIR)
        except:
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


if __name__ == "__main__":
    # directory where raw hansards PDFs are stored (flat structure)
    ROOT_DATA_DIR = Path(
        "/Users/shenghan/Code/playground/notebooks/hansards/hansards-pdf-raw"
    )
    house = "DR".upper()  # DR/DN

    # range of year
    # filenames = []
    # for year in range(2011, 2015):
    #     filenames.append(
    #         get_files_in_folder(
    #             ROOT_DATA_DIR,
    #             year=year,
    #             house=house,
    #         )
    #     )
    # filenames = pd.concat(filenames)

    # single year
    filenames = get_files_in_folder(ROOT_DATA_DIR, year=2009, house=house)

    hansard_dates = filenames["date"].dt.strftime("%d%m%Y").tolist()
    preprocess()
    parse_categories()
    post_parsing_edits.post_parsing_edits()
    pre_tabulate()
    edit_hansards.edit_hansards()
    tabulate()
