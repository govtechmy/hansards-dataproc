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
    DagsterRunStatus,
    MaterializeResult,
    Output,
)
import os
import io
import json
import pickle
from bs4 import BeautifulSoup
import boto3
import botocore
import requests
import pandas as pd
from dotenv import load_dotenv
from urllib.parse import urljoin
from typing import List, Tuple, Dict
from io import BytesIO
from datetime import datetime

from hansards_pipelines.utils.text_utils import (
    preprocess_malaya,
    process_tabulated,
    speeches_to_json,
    extract_pdf_url,
    get_sitting_object,
    house_mapper,
)
from hansards_pipelines.author_matching import perform_author_matching
from hansards_pipelines.utils.discord_utils import send_discord_message
from hansards_pipelines.utils.s3_utils import (
    read_txt_file,
    read_json_file,
    prepare_text_for_s3,
    prepare_json_for_s3,
    prepare_csv_for_s3,
    build_path,
)

load_dotenv()

S3_DATAPROC_BUCKET = os.getenv("S3_DATAPROC_BUCKET")
S3_PUBLIC_BUCKET = os.getenv("S3_PUBLIC_BUCKET")
DEV_API_URL = os.getenv("DEV_API_URL")
PROD_API_URL = os.getenv("PROD_API_URL")

FRONTEND_URL = os.getenv("FRONTEND_URL")
FRONTEND_TOKEN = os.getenv("FRONTEND_TOKEN")

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


house_names = ["DR", "DN", "KKDR"]


sitting_partitions_def = DynamicPartitionsDefinition(name="house_sittings")
# https://github.com/dagster-io/dagster/discussions/20508


def _generate_new_hansard_message(
    new_pdfs: list, skipped_pdfs: list, context: AssetExecutionContext
):

    file_name_str = ""
    for new_pdf in new_pdfs:
        file_name_str += f"{new_pdf[0]} to {new_pdf[2]}\n"

    skipped_file_name_str = ""
    for skipped_pdf in skipped_pdfs:
        skipped_file_name_str += f"{skipped_pdf}\n"

    message_fields = [{"name": "New PDFs", "value": file_name_str, "inline": True}]
    if len(skipped_pdfs) > 0:
        message_fields.append(
            {"name": "Skipped PDFs", "value": skipped_file_name_str, "inline": True}
        )
    footer = {"text": "Parliament Hansards Web Scraper"}
    send_discord_message(
        "",
        f"✨ New Hansards Scraped!",
        3066993,
        message_fields,
        footer,
        context,
        deeplink=False,
    )


@asset(group_name="scrape")
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
    skipped_pdfs = []
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
                    pdf_name = os.path.basename(pdf_url).split(".")[
                        0
                    ]  # KKDR-20022025-1

                    # Try to rename and correct PDF file name here eg. KKDR-20022025-1
                    pdf_name_parts = pdf_name.split("-")
                    if len(pdf_name_parts) != 2:
                        context.log.warning(
                            f"WARNING: PDF file name is not in the correct format: {pdf_name}"
                        )
                    house = pdf_name_parts[0]
                    date = pdf_name_parts[1]
                    if house not in house_names:
                        context.log.warning(
                            f"ERROR: House is not valid: {house}. Skipping"
                        )
                        skipped_pdfs.append(pdf_name)
                        continue
                    if len(date) != 8:
                        context.log.warning(
                            f"ERROR: Date portion is not 8 digits: {date}. Skipping"
                        )
                        skipped_pdfs.append(pdf_name)
                        continue
                    pdf_name = f"{house}-{date}.pdf"

                    s3_key = f"{house_folder}/{pdf_name}"
                    full_s3_key = f"new/{s3_key}"
                    # check s3 if file exists using the s3_client
                    try:
                        s3_client.head_object(
                            Bucket=S3_DATAPROC_BUCKET, Key=full_s3_key
                        )
                        context.log.info(f"{s3_key} exists in {S3_DATAPROC_BUCKET}.")
                    except botocore.exceptions.ClientError as e:
                        # doesn't exist in new/, check if already ingested
                        base_pdf_name = pdf_name.split(".")[0]
                        runs = context.instance.get_runs(
                            filters=RunsFilter(
                                tags={"dagster/partition": base_pdf_name},
                                statuses=[
                                    DagsterRunStatus.STARTED,
                                    DagsterRunStatus.STARTING,
                                    DagsterRunStatus.QUEUED,
                                    DagsterRunStatus.SUCCESS,
                                    DagsterRunStatus.FAILURE,
                                ],
                            )
                        )
                        has_run = any(runs)
                        if not has_run:
                            # new PDF: create new partition and upload to S3
                            pdf_response = requests.get(pdf_url)
                            pdf_response.raise_for_status()  # Raise an exception for HTTP errors

                            # Upload the PDF to S3
                            s3_client.put_object(
                                Bucket=S3_DATAPROC_BUCKET,
                                Key=full_s3_key,
                                Body=pdf_response.content,
                            )
                            destination_path = (
                                f"s3://{S3_DATAPROC_BUCKET}/{full_s3_key}"
                            )
                            context.log.info(
                                f"Uploaded {pdf_name} to {destination_path}"
                            )
                            new_pdfs.append((pdf_name, s3_key, destination_path))
                        else:
                            context.log.info(
                                f"{base_pdf_name} run found, already ingested"
                            )

    if len(new_pdfs) > 0:
        context.log.info(f"New PDFs: {new_pdfs}")
        _generate_new_hansard_message(new_pdfs, skipped_pdfs, context)

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


@asset(group_name="scrape")
def move_and_rename_all_hansards(
    context: AssetExecutionContext, scrape_website: List[Tuple[str, str, str]]
):
    """Move and rename all hansards from new/ to main downloads folder"""
    # New PDFs: [('DN-24032025.pdf', 'dewannegara/DN-24032025.pdf', 's3://hansards-dataproc-kd/new/dewannegara/DN-24032025.pdf')]
    for new_pdf, s3_key, destination_path in scrape_website:
        context.log.info(f"Moving and renaming {s3_key}")

        sitting_object = get_sitting_object(new_pdf[:-4])

        # Read from S3
        pdf_response = s3_client.get_object(
            Bucket=S3_DATAPROC_BUCKET,
            Key=f"new/{sitting_object['house_folder']}/{sitting_object['original_filename']}",
        )
        new_pdf_name = (
            f"{sitting_object['house_folder']}/{sitting_object['renamed_filename']}.pdf"
        )

        # Rename and move the file
        s3_client.put_object(
            Bucket=S3_PUBLIC_BUCKET,
            Key=new_pdf_name,
            Body=pdf_response["Body"].read(),
            ContentType="application/pdf",
        )

        context.log.info(f"Renamed and moved {s3_key} to {new_pdf_name}")


@asset(
    partitions_def=sitting_partitions_def,
    # deps=[move_and_rename_hansards],
    group_name="parse",
)
def dg_parse_hansard(context: AssetExecutionContext):
    """Parse hansard
    Output of this is parsed_pdf folder - plaintext, bold, italics, tables, attendance.txt
    """
    sitting_object = get_sitting_object(context.partition_key)
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
    s3_key = build_path("parsed_pdf", "plaintext.txt", sitting_object)
    s3_client.put_object(Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=text)
    context.log.info(f"Uploaded plaintext to {s3_key}")
    s3_key = build_path("parsed_pdf", "bold.txt", sitting_object)
    s3_client.put_object(Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=spaced_bold)
    context.log.info(f"Uploaded bold to {s3_key}")
    s3_key = build_path("parsed_pdf", "italics.txt", sitting_object)
    s3_client.put_object(Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=spaced_italics)
    context.log.info(f"Uploaded italics to {s3_key}")
    # save tables even if empty
    s3_key = build_path("parsed_pdf", "tables.json", sitting_object)
    s3_client.put_object(Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=json.dumps(tables))
    context.log.info(f"Uploaded tables to {s3_key}")
    if attn_text != "":
        s3_key = build_path("parsed_pdf", "attendance.txt", sitting_object)
        s3_client.put_object(Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=attn_text)
        context.log.info(f"Uploaded attendance to {s3_key}")


@asset(
    partitions_def=sitting_partitions_def, deps=[dg_parse_hansard], group_name="parse"
)
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
    sitting_object = get_sitting_object(context.partition_key)
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

    s3_key = build_path("get_categories", "categories.json", sitting_object)
    s3_client.put_object(
        Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=prepare_json_for_s3(categories)
    )
    context.log.info(f"Uploaded categories to {s3_key}")

    s3_key = build_path("get_categories", "toc_analysis/plaintext.txt", sitting_object)
    s3_client.put_object(Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=text)
    context.log.info(f"Uploaded plaintext to {s3_key}")
    s3_key = build_path("get_categories", "toc_analysis/bold.txt", sitting_object)
    s3_client.put_object(Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=spaced_bold)
    context.log.info(f"Uploaded bold to {s3_key}")
    s3_key = build_path("get_categories", "toc_analysis/italics.txt", sitting_object)
    s3_client.put_object(Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=spaced_italics)
    context.log.info(f"Uploaded italics to {s3_key}")


@asset(
    partitions_def=sitting_partitions_def, deps=[dg_get_categories], group_name="parse"
)
def dg_post_parsing_edits(context: AssetExecutionContext):
    """
    Hardcoded edits to parsed text files.
    """
    sitting_object = get_sitting_object(context.partition_key)
    # get tables.json and categories.json
    tables_s3_key = build_path("parsed_pdf", "tables.json", sitting_object)
    try:
        tables = read_json_file(s3_client, S3_DATAPROC_BUCKET, tables_s3_key)
    except botocore.exceptions.ClientError as e:
        context.log.warning(f"No tables.json found for {context.partition_key}")
        tables = None

    categories_s3_key = build_path("get_categories", "categories.json", sitting_object)

    try:
        categories = read_json_file(s3_client, S3_DATAPROC_BUCKET, categories_s3_key)
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
            Body=prepare_json_for_s3(tables),
        )
        context.log.info(f"Uploaded tables to {tables_s3_key}")
    else:
        context.log.warning(f"No post parsing edits found for {context.partition_key}")
    if categories:
        s3_client.put_object(
            Bucket=S3_DATAPROC_BUCKET,
            Key=categories_s3_key,
            Body=prepare_json_for_s3(categories),
        )
        context.log.info(f"Uploaded categories to {categories_s3_key}")
    else:
        context.log.warning(f"No TOC edits found for {context.partition_key}")


@asset(
    partitions_def=sitting_partitions_def,
    deps=[dg_post_parsing_edits],
    group_name="parse",
)
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
    sitting_object = get_sitting_object(context.partition_key)
    context.log.info(f"Pre tabulating {context.partition_key}")

    plaintext = read_txt_file(
        s3_client,
        S3_DATAPROC_BUCKET,
        build_path("parsed_pdf", "plaintext.txt", sitting_object),
    )
    bold = read_txt_file(
        s3_client,
        S3_DATAPROC_BUCKET,
        build_path("parsed_pdf", "bold.txt", sitting_object),
    )
    italics = read_txt_file(
        s3_client,
        S3_DATAPROC_BUCKET,
        build_path("parsed_pdf", "italics.txt", sitting_object),
    )
    tables = read_json_file(
        s3_client,
        S3_DATAPROC_BUCKET,
        build_path("parsed_pdf", "tables.json", sitting_object),
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

    s3_key = build_path("pretabulation", "plaintext.txt", sitting_object)
    s3_client.put_object(
        Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=prepare_text_for_s3(processed_text)
    )
    context.log.info(f"Uploaded plaintext to {s3_key}")
    s3_key = build_path("pretabulation", "bold.txt", sitting_object)
    s3_client.put_object(
        Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=prepare_text_for_s3(processed_bold)
    )
    context.log.info(f"Uploaded bold to {s3_key}")
    s3_key = build_path("pretabulation", "italics.txt", sitting_object)
    s3_client.put_object(
        Bucket=S3_DATAPROC_BUCKET,
        Key=s3_key,
        Body=prepare_text_for_s3(processed_italics),
    )
    context.log.info(f"Uploaded italics to {s3_key}")


@asset(
    partitions_def=sitting_partitions_def, deps=[dg_pre_tabulate], group_name="parse"
)
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
    sitting_object = get_sitting_object(context.partition_key)
    context.log.info(f"Editing hansards for {context.partition_key}")

    plaintext = read_txt_file(
        s3_client,
        S3_DATAPROC_BUCKET,
        build_path("pretabulation", "plaintext.txt", sitting_object),
    )
    bold = read_txt_file(
        s3_client,
        S3_DATAPROC_BUCKET,
        build_path("pretabulation", "bold.txt", sitting_object),
    )
    italics = read_txt_file(
        s3_client,
        S3_DATAPROC_BUCKET,
        build_path("pretabulation", "italics.txt", sitting_object),
    )

    text, bold, italics, num_edits = edit_hansards(
        sitting_object["house"],
        sitting_object["date_str"],
        plaintext,
        bold,
        italics,
        is_pipeline=True,
    )

    s3_key = build_path("pretabulation", "plaintext.txt", sitting_object)
    s3_client.put_object(
        Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=prepare_text_for_s3(text)
    )
    context.log.info(f"Uploaded plaintext to {s3_key}")
    s3_key = build_path("pretabulation", "bold.txt", sitting_object)
    s3_client.put_object(
        Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=prepare_text_for_s3(bold)
    )
    context.log.info(f"Uploaded bold to {s3_key}")
    s3_key = build_path("pretabulation", "italics.txt", sitting_object)
    s3_client.put_object(
        Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=prepare_text_for_s3(italics)
    )
    context.log.info(f"Uploaded italics to {s3_key}")


@asset(
    partitions_def=sitting_partitions_def, deps=[dg_edit_hansards], group_name="parse"
)
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

    sitting_object = get_sitting_object(context.partition_key)
    context.log.info(f"Tabulating {context.partition_key}")

    # get files from s3
    plaintext = read_txt_file(
        s3_client,
        S3_DATAPROC_BUCKET,
        build_path("pretabulation", "plaintext.txt", sitting_object),
    )
    bold = read_txt_file(
        s3_client,
        S3_DATAPROC_BUCKET,
        build_path("pretabulation", "bold.txt", sitting_object),
    )
    italics = read_txt_file(
        s3_client,
        S3_DATAPROC_BUCKET,
        build_path("pretabulation", "italics.txt", sitting_object),
    )
    print(f"length of plaintext: {len(plaintext)}")
    print(f"length of bold: {len(bold)}")
    print(f"length of italics: {len(italics)}")

    # read categories.json from root folder
    categories = read_json_file(s3_client, S3_DATAPROC_BUCKET, "categories.json")

    if sitting_object["house"] != "DN":
        categories = json.loads(
            read_json_file(
                s3_client,
                S3_DATAPROC_BUCKET,
                build_path("get_categories", "categories.json", sitting_object),
            )
        )

    print(type(categories))

    try:
        attendance = read_txt_file(
            s3_client,
            S3_DATAPROC_BUCKET,
            build_path("parsed_pdf", "attendance.txt", sitting_object),
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
        is_pipeline=True,
    )

    s3_key = build_path("tabulated", "result.csv", sitting_object)
    s3_client.put_object(
        Bucket=S3_DATAPROC_BUCKET, Key=s3_key, Body=prepare_csv_for_s3(speeches)
    )
    context.log.info(f"Uploaded result.csv to {s3_key}")
    s3_csv_key = (
        f"{sitting_object['house_folder']}/{sitting_object['renamed_filename']}.csv"
    )
    s3_client.put_object(
        Bucket=S3_PUBLIC_BUCKET,
        Key=s3_csv_key,
        Body=prepare_csv_for_s3(speeches),
    )
    context.log.info(f"Uploaded copy of result.csv to {s3_csv_key}")

    if absent_text:
        s3_key = build_path("tabulated", "absent.txt", sitting_object)
        s3_client.put_object(
            Bucket=S3_DATAPROC_BUCKET,
            Key=s3_key,
            Body=prepare_text_for_s3(absent_text),
        )
        context.log.info(f"Uploaded absent.txt to {s3_key}")

    if attended_text:
        s3_key = build_path("tabulated", "attended.txt", sitting_object)
        s3_client.put_object(
            Bucket=S3_DATAPROC_BUCKET,
            Key=s3_key,
            Body=prepare_text_for_s3(attended_text),
        )
        context.log.info(f"Uploaded attended.txt to {s3_key}")


@asset(partitions_def=sitting_partitions_def, deps=[dg_tabulate], group_name="parse")
def remove_parsed_hansards(context: AssetExecutionContext):
    """
    Remove Hansards from /new after parsing
    Only removes pdf if result.csv is in /tabulated and if file is moved into new folder
    """
    sitting_object = get_sitting_object(context.partition_key)
    path_parts = [
        "new",
        sitting_object["house_folder"],
        sitting_object["original_filename"],
    ]  # new/dewanrakyat/DN-02122024.pdf
    new_pdf_s3_key = "/".join(path_parts)
    parsed_pdf_result_key = build_path(
        f"tabulated", "result.csv", sitting_object
    )  # tabulated/dewanrakyat/02122024/result.csv

    # new_pdf_s3_key = f"new/{house_folder}/{sitting_object['original_filename']}"  # new/dewanrakyat/DN-02122024.pdf
    # moved_pdf_key = f"{house_folder}/{sitting_object['renamed_filename']}"
    # parsed_pdf_result_key = f"tabulated/{house_folder}/{date}/result.csv"  # tabulated/dewanrakyat/02122024/result.csv

    # Check if result.csv is in /tabulated/dewanrakyat/02122024
    try:
        s3_client.head_object(Bucket=S3_DATAPROC_BUCKET, Key=parsed_pdf_result_key)
        context.log.info(f"{parsed_pdf_result_key} Verified!")
    except botocore.exceptions.ClientError:
        context.log.error(f"result.csv is not in {parsed_pdf_result_key}")
        raise botocore.exceptions.ClientError

    # Check if pdf file was moved
    try:
        s3_client.head_object(
            Bucket=S3_PUBLIC_BUCKET, Key=sitting_object["renamed_filename_key"]
        )
        context.log.info(f"{sitting_object['renamed_filename_key']}  Verified!")
    except botocore.exceptions.ClientError:
        context.log.error(f"{sitting_object['renamed_filename_key']} not Verfied")
        raise botocore.exceptions.ClientError

    # Remove file from new/ S3 bucket
    try:
        # First check if the object exists
        s3_client.head_object(Bucket=S3_DATAPROC_BUCKET, Key=new_pdf_s3_key)

        # If head_object doesn't raise an exception, the object exists and we can delete it
        try:
            s3_client.delete_object(Bucket=S3_DATAPROC_BUCKET, Key=new_pdf_s3_key)
            context.log.info(f"Removed {new_pdf_s3_key} from s3")
        except botocore.exceptions.ClientError as e:
            context.log.error(f"Error removing {new_pdf_s3_key} from s3: {str(e)}")
            raise e

    except botocore.exceptions.ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "404" or error_code == "NoSuchKey":
            context.log.warning(
                f"Object {new_pdf_s3_key} does not exist in S3, nothing to remove"
            )
        else:
            context.log.error(f"Error checking if {new_pdf_s3_key} exists: {str(e)}")
        raise e


@asset(partitions_def=sitting_partitions_def, deps=[dg_tabulate], group_name="parse")
def prepare_db_payload(context: AssetExecutionContext):
    """
    Prepare payload for DB Insertion
    - Pre-requisite: ParliamentaryCycle record exists
    - Create Sitting with speech_data - POST to /sitting - save Sitting and Speech records
    - Match AuthorHistory records if needed - GET to /author_history
    """
    sitting_object = get_sitting_object(context.partition_key)
    context.log.info(f"sitting_object: {sitting_object}")

    context.log.info(f"Start processing tabulated data")
    csv_path = build_path("tabulated", "result.csv", sitting_object)
    csv_data = s3_client.get_object(Bucket=S3_DATAPROC_BUCKET, Key=csv_path)
    df = pd.read_csv(io.BytesIO(csv_data["Body"].read()))
    df["date"] = sitting_object["proper_date_str"]
    df = process_tabulated(df, sitting_object["house"])

    speeches_count = len(df)
    context.log.info(f"Preprocessing speech tokens: {speeches_count} speeches")
    df["speech_tokens"] = df.proc_speech.apply(lambda text: preprocess_malaya(text))

    # df_speech = df[df.author != "ANNOTATION"]
    df_speech = df.dropna(subset="speech")
    df_speech.length = df_speech.length.astype(int)
    df_speech.reset_index(names="index", inplace=True)

    df_speech = df_speech[
        df_speech.speech_tokens.str.len() > 0
    ]  # remove cleaned til empty speeches

    # context.log.info(f"Converting speech tokens to PostgreSQL array string")
    # df_speech.speech_tokens = df_speech.speech_tokens.apply(
    #     lambda token_list: _to_postgresql_array_string(token_list)
    # )

    context.log.info(f"Start author matching")
    response = requests.get(f"{DEV_API_URL}/api/author-history")
    response.raise_for_status()
    author_history = response.json()
    df_author_history = pd.DataFrame(author_history)
    df_author_history["area"] = df_author_history.area_name.str[5:]
    context.log.info(f"Author history: {len(df_author_history)} records")

    context.log.info("Get Authors")
    response = requests.get(f"{DEV_API_URL}/api/author")
    response.raise_for_status()
    author = response.json()
    df_author = pd.DataFrame(author)
    context.log.info(f"Author: {len(df_author)} records")
    df_speech_matched = perform_author_matching(
        df_speech, df_author, df_author_history, context
    )
    matched_speeches_rate = (~df_speech_matched["author_id"].isna()).mean() * 100

    # rename to backend model names
    df_speech_matched = df_speech_matched.rename(
        columns={"author_id": "speaker", "date": "sitting"}
    )
    # change sitting to date string
    df_speech_matched["sitting"] = df_speech_matched["sitting"].apply(
        lambda date: date.strftime("%Y-%m-%d")
    )
    context.log.info(df_speech_matched.columns.tolist())
    # data completeness checking by column
    assert df_speech_matched["timestamp"].notna().all(), "timestamp column has NaN"
    assert df_speech_matched["index"].notna().all(), "index column has NaN"
    assert df_speech_matched["speech"].notna().all(), "speech column has NaN"
    # note: this speech_data is only as payload to backend ingestion, not the final JSON
    # speech_data = speeches_to_json(df_speech_matched)
    speech_data = df_speech_matched.to_dict(orient="records")

    # show row and column with NaN - speaker column NaN
    context.log.info(speech_data[0])

    sitting_payload = {
        "date": sitting_object["proper_date_str"],
        "filename": sitting_object["renamed_filename"],
        # "has_dataset": True,
        # "is_final": True, # TODO: determine this
        "speech_data": json.dumps(speech_data),
        "house": house_mapper.code_to_display(sitting_object["house"]),
    }

    # # TEMP: save sitting_payload to pickle
    # with open("sitting_payload.pkl", "wb") as f:
    #     pickle.dump(sitting_payload, f)

    context.log.info(f"context.run.tags: {context.run.tags}")
    return Output(
        sitting_payload,
        metadata={
            "speeches_count": speeches_count,
            "matched_speeches_rate": float(matched_speeches_rate),
            # "revalidate_frontend": "dagster/backfill" not in context.run.tags,
        },
    )


def _insert_to_db(api_url: str, payload: dict, context: AssetExecutionContext):
    """
    Insert Hansards to DB
    """
    # Post to Dev Sittings API
    response = requests.post(f"{api_url}/api/sitting/", json=payload, timeout=3600)
    # Check if request was successful
    try:
        response.raise_for_status()
        context.log.info(f"Successfully uploaded sitting data: {response}")
    except requests.exceptions.HTTPError as e:
        context.log.error(f"API request failed: {e}")
        context.log.error(f"Response content: {response.text}")
        # Re-raise the exception to trigger pipeline failure
        raise

    try:
        response_data = response.json()
    except json.JSONDecodeError:
        context.log.error(f"Failed to parse response as JSON: {response.text}")
        raise

    if response.status_code == 201 and "warning" in response_data:
        warning_message = f"Data integrity warning: {response_data['warning']}"
        context.log.warning(warning_message)
        raise Exception(warning_message)
    elif response.status_code == 201 and "speech_errors" in response_data:
        speech_errors = response_data["speech_errors"]
        context.log.warning(f"Speech errors: {speech_errors}")
        raise Exception(speech_errors)


@asset(
    partitions_def=sitting_partitions_def, deps=[prepare_db_payload], group_name="parse"
)
def insert_to_dev_db(context: AssetExecutionContext, prepare_db_payload: dict):
    """
    Insert Hansards to Dev DB
    """
    _insert_to_db(DEV_API_URL, prepare_db_payload, context)


@asset(
    partitions_def=sitting_partitions_def, deps=[prepare_db_payload], group_name="parse"
)
def insert_to_prod_db(context: AssetExecutionContext, prepare_db_payload: dict):
    """
    Insert Hansards to Prod DB
    """
    _insert_to_db(PROD_API_URL, prepare_db_payload, context)


# @asset(group_name="frontend")
# def revalidate_frontend(context: AssetExecutionContext, config: dict):
#     """
#     Revalidate frontend
#     """
#     if "partition" not in config:
#         context.log.info(
#             f"No partition provided, skipping revalidation. Config: {config}"
#         )
#         raise ValueError("No partition provided")

#     partition_key = config["partition"]
#     sitting_object = get_sitting_object(partition_key)
#     house_route = f"/katalog/{sitting_object['house_display']}"
#     hansard_route = f"/hansard/{sitting_object['house_display']}/{sitting_object['proper_date_str']}"
#     payload = {"route": f"{house_route},{hansard_route}"}

#     context.log.info(f"Revalidating frontend: {payload}")
#     try:
#         response = requests.post(
#             f"{FRONTEND_URL}/api/revalidate",
#             headers={"Authorization": f"Bearer {FRONTEND_TOKEN}"},
#             json=payload,
#         )
#         response.raise_for_status()
#         context.log.info(f"Successfully revalidated frontend: {response}")
#     except requests.exceptions.HTTPError as e:
# context.log.error(f"Failed to revalidate frontend: {e}")
# raise

# return MaterializeResult(
#     metadata={
#         "hansard_route": hansard_route,
#     }
# )


sittings_job = define_asset_job(
    "sittings_job",
    selection=[
        dg_parse_hansard,
        dg_get_categories,
        dg_post_parsing_edits,
        dg_pre_tabulate,
        dg_edit_hansards,
        dg_tabulate,
        remove_parsed_hansards,
        prepare_db_payload,
        insert_to_dev_db,
        insert_to_prod_db,
    ],
)
