# Configure parser here

from pathlib import Path

# base path for all intermediary files
BASE_PATH = Path.cwd()

# where new PDF files are expected to be and ingested into pipeline
INPUT_PIPELINE_DIR = Path.cwd().parent / "data" / "new"
