import os
import parse_pdf
import pretabulation_processing
import tabulate_hansard
from tqdm import tqdm
import edit_hansards

# somehow the file cwd is not its current folder, so now setting cwd to the current folder
# __file__ is a built-in variable which outputs the path of the current script
# os.path.dirname(__file__) gets the directory of the current script
# os.path.abspath converts a pathname into an absolute pathname
current_dir = os.path.dirname(os.path.abspath(__file__))

# os.chdir changes the current working directory to the specified path.
os.chdir(current_dir)


def get_filenames_in_folder(folder_path_):
    filenames_ = os.listdir(folder_path_)
    return filenames_


filenames = []
# filenames += get_filenames_in_folder("src_hansard/2023")
# for 15th parliament only
# filenames += ["DN-19122022.pdf", "DN-20122022"]
# filenames += get_filenames_in_folder("src_hansard/2022")
# filenames += get_filenames_in_folder("src_hansard/2021")
# filenames += get_filenames_in_folder("src_hansard/2020")
# filenames += get_filenames_in_folder("src_hansard/2019")
# filenames += get_filenames_in_folder("src_hansard/2018")
# loop through years 2008-2017 in desceding order
for year in range(2008, 2017 + 1)[::-1]:
    filenames += get_filenames_in_folder("src_hansard/" + str(year))

hansard_dates = [x[3:3 + 8] for x in filenames]

# for preprocessing
with open("hansards_with_tables.txt", "w") as f:
    f.write("")
with open("warnings/hansards_with_parsing_errors.txt", "w") as f:
    f.write("")
for hansard_date in tqdm(hansard_dates):
    try:
        parse_pdf.parse_hansard(hansard_date)
    except:
        # write this filename to file
        with open("warnings/hansards_with_parsing_errors.txt", "a") as f:
            f.write(hansard_date + "\n")
        print("Error parsing " + hansard_date)
        continue

# for pre-tabulation
with open("matched_tables.txt", "w") as f:
    f.write("")
for hansard_date in tqdm(hansard_dates):
    pretabulation_processing.preprocess(hansard_date)

# edit_hansards.edit_hansards()

# for tabulation
# clean these files for new logs
tabulation_files_for_deletion = [
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
]

for file in tabulation_files_for_deletion:
    if os.path.exists(file):
        os.remove(file)
for hansard_date in tqdm(hansard_dates):
    tabulate_hansard.tabulate(hansard_date)
