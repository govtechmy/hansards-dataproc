"""Directly edit specific Hansards to ease tabulation
"""


def replace(hansard_date, old_snippet, new_snippet):
    year = hansard_date[-4:]
    sortable_date = f'{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}'  # YYYY-MM-DD
    dir_path = f"preprocessed/{year}/{sortable_date}/"
    with open(dir_path + 'plaintext.txt', 'r') as f:
        text = f.read()
    num = text.count(old_snippet)
    print(f"{hansard_date} {num} instances found")
    new_text = text.replace(old_snippet, new_snippet)
    if new_text == text:
        print(f"{hansard_date} No changes made")
    else:
        print(f"{hansard_date} Changes made")
    with open(dir_path + 'plaintext.txt', 'w') as f:
        f.write(new_text)


if __name__ == "__main__":
    replace("20072022",
            "Tuan Pengerusi [Dato’ Ramli bin Dato’ Mohd Nor [Cameron Highlands)]:",
            "Tuan Pengerusi [Dato’ Ramli bin Dato’ Mohd Nor (Cameron Highlands)]:")
    replace("16082018",
            "Tuan Noor Amin bin Ahmad [Kangar] Tuan Noor Amin bin Ahmad [Kangar]:",
            "Tuan Noor Amin bin Ahmad [Kangar]:")
    replace("19112018",
            "Tuan Ahmad Fahmi bin Mohamed Fadzil [Lembah Pantai] Ya.",
            "Tuan Ahmad Fahmi bin Mohamed Fadzil [Lembah Pantai]: Ya.")
    replace("06082018",
            "Dato’ Dr. Noor Azmi bin Ghazali [Bagan Serai Ok.",
            "Dato’ Dr. Noor Azmi bin Ghazali [Bagan Serai]: Ok.")
    replace("16072019",
            "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa[ [Ketereh]: Yang",
            "Tan Sri Datuk Seri Panglima Haji Annuar bin Haji Musa [Ketereh]: Yang")
    replace("16072020",
            "Khairuddin bin Aman Razali] Terima kasih Tuan yang di-Pertua. Terima kasih Yang",
            "Khairuddin bin Aman Razali]: Terima kasih Tuan yang di-Pertua. Terima kasih Yang")
