import os
import get_categories
from tqdm import tqdm
import random


def get_filenames_in_folder(folder_path_):
    filenames_ = os.listdir(folder_path_)
    return filenames_


filenames = []
filenames += get_filenames_in_folder("../src_hansard/2023")
# for 15th parliament only
# filenames += ["DR-19122022.pdf", "DR-20122022"]
filenames += get_filenames_in_folder("../src_hansard/2022")
filenames += get_filenames_in_folder("../src_hansard/2021")
filenames += get_filenames_in_folder("../src_hansard/2020")
filenames += get_filenames_in_folder("../src_hansard/2019")
filenames += get_filenames_in_folder("../src_hansard/2018")
hansard_dates = [x[3:3 + 8] for x in filenames]

print(len(hansard_dates))
# hansard_dates = random.sample(hansard_dates, 50)

for hansard_date in tqdm(hansard_dates):
    # preprocess.preprocess_file(hansard_date)
    get_categories.get_categories(hansard_date)
