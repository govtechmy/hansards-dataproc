import csv
import json
import io
from typing import List


def build_path(current_key: str, filename: str, sitting_object: dict):
    """Build save directory for parsed hansard files"""
    path_parts = [
        current_key,
        sitting_object["house_folder"],
        sitting_object["date_str"],
        filename,
    ]
    return "/".join(path_parts)


def read_txt_file(s3_client, s3_bucket, s3_key) -> List[str]:
    """Read file from s3 and return as list of string
    Replicating the behaviour of open() readlines()"""
    response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
    return response.get("Body").read().decode("utf-8").splitlines(keepends=True)


def read_json_file(s3_client, s3_bucket, s3_key) -> dict:
    """Read JSON file from s3 and return as dict"""
    response = s3_client.get_object(Bucket=s3_bucket, Key=s3_key)

    # Have to call json loads twice else file will be a str type
    return json.loads(response.get("Body").read().decode("utf-8"))


def prepare_text_for_s3(text_lines: List[str]) -> str:
    """Ensure all lines have newline characters before joining"""
    return "".join(line if line.endswith("\n") else line + "\n" for line in text_lines)


def prepare_json_for_s3(json_dict: dict) -> str:
    """Convert dict to JSON string"""
    return json.dumps(json_dict)


def prepare_csv_for_s3(text_lines: List[str]) -> str:
    """Convert list of strings to CSV"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["level_1", "level_2", "level_3", "timestamp", "author", "speech"])
    writer.writerows(text_lines)
    output.seek(0)
    return output.getvalue()
