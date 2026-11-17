"""Explicit MMS session assignments; dates are never used to infer membership."""
import json
from io import BytesIO
import re
import xml.etree.ElementTree as ET

import pdfplumber
import requests

from hansards_pipelines.utils.malay_numbers import malay_ordinal_to_number
from hansards_pipelines.utils.text_utils import get_sitting_object

MMS_HOUSE = "majlis-mengangkat-sumpah"
MMS_URL = "https://www.parlimen.gov.my/hansard-majlis.html"


class ActiveMmsScraper:
    """Prepare active MMS metadata, caching the hierarchy for one scrape run."""

    def __init__(self, *, s3, bucket, logger, scrape_assignments):
        self.s3 = s3
        self.bucket = bucket
        self.logger = logger
        self.scrape_assignments = scrape_assignments
        self.assignments = None

    def prepare(self, filename, pdf_url):
        """Save membership and return a downloaded PDF response for reuse, if any."""
        if self.assignments is None:
            self.assignments = self.scrape_assignments()
        assignment = self.assignments.get(filename)
        pdf_response = None
        if assignment is None:
            pdf_response = requests.get(pdf_url, verify=False, timeout=300)
            pdf_response.raise_for_status()
            assignment = assignment_from_pdf(pdf_response.content, pdf_url)
            if assignment["metadata_conflict"]:
                self.logger.warning(
                    f"MMS Parlimen/Penggal differs between PDF pages for {filename}: "
                    f"{assignment['pdf_evidence']}. Using page {assignment['source_page']}."
                )
        sitting = get_sitting_object(filename)
        save_assignment(self.s3, self.bucket, sitting["renamed_filename"], assignment)
        return pdf_response


def assignment_from_pdf_pages(pages, source_url):
    """Prefer the first-page cover; retain page-two evidence and disagreements."""
    evidence = []
    for page_number, text in enumerate(pages[:2], 1):
        values = {}
        for label, field in (("PARLIMEN", "term"), ("PENGGAL", "session")):
            matches = re.findall(rf"^\s*{label}\s+([^\r\n]+)", text or "", re.IGNORECASE | re.MULTILINE)
            numbers = set()
            for label_text in matches:
                label_text = label_text.strip()
                numeric = re.fullmatch(r"(?:KE[- ]?)?(\d+)", label_text, re.IGNORECASE)
                number = int(numeric[1]) if numeric else malay_ordinal_to_number(label_text)
                if not number:
                    raise ValueError(f"Unrecognised MMS {label} on PDF page {page_number}: {label_text}")
                numbers.add(number)
            if len(numbers) > 1:
                raise ValueError(f"Conflicting MMS {label} labels within PDF page {page_number}")
            if numbers:
                values[field] = numbers.pop()
        if len(values) == 2:
            evidence.append({"page": page_number, **validate_assignment(values)})

    if not evidence:
        raise ValueError("No complete MMS Parlimen/Penggal found on PDF pages 1 or 2")
    chosen = evidence[0]
    conflict = any((item["term"], item["session"]) != (chosen["term"], chosen["session"])
                   for item in evidence[1:])
    return {**validate_assignment(chosen), "source": "pdf", "source_url": source_url,
            "source_page": chosen["page"], "pdf_evidence": evidence,
            "metadata_conflict": conflict}


def assignment_from_pdf(content, source_url):
    with pdfplumber.open(BytesIO(content)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages[:2]]
    return assignment_from_pdf_pages(pages, source_url)


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
                  Body=json.dumps({**assignment, "filename": filename}).encode(),
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
