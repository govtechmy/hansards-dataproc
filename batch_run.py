import os
import parse_pdf
import pretabulation_processing
import tabulate_hansard
from tqdm import tqdm
import edit_hansards


def get_filenames_in_folder(folder_path_):
    filenames_ = os.listdir(folder_path_)
    return filenames_


filenames = []
filenames += get_filenames_in_folder("src_hansard/2023")
# for 15th parliament only
# filenames += ["DR-19122022.pdf", "DR-20122022"]
filenames += get_filenames_in_folder("src_hansard/2022")
filenames += get_filenames_in_folder("src_hansard/2021")
filenames += get_filenames_in_folder("src_hansard/2020")
filenames += get_filenames_in_folder("src_hansard/2019")
filenames += get_filenames_in_folder("src_hansard/2018")
hansard_dates = [x[3:3 + 8] for x in filenames]

# for preprocessing
# with open("hansards_with_tables.txt", "w") as f:
#     f.write("")
# for hansard_date in tqdm(hansard_dates):
#     parse_pdf.parse_hansard(hansard_date)

# for pre-tabulation
with open("matched_tables.txt", "w") as f:
    f.write("")
for hansard_date in tqdm(hansard_dates):
    pretabulation_processing.preprocess(hansard_date)

# edit_hansards.edit_hansards()

# for tabulation
# with open("category_scores.csv", "w") as f:
#     f.write("")
# for hansard_date in tqdm(hansard_dates):
#     tabulate_hansard.tabulate(hansard_date)
