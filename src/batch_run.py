"""
Use this script to re-run the pipeline on a batch of hansards.
"""
import os
import re
import pandas as pd
from tqdm import tqdm
from pathlib import Path

import edit_hansards
import post_parsing_edits

from run import preprocess, parse_categories, pre_tabulate, tabulate
from config import DEFAULT_DATA_DIR, HOUSE_NAME


def get_filenames_in_folder(folder_path_):
    filenames_ = os.listdir(folder_path_)
    return filenames_


def get_files_in_folder(folder_path, house=None, year=None):
    """
    Get all files in folder_path with extension .pdf
    Filenames expected to be in the orignal format (eg. DR-01012021.pdf)
    House types supported: DR, DN, KKDR
    Optionally filterable by year and house
    """
    filenames_ = Path(folder_path).rglob("*.pdf")
    df = pd.DataFrame({"path": filenames_})
    pdf_file_pattern = r"(KKDR|DR|DN)-(\d{2})(\d{2})(\d{4})\.pdf"
    df["date"] = pd.to_datetime(
        df["path"]
        .astype(str)
        .str.extract(pdf_file_pattern, re.IGNORECASE)
        .apply(lambda x: "".join(x[1:].dropna().astype(str)), axis=1),
        format="%d%m%Y",
    )
    df["house"] = (
        df["path"]
        .astype(str)
        .str.extract(pdf_file_pattern, re.IGNORECASE)
        .apply(lambda x: x[0], axis=1)
    )
    if year:
        df = df[df.date.dt.year == year]
    if house:
        df = df[df.house == house.upper()]
    return df


if __name__ == "__main__":
    # range of year
    # filenames = []
    # for year in range(2013, 2024):
    #     filenames.append(
    #         get_files_in_folder(
    #             DEFAULT_DATA_DIR,
    #             house=HOUSE_NAME,
    #             year=year,
    #         )
    #     )
    # filenames = pd.concat(filenames)

    # single year
    filenames = get_files_in_folder(DEFAULT_DATA_DIR, house=HOUSE_NAME)

    hansard_dates = filenames["date"].dt.strftime("%d%m%Y").tolist()
    # preprocess(hansard_dates, HOUSE_NAME)
    # if HOUSE_NAME.upper() != "DN":
    #     parse_categories(hansard_dates, HOUSE_NAME)
    # post_parsing_edits.post_parsing_edits(HOUSE_NAME)
    # pre_tabulate(hansard_dates, HOUSE_NAME)
    # edit_hansards.edit_hansards(HOUSE_NAME)
    tabulate(hansard_dates, HOUSE_NAME)
