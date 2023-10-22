"""Helper functions"""


def warn(message, origin_filename):
    with open(f"warnings/{origin_filename}_warnings.txt", "a") as f:
        f.write(f"{message}\n")
