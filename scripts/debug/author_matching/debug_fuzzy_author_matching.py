"""
This script is for debugging fuzzy matching of author names.
Reason: To help diagnose why certain names are or are not matching as expected in the author matching process.
"""


import pandas as pd
from thefuzz import fuzz, process
from hansards_pipelines.hansards_pipelines.author_matching import normalize_malaysian_name
import requests
import warnings

from hansards_pipelines.hansards_pipelines.settings import DEV_API_URL
warnings.filterwarnings("ignore", category=FutureWarning)

# Replace with the actual author_df you loaded from API
author_df = pd.DataFrame(requests.get(DEV_API_URL).json())

# Normalize names from author_df
author_df["name_norm"] = author_df["name"].apply(normalize_malaysian_name)
author_df["name_up"] = author_df["name_norm"].str.upper()

# Name you're testing
raw_input = "Tuan Ng Peng Hay"

# Step 1: Normalize the name like your code does
norm_name = normalize_malaysian_name(raw_input).upper()
print(f"Normalized input: {norm_name}")

# Step 2: Run fuzzy matching using token_set_ratio
matches = process.extract(norm_name, author_df["name_up"].unique(), scorer=fuzz.token_set_ratio)

# Step 3: Show top 10 matches with scores
print("\nTop fuzzy matches:")
for match, score in matches[:10]:
    print(f"→ {match:30} | Score: {score}")

# Step 4: Check if any matches exceed threshold (e.g. 70)
threshold = 70
passing_matches = [(m, s) for m, s in matches if s >= threshold]

if not passing_matches:
    print("\nNo matches exceeded threshold. Match should NOT have occurred.")
else:
    print("\nMatches that exceeded threshold:")
    for match, score in passing_matches:
        matched_row = author_df[author_df["name_up"] == match]
        print(f"{match} (score {score}) → new_author_id: {matched_row['new_author_id'].values[0]}")
