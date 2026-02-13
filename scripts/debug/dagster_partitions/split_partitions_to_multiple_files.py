"""
This standalone script reads a JSON file containing a list of partitions and splits them into
multiple smaller JSON files, each containing a specified number of partitions.

Reason: Dagster cannot handle very large partition lists in a single file, so this script helps to break them
down into manageable chunks.
"""

import json
import math
import os

INPUT_FILE = "example-arkib_partitions.pending.json"
CHUNK_SIZE = 100

with open(INPUT_FILE, "r") as f:
    data = json.load(f)

partitions = data["partitions"]

total_files = math.ceil(len(partitions) / CHUNK_SIZE)

for i in range(total_files):
    start = i * CHUNK_SIZE
    end = start + CHUNK_SIZE
    chunk = partitions[start:end]

    chunk_payload = {
        "generated_at": data["generated_at"],
        "criteria": data["criteria"],
        "partitions": chunk,
    }

    output_file = f"{i+1}-legacy_partitions.ready.json"

    with open(output_file, "w") as f:
        json.dump(chunk_payload, f, indent=2)

print(f"Split {len(partitions)} partitions into {total_files} files.")
