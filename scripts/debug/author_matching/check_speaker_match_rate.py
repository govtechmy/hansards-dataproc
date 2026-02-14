"""
This script is for debugging speaker assignment issues. 

- It loads speech data from a JSON payload.
- creates a DataFrame, and analyzes the presence of speaker information. 
- It provides a breakdown of rows with and without speaker data, displays unique combinations of authors and speakers, and calculates the author match rate.

Match rate only counts rows where speaker is not null as matched.
"""


import json
import pandas as pd

# Load payload
with open("payload_1991-02-18.json") as f:
    payload = json.load(f)

speech_data = json.loads(payload["speech_data"])
df = pd.DataFrame(speech_data)

# Breakdown
null_speaker = df[df["speaker"].isnull()]
non_null_speaker = df[df["speaker"].notnull()]

print(f"Total rows: {len(df)}")
print(f"With speaker: {len(non_null_speaker)}")
print(f"Without speaker: {len(null_speaker)}")

# Display only unique combinations
print("\n# Unique samples with speaker:")
print(non_null_speaker[["author", "speaker"]].drop_duplicates().head(50).to_string(index=False))

print("\n# Unique samples without speaker:")
print(null_speaker[["author", "speaker"]].drop_duplicates().head(10).to_string(index=False))

match_rate = len(non_null_speaker) / len(df) * 100
print(f"\nAuthor Match Rate: {match_rate:.2f}%")
