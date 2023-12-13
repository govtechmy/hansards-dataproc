import os
import pandas as pd
from tqdm import tqdm
from pathlib import Path

import parse_pdf
import pretabulation_processing
import tabulate_hansard
import get_categories
from config import DEFAULT_DATA_DIR


def get_filenames_in_folder(folder_path_):
    filenames_ = os.listdir(folder_path_)
    return filenames_


def get_files_in_folder(folder_path, year=None, house=None):
    """
    Get all files in folder_path with extension .pdf
    Optionally filterable by year and house
    """
    filenames_ = Path(folder_path).rglob("*.pdf")
    df = pd.DataFrame({"path": filenames_})
    df["house"] = df["path"].apply(lambda x: x.stem[:2])
    df["date"] = df["path"].apply(lambda x: x.stem[3 : 3 + 8])
    df["date"] = pd.to_datetime(df["date"], format="%d%m%Y")
    if year:
        df = df[df.date.dt.year == year]
    if house:
        df = df[df.house == house.upper()]
    return df


def preprocess(hansard_dates, house):
    # for preprocessing
    with open("hansards_with_tables.txt", "w") as f:
        f.write("")
    with open(f"errors/{house}/hansards_with_parsing_errors.txt", "w") as f:
        f.write("")
    for hansard_date in tqdm(hansard_dates):
        try:
            parse_pdf.parse_hansard(hansard_date, house, DEFAULT_DATA_DIR)
        except:
            # write this filename to file
            with open(f"errors/{house}/hansards_with_parsing_errors.txt", "a") as f:
                f.write(hansard_date + "\n")
            print("Error parsing " + hansard_date)
            continue


def parse_categories(hansard_dates, house):
    # for preprocessing
    get_categories_files_for_deletion = [
        f"warnings/{house}/empty_categories.txt",
        f"errors/{house}/TOC_errors.txt",
        f"warnings/{house}/long_toc_hansards.txt",
        f"warnings/{house}/kkdr_subcategories_non_bold.txt",
    ]
    for file in get_categories_files_for_deletion:
        if os.path.exists(file):
            os.remove(file)
    for hansard_date in tqdm(hansard_dates):
        try:
            get_categories.get_categories(hansard_date, house, DEFAULT_DATA_DIR)
        except:
            # write this filename to file
            with open(f"errors/{house}/TOC_errors.txt", "a") as f:
                f.write(hansard_date + "\n")
            print("Error parsing " + hansard_date)
            continue


def pre_tabulate(hansard_dates, house):
    # for pre-tabulation
    pre_tabulation_files_for_deletion = [
        f"dump/{house}/matched_tables.txt",
        f"errors/{house}/error_tables.txt",
        f"errors/{house}/pretabulation_errors.txt",
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
            with open(f"errors/{house}/pretabulation_errors.txt", "a") as f:
                f.write(f"{hansard_date}\n")
                f.write(f"{e}\n\n")
            continue


# for tabulation
def tabulate(hansard_dates, house):
    # clean these files for new logs
    tabulation_files_for_deletion = [
        f"dump/{house}/autoclosed_annotation.txt",
        f"dump/{house}/all_timestamps_dated.txt",
        f"dump/{house}/all_timestamps.txt",
        f"warnings/{house}/matched_categories.csv",
        f"warnings/{house}/timestamp_in_annotation.txt",
        f"warnings/{house}/autocorrected_authors.txt",
        f"warnings/{house}/stray_bolds.txt",
        f"warnings/{house}/capitalised_level_2.txt",
        f"warnings/{house}/level_2_following_level_1.txt",
        f"warnings/{house}/in-text-bold.txt",
        f"warnings/{house}/annotation_too_long.txt",
        f"warnings/{house}/uppercased_non_author.txt",
        f"warnings/{house}/mixed_bolds.txt",
        f"warnings/{house}/unsorted_timestamps.txt",
        f"errors/{house}/tabulation_errors.txt",
        f"warnings/{house}/toc_mismatch.txt",
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
            with open(f"errors/{house}/tabulation_errors.txt", "a") as f:
                f.write(f"{hansard_date}\n")
                f.write(f"{e}\n\n")
            continue
