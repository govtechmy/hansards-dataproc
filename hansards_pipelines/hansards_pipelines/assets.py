import botocore.exceptions
from dagster import (
    SensorEvaluationContext,
    asset,
    sensor,
    job,
    RunRequest,
    RunConfig,
    SensorResult,
    DynamicPartitionsDefinition,
    AssetExecutionContext,
    define_asset_job,
    RunsFilter,
    DagsterRunStatus
)
import sys
import os
import io
import csv
import json
from bs4 import BeautifulSoup
import re
import boto3
import botocore
import requests
from dotenv import load_dotenv
from urllib.parse import urljoin
from typing import List
from io import BytesIO
from datetime import datetime

load_dotenv()

S3_DATAPROC_BUCKET = os.getenv("S3_DATAPROC_BUCKET")
S3_PUBLIC_BUCKET = os.getenv("S3_PUBLIC_BUCKET")

# from discord_webhook import DiscordWebhook, DiscordEmbed

# main pipeline
# 1. scrape from the website, push pdf to s3 hansards-new
# 2. move and rename hansards-new to main raw hansards folder
# 3. run parse_hansard (in: raw PDF, out: parsed_pdf folder - plaintext, bold, italics, tables, attendance.txt)
# 4. run get_categories (in: parsed_pdf files, out: parsed_pdf folder - categories.json)
# 5. [human IL] post parsing edits - human to add edits to py file based on warnings/errors, then rerun 3 and 4
# 6. run pre_tabulate (in: parsed_pdf files, out: pretabulation folder - plaintext, bold, italics.txt files)
# 7. [human IL] edit hansards - human to add edits to py file based on warnings/errors, then rerun 6
# 8. run tabulate (in: pretabulation files, out: tabulated folder - result.csv, absent.txt, attended.txt)
# 9. upload tabulated CSV to s3
# 10. load data into DB models
# from src.parse_pdf import parse_hansard
# from src.get_categories import get_categories
# from src.pretabulation_processing import preprocess

from hansards_pipelines.parse_pdf import parse_hansard
from hansards_pipelines.get_categories import get_categories
from hansards_pipelines.post_parsing_edits import post_parsing_edits
from hansards_pipelines.pretabulation_processing import preprocess
from hansards_pipelines.edit_hansards import edit_hansards
from hansards_pipelines.tabulate_hansard import tabulate

s3_client = boto3.client("s3")

house_map = {
    "dewanrakyat": "dr",
    "dewannegara": "dn",
    "kamarkhas": "kkdr",
}
house_map_reverse = {v: k for k, v in house_map.items()}


def extract_pdf_url(js_string):
    # Define the regular expression pattern to match the PDF URL
    pattern = r"loadResult\('([^']*\.pdf)'"

    # Search for the pattern in the given JavaScript string
    match = re.search(pattern, js_string)

    # If a match is found, extract and return the URL
    if match:
        return match.group(1)
    else:
        return None


def rename_pdf(filename):
    """DR-DDMMYYYY.pdf -> dr_yyyy-mm-dd.pdf"""
    match = re.search(r"(DR|DN|KKDR)-(\d{2})(\d{2})(\d{4})", filename, re.IGNORECASE)
    if match is not None:
        house, day, month, year = match.groups()
        new_filename = f"{house.lower()}_{year}-{month}-{day}"
        return new_filename
    else:
        # if fail to detect filename format, return the original filename
        return filename


def reverse_date_format(date_str):
    """YYYY-MM-DD -> DDMMYYYY"""
    year, month, day = date_str.split("-")
    return f"{day}{month}{year}"


def _get_sitting_object(pdf_file_key: str):
    """Convert PDF file key to house, date_str and datetime"""
    # DR-12122024
    house = pdf_file_key.split("-")[0].upper()  # DR
    house_folder = house_map_reverse[house.lower()]  # dr -> dewanrakyat (for s3)
    date_str = pdf_file_key.split("-")[1]  # 12122024
    date = datetime.strptime(date_str, "%d%m%Y")
    original_filename = pdf_file_key + ".pdf"
    renamed_filename = rename_pdf(pdf_file_key)  # DR-12122024 -> dr_2024-12-12.pdf
    renamed_filename_key = f"{house_folder}/{renamed_filename}"
    return {
        "house": house,
        "house_folder": house_folder,
        "date_str": date_str,
        "date": date,
        "original_filename": original_filename,
        "renamed_filename": renamed_filename,
        "renamed_filename_key": renamed_filename_key,
    }


def _build_save_dir(current_key: str, filename: str, sitting_object: dict):
    """Build save directory for parsed hansard files"""
    path_parts = [
        current_key,
        sitting_object["house_folder"],
        sitting_object["date_str"],
        filename,
    ]
    return "/".join(path_parts)


def _read_txt_file(s3_bucket, s3_key) -> List[str]:
    """Read file from s3 and return as list of string
    Replicating the behaviour of open() readlines()"""
    response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
    return response.get("Body").read().decode("utf-8").splitlines(keepends=True)


def _read_json_file(s3_bucket, s3_key) -> dict:
    """Read JSON file from s3 and return as dict"""
    response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
    return json.loads(response.get("Body").read().decode("utf-8"))


def _prepare_text_for_s3(text_lines: List[str]) -> str:
    """Ensure all lines have newline characters before joining"""
    return "".join(line if line.endswith("\n") else line + "\n" for line in text_lines)


def _prepare_json_for_s3(json_dict: dict) -> str:
    """Convert dict to JSON string"""
    return json.dumps(json_dict)


def _prepare_csv_for_s3(text_lines: List[str]) -> str:
    """Convert list of strings to CSV"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["level_1", "level_2", "level_3", "timestamp", "author", "speech"])
    writer.writerows(text_lines)
    output.seek(0)
    return output.getvalue()


sitting_partitions_def = DynamicPartitionsDefinition(name="house_sittings")
# https://github.com/dagster-io/dagster/discussions/20508


# @asset(deps=[])
def scrape_website(context: AssetExecutionContext) -> List:
    """Scrape list of PDFs and add new partition if doesn't exist
    Upload PDF file to S3"""

    # sqs = boto3.client("sqs")
    # queue_url = "https://sqs.ap-southeast-1.amazonaws.com/761623003862/NewHansardsQueue"

    base_url = "https://www.parlimen.gov.my"

    sources = [
        (
            "https://www.parlimen.gov.my/hansard-dewan-rakyat.html?&uweb=dr&lang=bm&arkib=yes",
            "dewanrakyat",
        ),
        (
            "https://www.parlimen.gov.my/hansard-dewan-negara.html?&uweb=dn&lang=bm&arkib=yes",
            "dewannegara",
        ),
        (
            "https://www.parlimen.gov.my/hansard-dewan-khas.html?uweb=dr&arkib=yes",
            "kamarkhas",
        ),
    ]
    new_pdfs = []
    for source in sources:

        source_url = source[0]
        house_folder = source[1]
        # Send a request to the base URL
        response = requests.get(source_url)
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Parse the HTML content
        soup = BeautifulSoup(response.text, "html.parser")

        # Find all <a> tags within divs with class "boxAktivitiContentText"
        divs = soup.find_all("div", class_="boxAktivitiContentText")
        for div in divs:
            a_tags = div.find_all("a")
            for a_tag in a_tags:
                pdf_path = extract_pdf_url(a_tag.get("href"))
                pdf_url = urljoin(base_url, pdf_path)
                if pdf_url.endswith(".pdf"):
                    # Determine the PDF file name
                    pdf_name = os.path.basename(pdf_url)
                    # new_pdf_name = rename_pdf(pdf_name)
                    # context.log.info(pdf_name, new_pdf_name)

                    s3_key = f"{house_folder}/{pdf_name}"
                    full_s3_key = f"new/{s3_key}"
                    # check s3 if file exists using the s3_client
                    try:
                        s3_client.head_object(
                            Bucket=S3_DATAPROC_BUCKET, Key=full_s3_key
                        )
                        context.log.info(f"{s3_key} exists in {S3_DATAPROC_BUCKET}.")
                    except botocore.exceptions.ClientError as e:
                        # new PDF: create new partition and upload to S3

                        pdf_response = requests.get(pdf_url)
                        pdf_response.raise_for_status()  # Raise an exception for HTTP errors

                        # Upload the PDF to S3
                        s3_client.put_object(
                            Bucket=S3_DATAPROC_BUCKET,
                            Key=full_s3_key,
                            Body=pdf_response.content,
                        )
                        context.log.info(
                            f"Uploaded {pdf_name} to s3://{S3_DATAPROC_BUCKET}/{full_s3_key}"
                        )
                        new_pdfs.append((pdf_name, s3_key))

    if len(new_pdfs) > 0:
        context.log.info(f"New PDFs: {new_pdfs}")

    return new_pdfs

    # # partition key: eg. dr_2022-01-01
    # run_req = RunRequest(partition_key=new_pdf_name)

    # sensor_result = SensorResult(
    #     run_requests=new_pdfs,
    #     dynamic_partitions_requests=[
    #         sitting_partitions_def.build_add_request(
    #             [new_pdf_name.partition_key for new_pdf_name in new_pdfs]
    #         )
    #     ],
    # )


sittings_job = define_asset_job(
    "sittings_job",
)


@sensor(job=sittings_job)
def sittings_sensor(context: SensorEvaluationContext):
    """Set up partitions
    One partition is one dewan, one sitting (date)
    One partition is one file still in new/
    TODO: implement actual moving of parsed PDFs from new folder
    """
    # get new pdfs

    # get all partitions in s3
    response = s3_client.list_objects_v2(Bucket=S3_DATAPROC_BUCKET, Prefix="new/")
    new_pdfs = []
    for obj in response.get("Contents", []):
        # key new/dewannegara/DN-03122024.pdf
        if obj["Key"].lower().endswith(".pdf"):
            # take filename only without extension: DN-03122024
            pdf_name = obj["Key"].split("/")[-1].split(".")[0]
            context.log.info(f"New PDF: {pdf_name}")
            new_pdfs.append(pdf_name)

            # TODO: ensure date portion is 8 digits DDMMYYYY
            date = pdf_name.split("-")[1]
            if len(date) != 8:
                context.log.warning(f"WARNING: Date portion is not 8 digits: {date}")
            # TODO: ensure house is valid
            house = pdf_name.split("-")[0]
            if house.lower() not in house_map.values():
                context.log.warning(f"WARNING: House is not valid: {house}")

    # TODO: REMOVE THIS FOR TESTING ONLY
    new_pdfs = new_pdfs[:5]
    context.log.info(f"New PDFs: {new_pdfs}")
    
    ## Only Create New Runs if Partition has no active runs
    # Get runs for each partition
    run_requests = []
    dynamic_partition_additions = []

    for pdf_name in new_pdfs:
        # Get latest run for this partition using Dagster's RunsFilter
        runs = context.instance.get_runs(
            filters=RunsFilter(
                tags={
                    "dagster/partition": pdf_name
                },
                statuses=[
                    DagsterRunStatus.STARTED,
                    DagsterRunStatus.STARTING
                ]
            )
        )
        
        # Check if there are any active runs
        has_active_run = any(runs)
        
        if not has_active_run:
            run_requests.append(RunRequest(partition_key=pdf_name))
            dynamic_partition_additions.append(pdf_name)
            context.log.info(f"Creating new run for partition: {pdf_name}")
        else:
            context.log.info(f"Skipping partition {pdf_name} - has active run")
    

    return SensorResult(
        run_requests=run_requests,
        dynamic_partitions_requests=[
            sitting_partitions_def.build_add_request(dynamic_partition_additions)
        ] if dynamic_partition_additions else []
    )


@asset(partitions_def=sitting_partitions_def)
def move_and_rename_hansards(context: AssetExecutionContext):
    """Move and rename raw hansards from new/ to main downloads folder"""

    # context.log.info(f"Moving and renaming hansards {len(scrape_website)}")

    # name of PDFs already in new/ format: DN-02122024
    sitting_object = _get_sitting_object(context.partition_key)
    house_folder = sitting_object["house_folder"]
    new_pdf_s3_key = f"new/{house_folder}/{sitting_object['original_filename']}"  # new/dewanrakyat/DN-02122024.pdf
    context.log.info(f"Moving and renaming {new_pdf_s3_key}")

    # Read from s3
    pdf_response = s3_client.get_object(Bucket=S3_DATAPROC_BUCKET, Key=new_pdf_s3_key)
    new_pdf_name = f"{house_folder}/{sitting_object['renamed_filename']}"
    # Rename and move the file
    s3_client.put_object(
        Bucket=S3_PUBLIC_BUCKET, Key=new_pdf_name, Body=pdf_response["Body"].read()
    )
    context.log.info(f"Renamed and moved {new_pdf_s3_key} to {new_pdf_name}")
    return new_pdf_name  # dewanrakyat/dr_2024-12-02.pdf


@asset(partitions_def=sitting_partitions_def, deps=[move_and_rename_hansards])
def dg_parse_hansard(context: AssetExecutionContext):
    """Parse hansard
    Output of this is parsed_pdf folder - plaintext, bold, italics, tables, attendance.txt
    """
    sitting_object = _get_sitting_object(context.partition_key)
    context.log.info(f"Parsing {sitting_object['original_filename']}")

    # read pdf from s3
    pdf_response = s3_client.get_object(
        Bucket=S3_PUBLIC_BUCKET, Key=sitting_object["renamed_filename_key"]
    )
    text, spaced_bold, spaced_italics, tables, attn_text = parse_hansard(
        sitting_object["date_str"],
        sitting_object["house"],
        "DEFAULT_DATA_DIR",
        file_content=BytesIO(pdf_response["Body"].read()),
    )
    # save to s3
    s3_key = _build_save_dir("parsed_pdf", "plaintext.txt", sitting_object)
    s3_client.put_object(Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=text)
    context.log.info(f"Uploaded plaintext to {s3_key}")
    s3_key = _build_save_dir("parsed_pdf", "bold.txt", sitting_object)
    s3_client.put_object(Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=spaced_bold)
    context.log.info(f"Uploaded bold to {s3_key}")
    s3_key = _build_save_dir("parsed_pdf", "italics.txt", sitting_object)
    s3_client.put_object(Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=spaced_italics)
    context.log.info(f"Uploaded italics to {s3_key}")
    # save tables even if empty
    s3_key = _build_save_dir("parsed_pdf", "tables.json", sitting_object)
    s3_client.put_object(Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=json.dumps(tables))
    context.log.info(f"Uploaded tables to {s3_key}")
    if attn_text != "":
        s3_key = _build_save_dir("parsed_pdf", "attendance.txt", sitting_object)
        s3_client.put_object(Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=attn_text)
        context.log.info(f"Uploaded attendance to {s3_key}")


@asset(partitions_def=sitting_partitions_def, deps=[dg_parse_hansard])
def dg_get_categories(context: AssetExecutionContext):
    """
    Reads:
    - Raw PDF

    Writes:
    - categories.json
    - toc_analysis/plaintext.txt
    - toc_analysis/bold.txt
    - toc_analysis/italics.txt

    Warnings:
    - long_toc_hansards
    - empty_categories
    - kkdr_subcategories_non_bold
    """
    sitting_object = _get_sitting_object(context.partition_key)
    context.log.info(f"Getting categories for {sitting_object['original_filename']}")

    pdf_response = s3_client.get_object(
        Bucket=S3_PUBLIC_BUCKET, Key=sitting_object["renamed_filename_key"]
    )
    (
        long_toc,
        text,
        spaced_bold,
        spaced_italics,
        empty_categories,
        kkdr_subcategories_non_bold,
        categories,
    ) = get_categories(
        sitting_object["date_str"],
        sitting_object["house"],
        file_content=BytesIO(pdf_response["Body"].read()),
    )

    if long_toc:
        # only logging required
        # TODO: feed to system-wide/central log
        context.log.info(f"Long TOC found in {context.partition_key}")
    if empty_categories:
        # only logging required
        # TODO: feed to system-wide/central log
        context.log.info(f"Empty categories found in {context.partition_key}")
    if kkdr_subcategories_non_bold:
        # only logging required
        # TODO: feed to system-wide/central log
        context.log.info(
            f"KKDR subcategories non bold found in {context.partition_key}"
        )

    s3_key = _build_save_dir("get_categories", "categories.json", sitting_object)
    s3_client.put_object(
        Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=_prepare_json_for_s3(categories)
    )
    context.log.info(f"Uploaded categories to {s3_key}")

    s3_key = _build_save_dir(
        "get_categories", "toc_analysis/plaintext.txt", sitting_object
    )
    s3_client.put_object(Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=text)
    context.log.info(f"Uploaded plaintext to {s3_key}")
    s3_key = _build_save_dir("get_categories", "toc_analysis/bold.txt", sitting_object)
    s3_client.put_object(Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=spaced_bold)
    context.log.info(f"Uploaded bold to {s3_key}")
    s3_key = _build_save_dir(
        "get_categories", "toc_analysis/italics.txt", sitting_object
    )
    s3_client.put_object(Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=spaced_italics)
    context.log.info(f"Uploaded italics to {s3_key}")


@asset(partitions_def=sitting_partitions_def, deps=[dg_get_categories])
def dg_post_parsing_edits(context: AssetExecutionContext):
    """
    Hardcoded edits to parsed text files.
    """
    sitting_object = _get_sitting_object(context.partition_key)
    # get tables.json and categories.json
    tables_s3_key = _build_save_dir("parsed_pdf", "tables.json", sitting_object)
    try:
        tables = _read_json_file(S3_DATAPROC_BUCKET, tables_s3_key)
    except botocore.exceptions.ClientError as e:
        context.log.warning(f"No tables.json found for {context.partition_key}")
        tables = None

    categories_s3_key = _build_save_dir(
        "get_categories", "categories.json", sitting_object
    )
    try:
        categories = _read_json_file(S3_DATAPROC_BUCKET, categories_s3_key)
    except botocore.exceptions.ClientError as e:
        context.log.warning(f"No categories.json found for {context.partition_key}")
        categories = None

    tables, categories = post_parsing_edits(
        sitting_object["house"],
        sitting_object["date_str"],
        tables,
        categories,
    )

    if tables:
        s3_client.put_object(
            Bucket=S3_DATAPROC_BUCKET,
            Key=tables_s3_key,
            Body=_prepare_json_for_s3(tables),
        )
        context.log.info(f"Uploaded tables to {tables_s3_key}")
    else:
        context.log.warning(f"No post parsing edits found for {context.partition_key}")
    if categories:
        s3_client.put_object(
            Bucket=S3_DATAPROC_BUCKET,
            Key=categories_s3_key,
            Body=_prepare_json_for_s3(categories),
        )
        context.log.info(f"Uploaded categories to {categories_s3_key}")
    else:
        context.log.warning(f"No TOC edits found for {context.partition_key}")


@asset(partitions_def=sitting_partitions_def, deps=[dg_post_parsing_edits])
def dg_pre_tabulate(context: AssetExecutionContext):
    """
    Reads:
    - parsed_pdf/plaintext.txt
    - parsed_pdf/bold.txt
    - parsed_pdf/italics.txt
    - parsed_pdf/tables.json

    Writes:
    - pretabulation/plaintext.txt
    - pretabulation/bold.txt
    - pretabulation/italics.txt
    """
    sitting_object = _get_sitting_object(context.partition_key)
    context.log.info(f"Pre tabulating {context.partition_key}")

    plaintext = _read_txt_file(
        S3_DATAPROC_BUCKET,
        _build_save_dir("parsed_pdf", "plaintext.txt", sitting_object),
    )
    bold = _read_txt_file(
        S3_DATAPROC_BUCKET, _build_save_dir("parsed_pdf", "bold.txt", sitting_object)
    )
    italics = _read_txt_file(
        S3_DATAPROC_BUCKET, _build_save_dir("parsed_pdf", "italics.txt", sitting_object)
    )
    tables = _read_json_file(
        S3_DATAPROC_BUCKET, _build_save_dir("parsed_pdf", "tables.json", sitting_object)
    )

    # check and warn if contents are empty
    if not plaintext:
        context.log.warning(f"No plaintext.txt found for {context.partition_key}")
    if not bold:
        context.log.warning(f"No bold.txt found for {context.partition_key}")
    if not italics:
        context.log.warning(f"No italics.txt found for {context.partition_key}")

    processed_text, processed_bold, processed_italics = preprocess(
        sitting_object["date_str"],
        sitting_object["house"],
        plaintext,
        bold,
        italics,
        tables,
        is_pipeline=True,
    )

    s3_key = _build_save_dir("pretabulation", "plaintext.txt", sitting_object)
    s3_client.put_object(
        Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=_prepare_text_for_s3(processed_text)
    )
    context.log.info(f"Uploaded plaintext to {s3_key}")
    s3_key = _build_save_dir("pretabulation", "bold.txt", sitting_object)
    s3_client.put_object(
        Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=_prepare_text_for_s3(processed_bold)
    )
    context.log.info(f"Uploaded bold to {s3_key}")
    s3_key = _build_save_dir("pretabulation", "italics.txt", sitting_object)
    s3_client.put_object(
        Bucket=S3_DATAPROC_BUCKET,
        Key=s3_key,
        Body=_prepare_text_for_s3(processed_italics),
    )
    context.log.info(f"Uploaded italics to {s3_key}")


@asset(partitions_def=sitting_partitions_def, deps=[dg_pre_tabulate])
def dg_edit_hansards(context: AssetExecutionContext):
    """
    Performs hardcoded edits to parsed txt files
    Reads:
    - pretabulation/plaintext.txt
    - pretabulation/bold.txt
    - pretabulation/italics.txt

    Writes:
    - edited_hansards/plaintext.txt
    - edited_hansards/bold.txt
    - edited_hansards/italics.txt
    """
    sitting_object = _get_sitting_object(context.partition_key)
    context.log.info(f"Editing hansards for {context.partition_key}")

    plaintext = _read_txt_file(
        S3_DATAPROC_BUCKET,
        _build_save_dir("pretabulation", "plaintext.txt", sitting_object),
    )
    bold = _read_txt_file(
        S3_DATAPROC_BUCKET, _build_save_dir("pretabulation", "bold.txt", sitting_object)
    )
    italics = _read_txt_file(
        S3_DATAPROC_BUCKET,
        _build_save_dir("pretabulation", "italics.txt", sitting_object),
    )

    text, bold, italics, num_edits = edit_hansards(
        sitting_object["house"],
        sitting_object["date_str"],
        plaintext,
        bold,
        italics,
        is_pipeline=True,
    )

    s3_key = _build_save_dir("pretabulation", "plaintext.txt", sitting_object)
    s3_client.put_object(
        Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=_prepare_text_for_s3(text)
    )
    context.log.info(f"Uploaded plaintext to {s3_key}")
    s3_key = _build_save_dir("pretabulation", "bold.txt", sitting_object)
    s3_client.put_object(
        Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=_prepare_text_for_s3(bold)
    )
    context.log.info(f"Uploaded bold to {s3_key}")
    s3_key = _build_save_dir("pretabulation", "italics.txt", sitting_object)
    s3_client.put_object(
        Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=_prepare_text_for_s3(italics)
    )
    context.log.info(f"Uploaded italics to {s3_key}")


@asset(partitions_def=sitting_partitions_def, deps=[dg_edit_hansards])
def dg_tabulate(context: AssetExecutionContext):
    """
    Tabulate txt and json files in final CSV per sitting

    Reads:
    - [FIXED] categories.json
    - pretabulation/plaintext.txt
    - pretabulation/bold.txt
    - pretabulation/italics.txt
    - parsed_pdf/categories.json (if not DN)
    - parsed_pdf/attendance.txt

    Writes:
    - tabulated/result.csv
    - tabulated/absent.txt
    - tabulated/attended.txt

    Warnings:
    - stray_bolds.txt
    - level_2_following_level_1.txt
    - mixed_bolds.txt
    - matched_categories.csv
    - capitalised_level_2.txt
    - in-text-bold.txt
    - annotation_too_long.txt
    - uppercased_non_author.txt
    - unsorted_timestamps.txt
    - toc_mismatch.txt
    """

    sitting_object = _get_sitting_object(context.partition_key)
    context.log.info(f"Tabulating {context.partition_key}")

    # get files from s3
    plaintext = _read_txt_file(
        S3_DATAPROC_BUCKET,
        _build_save_dir("pretabulation", "plaintext.txt", sitting_object),
    )
    bold = _read_txt_file(
        S3_DATAPROC_BUCKET, _build_save_dir("pretabulation", "bold.txt", sitting_object)
    )
    italics = _read_txt_file(
        S3_DATAPROC_BUCKET,
        _build_save_dir("pretabulation", "italics.txt", sitting_object),
    )
    print(f"length of plaintext: {len(plaintext)}")
    print(f"length of bold: {len(bold)}")
    print(f"length of italics: {len(italics)}")

    # read categories.json from root folder
    categories = _read_json_file(S3_DATAPROC_BUCKET, "categories.json")

    try:
        attendance = _read_txt_file(
            S3_DATAPROC_BUCKET,
            _build_save_dir("parsed_pdf", "attendance.txt", sitting_object),
        )
        # attendance txt in tabulate expects a string
        attendance = "".join(attendance)
    except botocore.exceptions.ClientError as e:
        context.log.warning(f"No attendance.txt found for {context.partition_key}")
        attendance = None

    speeches, absent_text, attended_text = tabulate(
        sitting_object["date_str"],
        sitting_object["house"],
        plaintext,
        bold,
        italics,
        categories,
        attendance,
        is_pipeline=True
    )

    s3_key = _build_save_dir("tabulated", "result.csv", sitting_object)
    s3_client.put_object(
        Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=_prepare_csv_for_s3(speeches)
    )
    context.log.info(f"Uploaded result.csv to {s3_key}")

    if absent_text:
        s3_key = _build_save_dir("tabulated", "absent.txt", sitting_object)
        s3_client.put_object(
            Bucket=S3_DATAPROC_BUCKET,
            Key=s3_key,
            Body=_prepare_text_for_s3(absent_text),
        )
        context.log.info(f"Uploaded absent.txt to {s3_key}")

    if attended_text:
        s3_key = _build_save_dir("tabulated", "attended.txt", sitting_object)
        s3_client.put_object(
            Bucket=S3_DATAPROC_BUCKET,
            Key=s3_key,
            Body=_prepare_text_for_s3(attended_text),
        )
        context.log.info(f"Uploaded attended.txt to {s3_key}")


@asset(partitions_def=sitting_partitions_def,deps=[dg_tabulate])
def remove_parsed_hansards(context: AssetExecutionContext):
    """
        Remove Hansards from /new after parsing 
        Only removes pdf if result.csv is in /tabulated and if file is moved into new folder
    """
    sitting_object = _get_sitting_object(context.partition_key)
    house_folder = sitting_object["house_folder"]
    date = sitting_object["date_str"]
    new_pdf_s3_key = f"new/{house_folder}/{sitting_object['original_filename']}"  # new/dewanrakyat/DN-02122024.pdf
    moved_pdf_key = f"{house_folder}/{sitting_object['renamed_filename']}"
    parsed_pdf_result_key = f"tabulated/{house_folder}/{date}/result.csv" # tabulated/dewanrakyat/02122024/result.csv
    
    # Check if result.csv is in /tabulated/dewanrakyat/02122024
    try:
        s3_client.head_object(Bucket=S3_DATAPROC_BUCKET, Key=parsed_pdf_result_key)
        context.log.info(f"{parsed_pdf_result_key} Verified!")
    except botocore.exceptions.ClientError:
        context.log.error(f"result.csv is not in {parsed_pdf_result_key}")
        raise botocore.exceptions.ClientError
        

    # Check if file was moved
    try:
        s3_client.head_object(Bucket=S3_PUBLIC_BUCKET, Key=moved_pdf_key)
        context.log.info(f"{moved_pdf_key}  Verified!")
    except botocore.exceptions.ClientError:
        context.log.error(f"{moved_pdf_key} not Verfied")
        raise botocore.exceptions.ClientError
    
    # Remove file from S3 bucket
    try:
        s3_client.delete_object(Bucket=S3_DATAPROC_BUCKET,Key=new_pdf_s3_key)
        context.log.info(f"Removed {new_pdf_s3_key} from s3")
    except botocore.exceptions.ClientError:
        context.log.error(f"Error removing {new_pdf_s3_key} from s3")
        raise botocore.exceptions.ClientError
        

    
# TODO: add insert to hansards DB
