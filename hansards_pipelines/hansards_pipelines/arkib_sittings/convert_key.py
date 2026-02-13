def convert_arkib_key_to_partition(key: str) -> str:
    """
    Convert S3 arkib/ key to partition key format. So that we can trigger sittings_job on it.
    Example:
    arkib/dewanrakyat/dr_1986-03-17.pdf -> DR-17031968
    """
    filename = key.split("/")[-1].replace(".pdf", "")  # dn_2026-01-19
    house, date = filename.split("_")                  # dn, 2026-01-19
    yyyy, mm, dd = date.split("-")
    return f"{house.upper()}-{dd}{mm}{yyyy}"
