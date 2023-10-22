"""Modify tables"""
import json


def modify_table(hansard_date, old_table, new_table):
    year = hansard_date[-4:]
    sortable_date = f'{hansard_date[-4:]}-{hansard_date[2:4]}-{hansard_date[:2]}'  # YYYY-MM-DD
    dir_path = f"parsed_pdf/{year}/{sortable_date}/"
    file_name = dir_path + 'tables.json'
    # read the list of tables from the file
    with open(file_name, 'r') as f:
        tables = json.load(f)
    # find the table that matches the old table
    for i in range(len(tables)):
        if tables[i] == old_table:
            tables[i] = new_table
            break
    # remove any null tables
    tables = [table for table in tables if table is not None]
    # load this back into the file
    with open(file_name, 'w') as f:
        json.dump(tables, f, indent=4)


def modify_tables():
    pass


if __name__ == "__main__":
    modify_tables()
