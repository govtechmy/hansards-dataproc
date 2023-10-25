"""Directly edit specific Hansards to ease tabulation
"""
import re


def replace(hansard_date, old_text_snippet, new_text_snippet, new_bold_snippet, new_italics_snippet):
    if new_bold_snippet == "all":
        new_bold_snippet = re.sub(r'\S', '1', new_text_snippet)
    if new_italics_snippet == "all":
        new_italics_snippet = re.sub(r'\S', '1', new_text_snippet)
    if new_bold_snippet == "none":
        new_bold_snippet = re.sub(r'\S', '0', new_text_snippet)
    if new_italics_snippet == "none":
        new_italics_snippet = re.sub(r'\S', '0', new_text_snippet)

    assert re.fullmatch(r'[\s01]*', new_bold_snippet), \
        f'new_bold_snippet ({new_bold_snippet}) must only contain 0s and 1s'
    assert re.fullmatch(r'[\s01]*', new_italics_snippet), \
        f'new_italics_snippet ({new_italics_snippet}) must only contain 0s and 1s'
    assert len(new_text_snippet) == len(new_bold_snippet) == len(new_italics_snippet), \
        f"new_text_snippet ({new_text_snippet}), new_bold_snippet ({new_bold_snippet}), " \
        f"and new_italics_snippet ({new_italics_snippet}) must be of the same length"
    assert len(new_text_snippet.replace(' ', '')) == len(new_bold_snippet.replace(' ', '')) == len(
        new_italics_snippet.replace(' ', '')), \
        f"Without spaces, new_text_snippet ({new_text_snippet.replace(' ', '')}), " \
        f"new_bold_snippet ({new_bold_snippet.replace(' ', '')}), " \
        f"and new_italics_snippet ({new_italics_snippet.replace(' ', '')}) must be of the same length"
    year = hansard_date[-4:]
    sortable_date = f'{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}'  # YYYY-MM-DD
    dir_path = f"pretabulation/{year}/{sortable_date}/"
    with open(dir_path + 'plaintext.txt', 'r') as f:
        text = f.readlines()
    with open(dir_path + 'bold.txt', 'r') as f:
        bold = f.readlines()
    with open(dir_path + 'italics.txt', 'r') as f:
        italics = f.readlines()
    num_edits = 0
    for idx in range(len(text)):
        if old_text_snippet == text[idx]:
            # get the starting index where the match begins
            text[idx] = new_text_snippet
            bold[idx] = new_bold_snippet
            italics[idx] = new_italics_snippet
            num_edits += 1

    with open(dir_path + 'plaintext.txt', 'w') as f:
        f.writelines(text)
    with open(dir_path + 'bold.txt', 'w') as f:
        f.writelines(bold)
    with open(dir_path + 'italics.txt', 'w') as f:
        f.writelines(italics)
    print(f"{hansard_date} Num changes made: {num_edits}")


def edit_hansards():
    replace('18102021',
            "Mesyuaratdimulakanpadapukul10.00pagi\n",
            "Mesyuarat dimulakan pada pukul 10.00 pagi\n",
            'all',
            'none')
    replace('23122008',
            "(cid:2) 5.29 ptg.\n",
            "5.29 ptg.\n",
            "all",
            "none")


if __name__ == "__main__":
    edit_hansards()
