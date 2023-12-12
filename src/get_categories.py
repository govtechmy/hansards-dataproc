"""Extract TOC and get all categories through bold and uppercase
"""

import argparse
import json
import re

import pandas as pd
import pdfplumber
import os
from pathlib import Path
from config import INPUT_PIPELINE_DIR, BASE_PATH


def upper_lower_ratio(text):
    upper = sum(1 for c in text if c.isupper())
    lower = sum(1 for c in text if c.islower())
    if lower == 0:
        if upper == 0:
            # no alphabets
            return 0
        return 9999
    return upper / lower


def replace_kkdr_category(kkdr_subcategories_processed, to_replace, replacement):
    ind = kkdr_subcategories_processed.index(to_replace)
    kkdr_subcategories_processed[ind] = replacement
    return kkdr_subcategories_processed


def get_categories(hansard_date, house, root_dir=INPUT_PIPELINE_DIR):
    print(f"Get categories: {hansard_date} {house}")
    year = hansard_date[-4:]
    bold = []
    italics = []
    text = ""
    kandungan_seen_idx = -1
    sortable_date = (
        f"{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}"  # YYYY-MM-DD
    )
    logged_long_toc = False
    kandungan_seen = False
    with pdfplumber.open(root_dir / f"{house}-{hansard_date}.pdf") as pdf:
        for idx, page in enumerate(pdf.pages):
            # skip until TOC
            extracted_text = page.extract_text()
            if not kandungan_seen:
                if "KANDUNGAN" in extracted_text.replace(" ", ""):
                    kandungan_seen = True
                    kandungan_seen_idx = idx
                else:
                    continue
            else:
                # TOC stops at the Senarai Ahli-Ahli, which title evolves over the years
                if re.search(
                    r"(AHLI-AHLI +DEWAN +RAKYAT)|"
                    r"(SENARAI +KEHADIRAN +AHLI-AHLI +PARLIMEN)|"
                    r"(KEHADIRAN +AHLI-AHLI +PARLIMEN)|"
                    r"(SENARAI +AHLI-AHLI +)",
                    extracted_text,
                ):
                    break
                if re.search(
                    r"(MALAYSIA\s+DEWAN +RAKYAT\s+PARLIMEN\s)|"
                    r"(MALAYSIA\s+KAMAR +KHAS\s+PARLIMEN\s+)",
                    extracted_text,
                ):
                    # hard stop, missing attendance. e.g. 2020-07-27
                    # also for Kamar Khas hansards with no attendance
                    break
            if (
                kandungan_seen
                and kandungan_seen_idx < idx
                and re.search(r"[AEIOUaeiou]", extracted_text)
                and not logged_long_toc
            ):
                # this is a Hansard where the TOC is more than two pages
                # e.g. 30032023
                logged_long_toc = True
                with open("warnings/long_toc_hansards.txt", "a") as f:
                    f.write(hansard_date + "\n")
            text += extracted_text + "\n"  # add newline to separate pages
            formatted_words = page.extract_words(extra_attrs=["fontname"])
            for word in formatted_words:
                is_bold = 0
                if "bold" in word["fontname"].lower():
                    is_bold = 1
                is_italic = 0
                if "italic" in word["fontname"].lower():
                    is_italic = 1
                bold += [is_bold] * len(word["text"])
                italics += [is_italic] * len(word["text"])

    assert len(bold) == len(
        italics
    ), f"Length of bold and italics do not match: {len(bold)} vs {len(italics)}"
    raw_text = re.sub(r"\s+", "", text)
    assert len(bold) == len(
        raw_text
    ), f"Length of bold and raw_text do not match: {len(bold)} vs {len(raw_text)}"
    # add whitespace to bold and italics using the raw text layout
    spaced_bold = ""
    spaced_italics = ""
    # to improve time complexity, reverse the string and pop from the end
    bold.reverse()
    italics.reverse()
    for char in text:
        if char.isspace():
            spaced_bold += char
            spaced_italics += char
        else:
            spaced_bold += str(bold.pop())
            spaced_italics += str(italics.pop())
    assert len(bold) == 0, f"Not all bold characters were processed: {len(bold)}"
    assert (
        len(italics) == 0
    ), f"Not all italic characters were processed: {len(italics)}"

    dir_path = BASE_PATH / "parsed_pdf" / house / year
    dir_path.mkdir(parents=True, exist_ok=True)
    dir_path /= f"{sortable_date}"
    dir_path.mkdir(parents=True, exist_ok=True)
    dir2_path = dir_path / "toc_analysis"
    dir2_path.mkdir(parents=True, exist_ok=True)

    with open(dir2_path / "plaintext.txt", "w") as f:
        f.write(text)
    with open(dir2_path / "bold.txt", "w") as f:
        f.write(spaced_bold)
    with open(dir2_path / "italics.txt", "w") as f:
        f.write(spaced_italics)

    text = re.sub(
        r"\(Halaman +\d+ ?\)", "!!!", text
    )  # this is to allow upper_lower_ratio to work
    # keep in mind that text is now out of sync of bold and italics at the inline level
    lines = text.split("\n")
    bold_lines = spaced_bold.split("\n")
    # get the line index where the TOC starts
    toc_start_idx = 0
    while not re.search(r"K *A *N *D *U *N *G *A *N", lines[toc_start_idx]):
        toc_start_idx += 1

    lines = lines[toc_start_idx + 1 :]
    bold_lines = bold_lines[toc_start_idx + 1 :]
    line_idx = -1
    categories = []
    kkdr_subcategories = []
    kkdr_subcategories_non_bold = []
    while line_idx + 1 < len(lines):
        line_idx += 1
        # check if current line is category
        if "1" in bold_lines[line_idx] and upper_lower_ratio(lines[line_idx]) > 1:
            category = lines[line_idx].strip()
            # check if the next line is a continuation of category
            add_idx = 1
            while (
                line_idx + add_idx < len(lines)
                and upper_lower_ratio(lines[line_idx + add_idx]) > 1
                and "!!!" not in lines[line_idx + add_idx - 1]
            ):
                category += " " + lines[line_idx + add_idx].strip()
                add_idx += 1
            line_idx += add_idx - 1
            categories.append(category.replace("!!!", "").strip())
        elif (
            lines[line_idx].strip().startswith("o ")
            or lines[line_idx].strip().startswith("• ")
            or lines[line_idx].strip().startswith("■ ")
            and house.upper() == "KKDR"
        ):
            # with bullets in KANDUNGAN page, 99.9% most likely to be KKDR subcategory
            category = lines[line_idx].strip()
            if "1" not in bold_lines[line_idx]:
                kkdr_subcategories_non_bold.append(category)

            add_idx = 1
            while (
                line_idx + add_idx < len(lines)
                and lines[line_idx + add_idx].strip() != ""
                and not lines[line_idx + add_idx]
                .strip()
                .startswith("__")  # end at footer for some cases
                and not (
                    lines[line_idx + add_idx].strip().startswith("o ")
                    or lines[line_idx + add_idx].strip().startswith("• ")
                    or lines[line_idx + add_idx].strip().startswith("■ ")
                )
            ):
                category += " " + lines[line_idx + add_idx].strip()
                add_idx += 1
                # print("KKDR subcategory: ", category)

            line_idx += add_idx - 1

            kkdr_subcategories.append(category.replace("!!!", "").strip())

    if len(kkdr_subcategories) == 0 and house.upper() == "KKDR":
        print("No KKDR subcategories found!")

    if len(categories) == 0:
        with open("warnings/empty_categories.txt", "a") as f:
            f.write(f"Empty category found in {hansard_date}" + "\n")
    if len(kkdr_subcategories_non_bold) > 0 and house.upper() == "KKDR":
        with open("warnings/kkdr_subcategories_non_bold.txt", "a") as f:
            f.write(f"{hansard_date}" + "\n")

    # global logging
    # preprocessing to remove : and strip
    categories = [x.strip().rstrip(":").strip() for x in categories]
    # delete empty category
    categories = [x for x in categories if x != ""]
    # delete typo
    # 12112018
    categories = [x for x in categories if x != "USUL-USUL:P"]
    # get the count of each category
    category_count = [(x, categories.count(x)) for x in categories]
    category_count = list(set(category_count))
    # export the category count to csv using pandas
    df = pd.DataFrame(category_count, columns=["category", "count"])
    categories = list(set(categories))
    categories.sort()

    # handle KKDR subcategories
    kkdr_subcategories_processed = []
    if house.upper() == "KKDR" and len(kkdr_subcategories) > 0:
        for subcat in kkdr_subcategories:
            if subcat == "":
                continue
            subcat = subcat.strip().lstrip("o • ■ ").strip()
            subcat = re.sub(" +", " ", subcat)
            if any(x in subcat for x in [" - ", " – ", " -Y", " –Y"]):
                # remove YB name after dash
                # some eg: 15032023 missing space after dash ".. -YB.."
                # only 04042023 doesn't have a dash
                subcat = re.split(" - | – | -Y| –Y", subcat)[0].strip()
            else:
                print("KKDR subcategory without dash!", subcat)
            kkdr_subcategories_processed.append(subcat)

        if hansard_date == "16022023":
            # 16022023 has wrong content in TOC
            kkdr_subcategories_processed = kkdr_subcategories_processed[:-1]
            kkdr_subcategories_processed.append(
                "Isu Penambahbaikan Jalan Raya di Sepanjang Jalan Utama Batu Pahat-Semerah, Batu Pahat"
            )
        if hansard_date == "04042017":
            # missing from TOC
            kkdr_subcategories_processed.append("Isu Rumah Mampu Milik")

        if hansard_date == "28032017":
            # replace trimmed text with dash
            kkdr_subcategories_processed = replace_kkdr_category(
                kkdr_subcategories_processed,
                "Status Tidak Berjaya Terhadap Permohonan Berulang",
                "Status Tidak Berjaya Terhadap Permohonan Berulang - Jawatan Pegawai Perkhidmatan Pendidikan Gred DG41",
            )
        if hansard_date == "11112019":
            kkdr_subcategories_processed = replace_kkdr_category(
                kkdr_subcategories_processed,
                "Pertanyaan Mengenai Projek Pembangunan Lanskap Pesisiran Sungai Batu Pahat dan Projek Naik Taraf Kompleks Niaga Benteng Peserai di Parlimen Parit Sulong",
                "Status Projek Pembangunan Landskap Persisiran Sungai Batu Pahat dan Projek Naik Taraf Kompleks Niaga Benteng Peserai di Parlimen Parit Sulong",
            )
        if hansard_date == "27082020":
            kkdr_subcategories_processed = replace_kkdr_category(
                kkdr_subcategories_processed,
                "Kewarganegaraan Keluarga Soon YB. Tuan Khoo Poay Tiong (Kota Melaka)",
                "Kewarganegaraan Keluarga Soon",
            )
        if hansard_date == "14032022":
            kkdr_subcategories_processed = replace_kkdr_category(
                kkdr_subcategories_processed,
                "Memohon Kementerian Dalam Negeri Menyatakan Status Permohonan Kewarganegaraan Clara Sonia Joseph",
                "Status Permohonan Kewarganegaraan Clara Sonia Joseph",
            )

        kkdr_subcategories = list(set(kkdr_subcategories_processed))
        # KKDR categories.json contains two lists
        categories = [categories, kkdr_subcategories]

    # dump to json
    with open(dir_path / "categories.json", "w") as f:
        json.dump(categories, f, indent=4)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "hansard_date", help="hansard_date eg. 23052023", default="30032023", nargs="?"
    )
    # Parse arguments
    args = parser.parse_args()
    get_categories(args.hansard_date)
