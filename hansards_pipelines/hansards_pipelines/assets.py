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
    Failure
)
import os
import io
import json
import pickle
from bs4 import BeautifulSoup
import boto3
import botocore
import re
import requests
import pandas as pd
from urllib.parse import urljoin
from typing import List, Tuple, Dict, Optional
from io import BytesIO
import pdfplumber
from datetime import datetime
import math

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

from hansards_pipelines.settings import S3_DATAPROC_BUCKET, S3_PUBLIC_BUCKET, DEV_API_URL, PROD_API_URL, FRONTEND_URL, FRONTEND_TOKEN, HANSARD_DB_URL, AWS_REGION, ARKIB_PARTITION_MIN_YEAR, ARKIB_PARTITION_MAX_YEAR, READY_QUEUE_KEY, PENDING_QUEUE_KEY
from hansards_pipelines.scrape_parliamentary_cycle import (
    scrape_arkib_cycles,
    scrape_active_cycles,
    fetch_db_cycles,
    upsert_cycles_via_api,
)
import psycopg
from hansards_pipelines.direct_sitting_ingest import ingest_sitting_to_db

from hansards_pipelines.scrape_arkib import run_scrape
from hansards_pipelines.move_and_rename_pdf import move_arkib_pdfs_to_public_main
from hansards_pipelines.author import load_author_csv_to_db
from pathlib import Path

from hansards_pipelines.arkib.build_arkib_partition_queue import build_arkib_partition_queue
from hansards_pipelines.arkib.promote_pdfs import promote_arkib_pdfs

from hansards_pipelines.legacy_pipeline.main import process_legacy_pipeline

# main pipeline
# 1. scrape from the website, push pdf to s3 hansards-new
# 2. move and rename hansards-new to main raw hansards folder
# 3. run parse_hansard (in: raw PDF, out: parsed_pdf folder - plaintext, bold, italics, tables, attendance.txt, is_final.txt)
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
sitting_legacy_partitions_def = DynamicPartitionsDefinition(name="house_sittings_legacy")
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
    try:
        send_discord_message(
            "",
            f"✨ New Hansards Scraped!",
            3066993,
            message_fields,
            footer,
            context,
            deeplink=False,
        )
    except Exception as e:
        context.log.warning(f"Discord notification failed (ignored): {e}")



@asset(group_name="scrape")
def scrape_parliamentary_cycle_arkib(context: AssetExecutionContext) -> Dict:
    """
    Scrape parliamentary cycle data (Parlimen, Penggal, Mesyuarat + date ranges)
    from Portal Rasmi Parlimen archive for DR, DN, KKDR and upsert via
    POST /api/parliamentary-cycle.
    
    This scrapes COMPLETED sessions from the archive tree structure.
    """
    # Scrape cycles from arkib
    cycles = scrape_arkib_cycles(context=context)
    
    # Fetch existing cycles from database
    context.log.info("[arkib] Fetching existing cycles from database...")
    existing_keys = fetch_db_cycles(HANSARD_DB_URL, context)
    
    # Upsert via API
    api_endpoint = f"{DEV_API_URL}/api/parliamentary-cycle"
    context.log.info(f"[arkib] Using API endpoint: {api_endpoint}")
    
    stats = upsert_cycles_via_api(
        cycles=cycles,
        existing_keys=existing_keys,
        api_endpoint=api_endpoint,
        log_prefix="arkib",
        context=context
    )
    
    summary = {
        "total_scraped": len(cycles),
        **stats,
    }
    
    context.log.info(f"[arkib] Summary: {summary}")
    return summary


@asset(group_name="scrape")
def scrape_parliamentary_cycle_active(context: AssetExecutionContext) -> Dict:
    """
    Scrape ACTIVE parliamentary cycle data (Parlimen, Penggal, Mesyuarat + date ranges)
    from Portal Rasmi Parlimen main pages for DR, DN, KKDR.
    """
    # Scrape active cycles
    cycles = scrape_active_cycles(context=context)
    
    # Fetch existing cycles from database
    context.log.info("[active] Fetching existing cycles from database...")
    existing_keys = fetch_db_cycles(HANSARD_DB_URL, context)
    
    # Upsert via API
    api_endpoint = f"{DEV_API_URL}/api/parliamentary-cycle"
    context.log.info(f"[active] Using API endpoint: {api_endpoint}")
    
    stats = upsert_cycles_via_api(
        cycles=cycles,
        existing_keys=existing_keys,
        api_endpoint=api_endpoint,
        log_prefix="active",
        context=context
    )
    
    summary = {
        "total_scraped": len(cycles),
        **stats,
    }
    
    context.log.info(f"[active] Summary: {summary}")
    return summary


@asset(group_name="scrape")
def scrape_website(context: AssetExecutionContext) -> List:
    """Scrape list of PDFs and add new partition if doesn't exist
    Upload PDF file to S3"""

    # sqs = boto3.client("sqs")
    # queue_url = "https://sqs.ap-southeast-1.amazonaws.com/761623003862/NewHansardsQueue"

    base_url = "https://www.parlimen.gov.my"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    # Configure requests session with SSL settings
    session = requests.Session()
    session.headers.update(headers)

    # Try with verification first, fallback to no verification if needed
    verify_ssl = True

    sources = [
        (
            "https://www.parlimen.gov.my/hansard-dewan-rakyat.html?&uweb=dr&lang=bm",
            "dewanrakyat",
        ),
        (
            "https://www.parlimen.gov.my/hansard-dewan-negara.html?&uweb=dn&lang=bm",
            "dewannegara",
        ),
        (
            "https://www.parlimen.gov.my/hansard-dewan-khas.html?uweb=dr",
            "kamarkhas",
        ),
    ]
    new_pdfs = []
    skipped_pdfs = []
    for source in sources:

        source_url = source[0]
        house_folder = source[1]
        # Send a request to the base URL with SSL handling
        try:
            response = session.get(source_url, verify=verify_ssl, timeout=300)
            response.raise_for_status()  # Raise an exception for HTTP errors
        except requests.exceptions.SSLError as ssl_error:
            context.log.warning(
                f"SSL verification failed for {source_url}, retrying without verification: {ssl_error}"
            )
            # Fallback to no SSL verification
            response = session.get(source_url, verify=False, timeout=30)
            response.raise_for_status()  # Raise an exception for HTTP errors
            verify_ssl = False  # Update for subsequent requests

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
                    should_upload = False
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

                    # Step 1: Check if file exists in S3 new/
                    exists_in_s3 = False
                    try:
                        s3_client.head_object(Bucket=S3_DATAPROC_BUCKET, Key=full_s3_key)
                        exists_in_s3 = True
                        context.log.info(f"{s3_key} exists in {S3_DATAPROC_BUCKET}.")
                    except botocore.exceptions.ClientError as e:
                        if e.response["Error"]["Code"] == "404":
                            context.log.info(f"S3 object not found: {full_s3_key}")
                        else:
                            raise
                        
                    # Step 1b: Check if file already exists in PUBLIC (canonical location)
                    exists_in_public = False
                    sitting_object = get_sitting_object(pdf_name[:-4])
                    public_house_folder = sitting_object["house_folder"]
                    renamed_public_key = f"{public_house_folder}/{sitting_object['renamed_filename']}.pdf"
                    try:
                        s3_client.head_object(
                            Bucket=S3_PUBLIC_BUCKET,
                            Key=renamed_public_key,
                        )
                        exists_in_public = True
                    except botocore.exceptions.ClientError:
                        pass


                    if exists_in_s3 and not exists_in_public:
                        # Stranded file: uploaded before but never moved to PUBLIC
                        context.log.warning(f"{pdf_name} exists in new/ but not in PUBLIC. No need to upload again, but re-queueing for move")
                        should_upload = False
                        new_pdfs.append((pdf_name, s3_key, f"s3://{S3_DATAPROC_BUCKET}/{full_s3_key}"))
                    elif exists_in_s3 and exists_in_public:
                        should_upload = False
                    else:
                        # Step 2: Download and open PDF to determine is_final_pdf flag
                        pdf_response = requests.get(pdf_url, verify=False, timeout=300)
                        pdf_response.raise_for_status()
                        is_final_pdf = True
                        with pdfplumber.open(BytesIO(pdf_response.content)) as pdf:
                            for page in pdf.pages:
                                text = page.extract_text().lower()
                                if text and ("naskhah belum disemak" in text or "naskhah belum semak" in text):
                                    context.log.info(f"{pdf_name} - Naskhah belum disemak: {page}")
                                    is_final_pdf = False
                                    break

                        # Step 3: Check if Dagster has already run
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

                        # Step 4: Check DB is_final for this sitting 
                        is_final_db = False                  
                        try:
                            proper_date = f"{date[4:]}-{date[2:4]}-{date[:2]}"  # DDMMYYYY -> YYYY-MM-DD
                            house_sitting  = house_mapper.code_to_display(house.lower())
                            api_url = f"{DEV_API_URL}/api/sitting/?house={house_sitting}&date={proper_date}"
                            db_response = requests.get(api_url, timeout=15)
                            if db_response.ok:               
                                is_final_db = db_response.json().get("meta", {}).get("is_final", False)
                            else:
                                context.log.warning(f"API returned non-200 for {pdf_name}: {db_response.status_code} - {db_response.text}")
                        except Exception as db_err:
                            context.log.warning(f"DB check failed for {pdf_name}: {db_err}")

                        # Step 5: Decide to upload or skip
                        match (is_final_pdf, is_final_db, has_run):
                            case (False, False, False):
                                context.log.info(f"Upload {pdf_name} - Entirely new hansard")
                                should_upload = True
                            case (False, False, True):
                                context.log.info(f"Skip {pdf_name} - Not final, completed ingestion (was not final)")
                                should_upload = False
                            case (False, True, True):
                                context.log.info(f"Skip {pdf_name} - Not final, completed ingestion (was final) - shouldn't happen")
                                should_upload = False
                            case (True, False, True):
                                context.log.info(f"Upload {pdf_name} - Final PDF, completed ingestion (was previously draft)")
                                should_upload = True
                            case (True, True, True):
                                context.log.info(f"Skip {pdf_name} - Final PDF, completed ingestion (final) (unchanged)")
                                should_upload = False
                            case (True, False, False):
                                context.log.info(f"Upload {pdf_name} - Final PDF, not in DB yet, no runs yet - Entirely new hansard & final")
                                should_upload = True
                            case _:
                                context.log.info(f"Skip {pdf_name} - Fallback unknown case combination by default")
                                should_upload = False

                            #  exists_in_s3 | is_final_pdf | is_final_db | has_run | action   | desc
                            #       /                -            -           -      skip     | Hasn't completed ingestion
                            #       X                X            X           X      upload   | Entirely new hansard
                            #       X                X            X           /      skip     | Not final, completed ingestion (was not final)
                            #       X                X            /           /      skip     | Not final, completed ingestion (was final) - shouldn't happen
                            #       X                /            X           /      upload   | Final PDF, completed ingestion (was not final)
                            #       X                /            /           /      skip     | Final PDF, completed ingestion (was final)
                                
                        if should_upload:
                            # Upload the PDF to S3
                            s3_client.put_object(
                                Bucket=S3_DATAPROC_BUCKET,
                                Key=full_s3_key,
                                Body=pdf_response.content,
                            )
                            destination_path = (f"s3://{S3_DATAPROC_BUCKET}/{full_s3_key}")
                            new_pdfs.append((pdf_name, s3_key, destination_path))
                            context.log.info(f"Uploaded {pdf_name} to {destination_path} | exists_in_s3={exists_in_s3}, is_final_pdf={is_final_pdf}, is_final_db={is_final_db}, has_run={has_run}")
                        else:
                            context.log.info(f"Skipped {pdf_name} | exists_in_s3={exists_in_s3}, is_final_pdf={is_final_pdf}, is_final_db={is_final_db}, has_run={has_run}")

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

        # Read from S3 using the actual key that was uploaded
        pdf_response = s3_client.get_object(
            Bucket=S3_DATAPROC_BUCKET,
            Key=f"new/{s3_key}",
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

def _dg_parse_hansard_impl(
    *,
    context: AssetExecutionContext,
    pdf_key: str,
):
    """Parse hansard
    Output of this is parsed_pdf folder - plaintext, bold, italics, tables, attendance.txt
    """
    # only if sittings_job is triggered by sensor trigger_sittings_job_arkib_sensor, delete the READY_QUEUE_KEY
    if context.run.tags.get("pdf_source") == "arkib":

        try:
            s3_client.delete_object(
                Bucket=S3_DATAPROC_BUCKET,
                Key=READY_QUEUE_KEY,
            )
            context.log.info(f"Deleted READY_QUEUE_KEY: {READY_QUEUE_KEY}")
        except Exception as e:
            context.log.warning(f"Failed to delete READY_QUEUE_KEY: {e}")

    sitting_object = get_sitting_object(context.partition_key)
    context.log.info(f"Parsing {sitting_object['original_filename']}")

    # read pdf from s3
    try:
        pdf_response = s3_client.get_object(
            Bucket=S3_PUBLIC_BUCKET,
            Key=pdf_key,
        )
    except botocore.exceptions.ClientError as e:
        context.log.error(f"PDF not found in {S3_PUBLIC_BUCKET} for {context.partition_key}. Likely move & rename step did not run.")
        raise

    text, spaced_bold, spaced_italics, tables, attn_text, is_final = parse_hansard(
        sitting_object["date_str"],
        sitting_object["house"],
        "DEFAULT_DATA_DIR",
        file_content=BytesIO(pdf_response["Body"].read()),
    )
    # save to s3
    s3_key = build_path("parsed_pdf", "is_final.txt", sitting_object)
    s3_client.put_object(Bucket=S3_DATAPROC_BUCKET,Key=s3_key, Body=f"{is_final}\n")
    context.log.info(f"Uploaded is_final.txt to {s3_key}")
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
    partitions_def=sitting_partitions_def,
    group_name="parse",
)
def dg_parse_hansard(context: AssetExecutionContext):
    """
    Parse hansard PDF for a sitting. Always reads from S3 PUBLIC ROOT.
    """

    sitting_object = get_sitting_object(context.partition_key)

    pdf_key = sitting_object["renamed_filename_key"]

    context.log.info(f"dg_parse_hansard | partition={context.partition_key} | key={pdf_key}")

    _dg_parse_hansard_impl(context=context, pdf_key=pdf_key)

    return {
        "partition": context.partition_key,
        "pdf_key": pdf_key,
    }


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

    pdf_key = sitting_object["renamed_filename_key"]

    context.log.info(f"Getting categories | key={pdf_key}")

    pdf_response = s3_client.get_object(
        Bucket=S3_PUBLIC_BUCKET, Key=pdf_key
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
    except botocore.exceptions.ClientError as e:
        context.log.error(f"result.csv is not in {parsed_pdf_result_key}")
        raise e

    # Check if pdf file was moved
    try:
        s3_client.head_object(
            Bucket=S3_PUBLIC_BUCKET, Key=sitting_object["renamed_filename_key"]
        )
        context.log.info(f"{sitting_object['renamed_filename_key']}  Verified!")
    except botocore.exceptions.ClientError as e:
        context.log.error(f"{sitting_object['renamed_filename_key']} not Verified")
        raise e

    # Remove file from new/ S3 bucket
    file_removed = False
    try:
        # First check if the object exists
        s3_client.head_object(Bucket=S3_DATAPROC_BUCKET, Key=new_pdf_s3_key)

        # If head_object doesn't raise an exception, the object exists and we can delete it
        try:
            s3_client.delete_object(Bucket=S3_DATAPROC_BUCKET, Key=new_pdf_s3_key)
            context.log.info(f"Removed {new_pdf_s3_key} from s3")
            file_removed = True
        except botocore.exceptions.ClientError as e:
            context.log.error(f"Error removing {new_pdf_s3_key} from s3: {str(e)}")
            raise e

    except botocore.exceptions.ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "404" or error_code == "NoSuchKey":
            context.log.warning(
                f"Object {new_pdf_s3_key} does not exist in S3, nothing to remove"
            )
            # This is OK - file was already removed or never existed
        else:
            context.log.error(f"Error checking if {new_pdf_s3_key} exists: {str(e)}")
            raise e
    
    return {"file_removed": file_removed, "s3_key": new_pdf_s3_key}


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

    try:
        s3_key = build_path("parsed_pdf", "is_final.txt", sitting_object)
        is_final_obj = s3_client.get_object(Bucket=S3_DATAPROC_BUCKET, Key=s3_key)
        is_final_content = is_final_obj["Body"].read().decode("utf-8").strip().lower()
        is_final = is_final_content == "true"
        context.log.info(f"'is_final': {is_final}")
    except Exception as e:
        context.log.warning(f"Could not load is_final.txt: {e}")
        is_final = False
        
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

    context.log.info(
    f"Sitting parsed: date={sitting_object['proper_date_str']}, "
    f"filename={sitting_object['renamed_filename']}, "
    f"is_final={is_final}, "
    f"house={house_mapper.code_to_display(sitting_object['house'])}")

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
    speech_data = [{k: (v if isinstance(v, (list, dict)) else None if pd.isna(v) else v) for k, v in row.items()} for row in df_speech_matched.to_dict(orient="records")]

    # show row and column with NaN - speaker column NaN
    context.log.info(speech_data[0])

    sitting_payload = {
        "date": sitting_object["proper_date_str"],
        "filename": sitting_object["renamed_filename"],
        "is_final": is_final,
        "speech_data": json.dumps(speech_data, ensure_ascii=False),
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
    # log the json payload
    context.log.info(f"Payload summary: speeches={len(payload['speech_data'])}, is_final={payload['is_final']}")

    response = requests.post(f"{api_url}/api/sitting", json=payload, timeout=3600)
    # Check if request was successful
    try:
        response.raise_for_status()
        context.log.info(f"Successfully uploaded sitting data: {response}")
    except requests.exceptions.HTTPError as e:
        context.log.error(f"API request failed: {e}")
        context.log.error(f"Response content: {response.text}")
        if "Parliamentary cycle not found for date/house" in response.text:
            context.log.warning("Please update the latest parliamentary cycle in the database")
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
    context.log.info(f"speech_data type = {type(prepare_db_payload['speech_data'])}")
    _insert_to_db(DEV_API_URL, prepare_db_payload, context)


@asset(
    partitions_def=sitting_partitions_def, deps=[prepare_db_payload], group_name="parse"
)
def insert_to_prod_db(context: AssetExecutionContext, prepare_db_payload: dict):
    """
    Insert Hansards to Prod DB
    """
    _insert_to_db(PROD_API_URL, prepare_db_payload, context)

@asset(partitions_def=sitting_partitions_def, deps=[prepare_db_payload], group_name="parse",
)
def direct_insert_to_db(context: AssetExecutionContext, prepare_db_payload: dict,
):
    context.log.info(
        f"Direct DB insert start | filename={prepare_db_payload['filename']}"
    )

    with psycopg.connect(HANSARD_DB_URL) as conn:
        with conn.transaction():
            ingest_sitting_to_db(prepare_db_payload, conn)

    context.log.info("Direct DB insert completed")

    return {
        "filename": prepare_db_payload["filename"],
        "date": prepare_db_payload["date"],
        "is_final": prepare_db_payload["is_final"],
    }




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


@asset(group_name="scrape")
def scrape_website_arkib(context: AssetExecutionContext):
    """Scrape arkib Hansard listings."""

    limit = 5
    
    context.log.info(f"Starting arkib scrape (all PDFs)")
    run_scrape(limit=limit)
    context.log.info("Completed arkib scrape")

@asset(group_name="scrape", deps=[scrape_website_arkib])
def move_arkib_pdfs_to_public(context: AssetExecutionContext):
    """Move and rename arkib PDFs from the dataproc bucket to the public bucket with renamed filenames."""

    context.log.info("Moving and renaming arkib PDFs to public bucket...")
    move_arkib_pdfs_to_public_main(category=None, logger=context.log)
    context.log.info("Completed moving arkib PDFs")


@asset(group_name="author")
def load_author_data_to_db(context: AssetExecutionContext):
    """
    Load author data from S3 into the api_author table in the database.
    CSV file should be manually uploaded to S3 at: canonical/author.csv
    """
    return load_author_csv_to_db(
        s3_bucket=S3_DATAPROC_BUCKET,
        s3_key="canonical/author.csv",
        db_url=HANSARD_DB_URL,
        context=context,
        aws_region=AWS_REGION
    )


@asset(deps=[move_arkib_pdfs_to_public], group_name="arkib")
def dg_build_arkib_partition_queue(context: AssetExecutionContext):
    """
    Build arkib partition queue JSON file (with min_year conditions) based on list of scraped PDFs that is put in S3 PUBLIC arkib/.
    - reads and list pdfs in S3 PUBLIC arkib/ bucket
    - writes queue/arkib_partitions.pending.json to S3 DATAPROC queue
    - sensor 'trigger_arkib_pdf_move' will pick up this pending.json, and trigger job move_arkib_pdfs_job (asset: dg_move_arkib_pdf_to_s3_root).

    TODO: add dependency.
    - Asset must depend on 'move_arkib_pdfs_to_public' asset
    - because the partition queue is built by listing all the pdfs in S3 PUBLIC (once moved & renamed).

    Conditions:
    - only for sittings from year MIN_YEAR onwards (and optionally up to MAX_YEAR),
    - this is due to a lot of manual(human) edits have been made to older sittings (2007 & below),
    - to avoid overwriting those manual edits with arkib PDFs, we only refresh PDFs from MIN_YEAR onwards.
    - then trigger sittings_job on those partitions.
    """

    MIN_YEAR = ARKIB_PARTITION_MIN_YEAR
    MAX_YEAR = ARKIB_PARTITION_MAX_YEAR
    PENDING_QUEUE_KEY = "arkib/queue/arkib_partitions.pending.json"

    payload = build_arkib_partition_queue(
        s3_client=s3_client,
        bucket=S3_PUBLIC_BUCKET,
        # prefix="arkib/"
        min_year=MIN_YEAR,
        max_year=MAX_YEAR,
        logger=context.log,
    )

    s3_client.put_object(
        Bucket=S3_DATAPROC_BUCKET,
        Key=PENDING_QUEUE_KEY,
        Body=json.dumps(payload, indent=2).encode(),
        ContentType="application/json",
    )


@asset(group_name="arkib")
def dg_move_arkib_pdf_to_s3_root(context: AssetExecutionContext):
    """
    Works with sensor 'trigger_arkib_pdf_move' to process arkib partition queue.
    Promote/move arkib PDFs from S3 PUBLIC arkib/ to S3 PUBLIC root.
    - reads queue/arkib_partitions.pending.json from S3_DATAPROC_BUCKET
    - writes queue/arkib_partitions.ready.json to S3_DATAPROC_BUCKET 
    - deletes queue/arkib_partitions.pending.json from S3_DATAPROC_BUCKET after done processing.
    """

    obj = s3_client.get_object(Bucket=S3_DATAPROC_BUCKET, Key=PENDING_QUEUE_KEY)
    payload = json.loads(obj["Body"].read())

    moved = promote_arkib_pdfs(
        s3_client=s3_client,
        bucket=S3_PUBLIC_BUCKET,
        partitions=payload["partitions"],
        get_sitting_object=get_sitting_object,
        logger=context.log,
    )

    context.log.info(f"Promoted arkib PDFs to S3 PUBLIC root | Total pdfs moved: {moved}")

    context.log.info(f"Creating {READY_QUEUE_KEY}... Ready for sensor to trigger sitting jobs on arkib partitions.")

    s3_client.put_object(
        Bucket=S3_DATAPROC_BUCKET,
        Key=READY_QUEUE_KEY,
        Body=json.dumps(payload, indent=2).encode(),
        ContentType="application/json",
    )

    context.log.info(f"Deleting {PENDING_QUEUE_KEY}.")

    s3_client.delete_object(
        Bucket=S3_DATAPROC_BUCKET,
        Key=PENDING_QUEUE_KEY,
    )


@asset(group_name="legacy_queue")
def dg_build_legacy_partition_queue(context: AssetExecutionContext):
    """
    Build legacy partition queue JSON file (1959-2007) based on PDFs in S3 PUBLIC.
    Writes legacy/queue/legacy_partitions.ready.json
    """

    LEGACY_MIN_YEAR = ARKIB_PARTITION_MIN_YEAR
    LEGACY_MAX_YEAR = ARKIB_PARTITION_MAX_YEAR

    LEGACY_READY_QUEUE_KEY = "legacy/queue/legacy_partitions.ready.json"

    payload = build_arkib_partition_queue(
        s3_client=s3_client,
        bucket=S3_PUBLIC_BUCKET,
        # prefix="legacy/",
        min_year=LEGACY_MIN_YEAR,
        max_year=LEGACY_MAX_YEAR,
        logger=context.log,
    )

    s3_client.put_object(
        Bucket=S3_DATAPROC_BUCKET,
        Key=LEGACY_READY_QUEUE_KEY,
        Body=json.dumps(payload, indent=2).encode(),
        ContentType="application/json",
    )


@asset(
    partitions_def=sitting_legacy_partitions_def,
    group_name="legacy_sittings",
)
def dg_legacy_sitting(context: AssetExecutionContext):
    """
    Insert one legacy sitting (1959-2007).

    Logic:
    Checks if manually edited CSV exists in S3 DATAPROC.
    - If exists, CSV -> insert to DB
    - Else, PDF -> parse -> tabulate as CSV -> insert payload to DB
    """
    partition_key = context.partition_key
    context.log.info(f"Processing legacy sitting: {partition_key}...")

    process_legacy_pipeline(partition_key=partition_key, s3_client=s3_client)


@asset
def noop_partition_registration():
    """
    No-op asset for partition registration. Intentionally does nothing.
    This is manually triggered to create the partitions.
    """
    return None
