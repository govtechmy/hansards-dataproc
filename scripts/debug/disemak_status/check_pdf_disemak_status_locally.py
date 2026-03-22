import os
import shutil
import pdfplumber

# def is_final_pdf(filepath):
#     """Returns False if the PDF contains 'naskhah belum disemak' or 'naskhah belum semak'."""
#     try:
#         with pdfplumber.open(filepath) as pdf:
#             for page in pdf.pages:
#                 text = page.extract_text()
#                 if text:
#                     text = text.lower()
#                     if "naskhah belum disemak" in text or "naskhah belum semak" in text:
#                         return False
#         return True
#     except Exception as e:
#         print(f"Error reading {filepath}: {e}")
#         return False


DRAFT_PHRASES = [
    "naskhah belum disemak",
    "naskhah belum semak",
    "nskhah belum disemak"
    "belum semak"
    "belum disemak"
]

def is_final_pdf(filepath):
    """Returns False if the PDF contains any draft phrase like 'naskhah belum disemak'."""
    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages[:2]: # Only scan first 3 pages
                words = [w["text"].lower() for w in page.extract_words()]
                joined = " ".join(words)
                if any(phrase in joined for phrase in DRAFT_PHRASES):
                    return False
        return True
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return False


def classify_and_move_pdfs(source_folder="data", final_folder="is_final", draft_folder="is_not_final"):
    os.makedirs(final_folder, exist_ok=True)
    os.makedirs(draft_folder, exist_ok=True)

    final_pdfs = []
    draft_pdfs = []

    if not os.path.exists(source_folder):
        print(f"Source folder '{source_folder}' does not exist.")
        return final_pdfs, draft_pdfs

    for filename in os.listdir(source_folder):
        if filename.lower().endswith(".pdf"):
            filepath = os.path.join(source_folder, filename)
            if is_final_pdf(filepath):
                destination = os.path.join(final_folder, filename)
                final_pdfs.append(filename)
            else:
                destination = os.path.join(draft_folder, filename)
                draft_pdfs.append(filename)

            # Move the file
            shutil.move(filepath, destination)
            print(f"Moved '{filename}' -> '{destination}'")

    return final_pdfs, draft_pdfs

if __name__ == "__main__":
    final, draft = classify_and_move_pdfs()

    print("\nFINAL PDFs:")
    for f in final:
        print(f"- {f}")

    print("\nDRAFT PDFs:")
    for d in draft:
        print(f"- {d}")
