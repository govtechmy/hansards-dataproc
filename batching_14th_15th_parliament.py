import os
import preprocess
from tqdm import tqdm


def get_filenames_in_folder(folder_path_):
    filenames_ = os.listdir(folder_path_)
    return filenames_


filenames = get_filenames_in_folder("src_hansard/2023")
filenames += get_filenames_in_folder("src_hansard/2022")
filenames += get_filenames_in_folder("src_hansard/2021")
filenames += get_filenames_in_folder("src_hansard/2020")
filenames += get_filenames_in_folder("src_hansard/2019")
filenames += get_filenames_in_folder("src_hansard/2018")
hansard_dates = [x[3:3 + 8] for x in filenames]

for hansard_date in tqdm(hansard_dates):
    preprocess.preprocess_file(hansard_date)
