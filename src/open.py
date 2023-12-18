"""Helper file for command to open the PDF file of a given date"""

import sys
import os
from config import DEFAULT_DATA_DIR, HOUSE_NAME


def open_pdf(_date):
    year = _date[-4:]
    month = _date[2:2 + 2]
    day = _date[:2]
    formatted_date = f"{year}-{month}-{day}"
    pdf_path = DEFAULT_DATA_DIR / f"{HOUSE_NAME}-{day}{month}{year}.pdf"
    parsed_path = f"parsed_pdf/{HOUSE_NAME}/{year}/{formatted_date}/plaintext.txt"
    pretabulate_path = f"pretabulation/{HOUSE_NAME}/{year}/{formatted_date}/plaintext.txt"
    tabulated_path = f"tabulated/{HOUSE_NAME}/{formatted_date}/result.csv"

    os.system(f"open {pdf_path}")
    os.system(f"open {parsed_path}")
    os.system(f"open {pretabulate_path}")
    os.system(f"open {tabulated_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python open.py <date>")
    else:
        date = sys.argv[1]
        open_pdf(date)
