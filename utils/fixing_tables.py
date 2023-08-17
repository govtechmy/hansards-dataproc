"""Go through the legacy old_hansards_with_tables and reparse using updated settings
"""

import preprocess
from tqdm import tqdm

if __name__ == "__main__":
    with open("old_hansards_with_tables.txt", 'r') as f:
        hansards = f.readlines()
    for hansard in tqdm(hansards):
        year, month, day = hansard.strip().split('-')
        hansard_date = f"{day}{month}{year}"
        preprocess.preprocess_file(hansard_date)
