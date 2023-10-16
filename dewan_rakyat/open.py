"""Helper file for command to open the PDF file of a given date"""

import sys
import os


def open_pdf(_date):
    year = _date[-4:]
    month = _date[2:2+2]
    day = _date[:2]
    formatted_date = f"{year}-{month}-{day}"
    pdf_path = f"src_hansard/{year}/DR-{_date}.pdf"
    parsed_path = f"parsed_pdf/{year}/{formatted_date}/plaintext.txt"
    pretabulate_path = f"pretabulation/{year}/{formatted_date}/plaintext.txt"
    tabulated_path = f"tabulated/{year}/{formatted_date}/result.csv"

    if os.path.exists(pdf_path):
        os.system(f"open {pdf_path}")  # for macOS
        os.system(f"open {parsed_path}")
        os.system(f"open {pretabulate_path}")
        os.system(f"open {tabulated_path}")
        # For Windows, you can use: os.system(f"start {pdf_path}")
        # For Linux, you can use: os.system(f"xdg-open {pdf_path}")
    else:
        print(f"Error: File {pdf_path} not found.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python open.py <date>")
    else:
        date = sys.argv[1]
        open_pdf(date)
