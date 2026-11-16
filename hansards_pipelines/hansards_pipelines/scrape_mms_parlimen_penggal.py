"""Explicit MMS session assignments; dates are never used to infer membership."""
import json
import re
import xml.etree.ElementTree as ET

MMS_HOUSE = "majlis-mengangkat-sumpah"
MMS_URL = "https://www.parlimen.gov.my/hansard-majlis.html"


def assignment_from_node(node_id):
    match = re.fullmatch(r"0_([1-9]\d*)_([1-9]\d*)(?:_\d+)*", node_id)
    if not match:
        raise ValueError(f"MMS node has no Parlimen/Penggal: {node_id}")
    return {"term": int(match[1]), "session": int(match[2]), "source_node": node_id}


def validate_assignment(value):
    for field in ("term", "session"):
        if type(value.get(field)) is not int or value[field] <= 0:
            raise ValueError(f"MMS requires a positive integer {field} from scraping")
    return {field: value[field] for field in ("term", "session")}


def assignment_key(filename):
    if not re.fullmatch(r"mms_\d{4}-\d{2}-\d{2}", filename):
        raise ValueError(f"Invalid normalized MMS filename: {filename}")
    return f"metadata/mms/{filename}.json"


def save_assignment(s3, bucket, filename, assignment):
    validate_assignment(assignment)
    s3.put_object(Bucket=bucket, Key=assignment_key(filename),
                  Body=json.dumps({"filename": filename, **assignment}).encode(),
                  ContentType="application/json")


def load_assignment(s3, bucket, filename):
    value = json.loads(s3.get_object(Bucket=bucket, Key=assignment_key(filename))["Body"].read())
    if value.get("filename") != filename:
        raise ValueError("MMS assignment filename mismatch")
    return validate_assignment(value)


def scrape_mms_cycles(session=None, context=None):
    """Read the MMS archive's explicit Parlimen/Penggal hierarchy for both cycle jobs.

    The portal exposes current and historical MMS sessions in this same tree.
    Stop at Penggal: MMS has no meeting or cycle dates.
    """
    if session is None:
        import requests
        session = requests.Session()

    def fetch(node):
        response = session.get(MMS_URL, params={"uweb": "dn", "arkib": "yes",
            "ajx": "0" if node == "0" else "1", "id": node}, timeout=60, verify=False)
        response.raise_for_status()
        return ET.fromstring(response.text).findall(".//item")

    cycles = []
    for term in fetch("0"):
        node = term.get("id", "")
        if not re.fullmatch(r"0_[1-9]\d*", node):
            raise ValueError(f"Unexpected MMS Parlimen node: {node}")
        for penggal in fetch(node):
            assignment = assignment_from_node(penggal.get("id", ""))
            if assignment["term"] != int(node.split("_")[1]):
                raise ValueError("MMS Penggal belongs to a different Parlimen")
            cycles.append({"house": 3, **validate_assignment(assignment),
                           "meeting": None, "start_date": None, "end_date": None})
    return cycles
