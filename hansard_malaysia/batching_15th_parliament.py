import os
import generate_markup


def get_filenames_in_folder(folder_path_):
    filenames_ = os.listdir(folder_path_)
    return filenames_


# Example usage:
folder_path = "src_hansard/downloads/2023"
filenames = get_filenames_in_folder(folder_path)
hansard_dates = [x[3:3 + 8] for x in filenames]

hansard_dates.append("19122022")
hansard_dates.append("20122022")

for hansard_date in hansard_dates:
    generate_markup.process_file(hansard_date)
