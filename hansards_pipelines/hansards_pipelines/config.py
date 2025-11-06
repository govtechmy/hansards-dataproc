# Configure parser here
from pathlib import Path

# house to parse: DR, DN, KKDR
HOUSE_NAME = "DR"

# base path for all intermediary files
BASE_PATH = Path.cwd()

# FOR BATCH RUN: source PDF folder
# DEFAULT_DATA_DIR = Path(
#     "/Users/shenghan/Code/playground/notebooks/hansards/hansards-pdf-raw"
# )
DEFAULT_DATA_DIR = Path.cwd().parent / "data" / "debug"

# FOR PIPELINE: where new PDF files are expected to be and ingested into pipeline
INPUT_PIPELINE_DIR = Path.cwd().parent / "data" / "new"
