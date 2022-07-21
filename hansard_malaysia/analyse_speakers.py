import generate_tabular
import re

titles = [
    "YB.",
    "YB",
    "YAB.",
    "YAB",
    "Senator",
    "Tan Sri",
    "Dato' Seri Utama",
    "Dato Seri Utama",
    "Dato' Sri",
    "Dato Sri",
    "Dato' Seri",
    "Dato Seri",
    "Dato' Wira",
    "Dato Wira",
    "Dato'",
    "Dato",
    "Tuan",
    "Datuk Seri Panglima",
    "Datuk Seri",
    "Datuk Wira",
    "Datuk",
    "Haji",
    "Ir.",
    "Ir",
    "Dr.",
    "Dr",
    "Puan",
    "Tun",
    "Hajah"
]


def remove_titles(speaker):
    removal_request = 1
    while removal_request:
        removal_request = 0
        for title in titles:
            if speaker.startswith(title):
                speaker = speaker[len(title):].strip()
                removal_request = 1
            elif speaker.startswith(title.replace("'", "’")):
                speaker = speaker[len(title):].strip()
                removal_request = 1
    return speaker


def remove_role(speaker):
    if "–" not in speaker:
        return speaker
    return speaker.split("–")[0].strip()


def remove_constituency(speaker):
    # for TOC list
    speaker = re.sub("\([A-Za-z ]+\)$", '', speaker)
    # for in-text
    return re.sub("\[[A-Za-z ]+\]$", '', speaker).strip()


def get_raw_name(speaker):
    speaker = remove_role(speaker)
    speaker = remove_titles(speaker)
    speaker = remove_constituency(speaker)
    return speaker.strip()


if __name__ == "__main__":

    hansard_code = "14-04-02-15"

    with open("preprocessed_hansard/" + hansard_code + "/2.txt", 'r') as f:
        all_text = ''.join(f.readlines()[1:])

    with open("preprocessed_hansard/" + hansard_code + "/3.txt", 'r') as f:
        all_text += ''.join(f.readlines()[1:])

    with open("preprocessed_hansard/" + hansard_code + "/4.txt", 'r') as f:
        all_text += ''.join(f.readlines()[1:])

    with open("preprocessed_hansard/" + hansard_code + "/5.txt", 'r') as f:
        all_text += ''.join(f.readlines()[1:])

    segments = generate_tabular.parse_markup(all_text)
    # remove empty spaces
    segments = [x for x in segments if x[0]]
    # remove bold
    segments = [x for x in segments if not x[1]]
    speakers_string = ''.join([x[0] for x in segments])
    speakers = [x.strip() for x in re.compile("[0-9]+\.").split(speakers_string)]
    speakers = [get_raw_name(speaker) for speaker in speakers]
    for speaker in speakers:
        print(speaker)
