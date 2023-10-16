import os
import parse_pdf
import pretabulation_processing
import tabulate_hansard
from tqdm import tqdm
import edit_hansards
import post_parsing_edits


def get_filenames_in_folder(folder_path_):
    filenames_ = os.listdir(folder_path_)
    return filenames_


def preprocess():
    # for preprocessing
    with open("hansards_with_tables.txt", "w") as f:
        f.write("")
    with open("errors/hansards_with_parsing_errors.txt", "w") as f:
        f.write("")
    for hansard_date in tqdm(hansard_dates):
        try:
            parse_pdf.parse_hansard(hansard_date)
        except:
            # write this filename to file
            with open("errors/hansards_with_parsing_errors.txt", "a") as f:
                f.write(hansard_date + "\n")
            print("Error parsing " + hansard_date)
            continue


def pre_tabulate():
    # for pre-tabulation
    pre_tabulation_files_for_deletion = [
        "dump/matched_tables.txt",
        "errors/error_tables.txt",
        "errors/pretabulation_errors.txt"
    ]
    for file in pre_tabulation_files_for_deletion:
        if os.path.exists(file):
            os.remove(file)
    for hansard_date in tqdm(hansard_dates):
        try:
            pretabulation_processing.preprocess(hansard_date)
        except Exception as e:
            print(e)
            print(f'Error in {hansard_date}')
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
        'warnings/timestamp_in_annotation.txt',
        "warnings/autocorrected_authors.txt",
        "warnings/stray_bolds.txt",
        "warnings/capitalised_level_2.txt",
        "warnings/level_2_following_level_1.txt",
        "warnings/in-text-bold.txt",
        "warnings/annotation_too_long.txt",
        "warnings/uppercased_non_author.txt",
        "warnings/mixed_bolds.txt",
        "warnings/unsorted_timestamps.txt",
        "errors/tabulation_errors.txt"
    ]

    for file in tabulation_files_for_deletion:
        if os.path.exists(file):
            os.remove(file)
    for hansard_date in tqdm(hansard_dates):
        try:
            tabulate_hansard.tabulate(hansard_date)
        except Exception as e:
            print(e)
            print(f'Error in {hansard_date}')
            with open("errors/tabulation_errors.txt", "a") as f:
                f.write(f"{hansard_date}\n")
                f.write(f"{e}\n\n")
            continue


if __name__ == "__main__":
    filenames = []
    filenames += get_filenames_in_folder("src_hansard/2023")
    # for 15th parliament only
    # filenames += ["DR-19122022.pdf", "DR-20122022"]
    filenames += get_filenames_in_folder("src_hansard/2022")
    filenames += get_filenames_in_folder("src_hansard/2021")
    filenames += get_filenames_in_folder("src_hansard/2020")
    filenames += get_filenames_in_folder("src_hansard/2019")
    filenames += get_filenames_in_folder("src_hansard/2018")
    # loop through years 2008-2017 in desceding order
    for year in range(2008, 2017 + 1)[::-1]:
        filenames += get_filenames_in_folder("src_hansard/" + str(year))

    hansard_dates = [x[3:3 + 8] for x in filenames]
    # preprocess()
    post_parsing_edits.modify_tables()
    pre_tabulate()
    edit_hansards.edit_hansards()
    tabulate()
