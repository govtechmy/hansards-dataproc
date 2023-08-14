"""Uses the output of preprocess.py to generate the csv file of speeches"""
import argparse
import os


def tabulate(hansard_date):
    year = hansard_date[-4:]
    dir_path = f"tabulated/{year}/"
    if not os.path.isdir(dir_path):
        os.mkdir(dir_path)
    sortable_date = f'{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}'  # YYYY-MM-DD
    dir_path += f"{sortable_date}/"
    if not os.path.isdir(dir_path):
        os.mkdir(dir_path)

    # the strategy is to iterate across rows
    # store the contents of the preprocessed text file in a list
    with open(f"preprocessed/{year}/{sortable_date}/plaintext.txt", 'r') as f:
        text = f.readlines()
    with open(f"preprocessed/{year}/{sortable_date}/bold.txt", 'r') as f:
        bold = f.readlines()
    with open(f"preprocessed/{year}/{sortable_date}/italics.txt", 'r') as f:
        italics = f.readlines()
    assert len(text) == len(bold) == len(italics), \
        f'Length of text, bold and italics do not match: {len(text)} vs {len(bold)} vs {len(italics)} '


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("hansard_date", help="hansard_date eg. 23052023",
                        default="28032023", nargs="?")
    # Parse arguments
    args = parser.parse_args()
    tabulate(args.hansard_date)
