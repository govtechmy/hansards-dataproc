import boto3
from hansards_pipelines.utils.text_utils import house_mapper
from hansards_pipelines.legacy_pipeline.insert_sitting_csv_to_db import process_and_insert as csv_process_and_insert
from hansards_pipelines.legacy_pipeline.process_textracted import build_textracted_key, process_and_insert as pipeline_process_and_insert
from hansards_pipelines.settings import S3_TEXTRACT_BUCKET
from datetime import datetime
from botocore.exceptions import ClientError

def partition_key_to_insert_args(partition_key: str):
    """
    Convert partition key to arguments for insertion. 
    The partition key is in the format "HOUSE-DDMMYYYY".

    The outputs are:
    - prefix: House prefix (dewanrakyat, dewannegara, or kamarkhas)
    - s3_key: S3 object key for the CSV file e.g., dewannegara/dn_2007-04-29.csv
    - date_str: Date string in YYYY-MM-DD format e.g., 2007-04-29
    
    Example:
    DN-29042007
    -> (
        prefix='dewannegara',
        s3_key='dewannegara/dn_2007-04-29.csv',
        date_str='2007-04-29'
        )
    """
    try:
        house_code, dmy = partition_key.split("-", 1)
        dt = datetime.strptime(dmy, "%d%m%Y")
    except Exception:
        raise ValueError(f"Invalid partition_key: {partition_key}")

    prefix = house_mapper.to_canonical(house_code) # DN -> dewannegara
    date_str = dt.strftime("%Y-%m-%d")
    filename = f"{house_code.lower()}_{date_str}.csv"
    s3_key = f"{prefix}/{filename}"

    return prefix, s3_key, date_str

def run_process_textracted(prefix: str, date_str: str, logger) -> None:
    """
    Entry point for Dagster legacy job.
    """
    house_code = house_mapper.to_code(prefix).lower()
    filename = f"{house_code}_{date_str}_layout.csv"
    key = build_textracted_key(prefix, filename)


    pipeline_process_and_insert(prefix, key, date_str, logger=logger)


# def process_legacy_pipeline(*, partition_key: str, s3_client, logger) -> None:
#     """
#     Process a single partition key for S3 and insert the corresponding data into the database.

#     There is a conditional check to see if a manual CSV exists for the given partition key. 
#     - If it exists, it processes and inserts that CSV directly.
#     - If not, it runs the pipeline to parse the PDF, generate the CSV, and then insert the data.

#     Args:        
#     partition_key: A string in the format "HOUSE-DDMMYYYY" (e.g., "DN-29042007")
#     """
#     prefix, s3_key, date_str = partition_key_to_insert_args(partition_key)

#     manual_key = f"manual_cleanup/{prefix}/{s3_key.split('/')[-1]}"

#     try:
#         s3_client.head_object(Bucket=S3_TEXTRACT_BUCKET, Key=manual_key)

#         logger.info("Manually cleaned CSV found -> direct csv insert into DB | %s", manual_key)

#         csv_process_and_insert(prefix=prefix, key=manual_key, date_str=date_str, logger=logger)
#         return

#     except ClientError as e:
#         # key does not exist
#         if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
#             logger.info("Manually cleaned CSV not found -> run process textracted pipeline | %s", partition_key)
#         else:
#             raise

#     run_process_textracted(prefix=prefix, date_str=date_str, logger=logger)

def process_legacy_pipeline(*, partition_key: str, s3_client, logger) -> None:
    """
    Always run the process textracted pipeline to parse the PDF, generate the CSV, and then insert the data.
    Ignore the existence of manually cleaned CSV for now, as we want to prioritise having the textracted pipeline 
    as the source of truth and have a consistent process for all partitions.
    """

    prefix, s3_key, date_str = partition_key_to_insert_args(partition_key)

    logger.info("Running textracted pipeline | %s", partition_key)

    run_process_textracted(prefix=prefix, date_str=date_str, logger=logger)
