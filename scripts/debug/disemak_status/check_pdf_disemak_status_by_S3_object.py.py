"""
This script checks whether a given PDF in S3 is a final or draft version based on the presence of specific phrases in its content.
- It reads the PDF from S3, scans the first few pages for draft indicators, and prints the result.
Usage:
    python script.py <s3_key>
Example:
    python script.py dewanrakyat/DR-05062025.pdf

"""

import sys
import boto3
import pdfplumber
from io import BytesIO
from hansards_pipelines.hansards_pipelines.settings import S3_PUBLIC_BUCKET

# --- Check argument ---
if len(sys.argv) != 2:
    print("Usage: python script.py <s3_key>")
    print("Example: python script.py dewanrakyat/DR-05062025.pdf")
    sys.exit(1)

PDF_KEY = sys.argv[1]  # full S3 key like dewanrakyat/DR-xxxxxx.pdf
S3_PUBLIC_BUCKET = S3_PUBLIC_BUCKET

# --- S3 client ---
s3_client = boto3.client("s3")

DRAFT_PHRASES = [
    "naskhah belum disemak",
    "naskhah belum semak",
    # "naskhah belum",
    "nskhah belum disemak"
]

def check_is_final(pdf_bytes):
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages[:3]:
            text = page.extract_text()
            if text:
                flat_text = text.replace("\n", " ").lower()
                if any(phrase in flat_text for phrase in DRAFT_PHRASES):
                    return False
    return True


DRAFT_PHRASES = [
    "naskhah belum disemak",
    "naskhah belum semak",
    "nskhah belum disemak"
]

def check_is_final(pdf_bytes):
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages[:3]):  # Only first 3 pages
            words = [w['text'].lower() for w in page.extract_words()]
            joined = " ".join(words)
            if any(phrase in joined for phrase in DRAFT_PHRASES):
                return False
    return True



# --- Main check ---
def main():
    print(f"Checking s3://{S3_PUBLIC_BUCKET}/{PDF_KEY}...")

    try:
        obj = s3_client.get_object(Bucket=S3_PUBLIC_BUCKET, Key=PDF_KEY)
        pdf_bytes = obj["Body"].read()
        is_final = check_is_final(pdf_bytes)

        if is_final:
            print(f"{PDF_KEY}: FINAL ✅")
        else:
            print(f"{PDF_KEY}: DRAFT ❌")

    except Exception as e:
        print(f"{PDF_KEY}: ERROR - {e}")

if __name__ == "__main__":
    main()
