"""
Website: https://data.mysociety.org/datasets/everypolitician-malaysia-dewan-rakyat/
"""
import pandas as pd


BASE_URL = "https://cdn.rawgit.com/everypolitician/everypolitician-data/aedf80c57d1c5c4ec726843070c466e678452ef6/data/Malaysia/Dewan_Rakyat/term-{}.csv"


START_TERM = 1
END_TERM = 13

KEEP_COLUMNS = [
    "id",
    "name",
    "group",
    "area_id",
    "area",
    "chamber",
    "term",
    "start_date",
    "end_date",
    "gender",
]


def load_and_merge_terms(start_term: int, end_term: int) -> pd.DataFrame:
    dfs = []

    for term in range(start_term, end_term + 1):
        url = BASE_URL.format(term)
        print(f"Loading term {term}")
        df = pd.read_csv(url)
        dfs.append(df)

    return pd.concat(dfs, ignore_index=True)


def filter_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    return df[columns].copy()


def add_area_name(df: pd.DataFrame) -> pd.DataFrame:
    df["area_name"] = (
        df["area_id"].fillna("").astype(str).str.strip()
        + " "
        + df["area"].fillna("").astype(str).str.strip()
    ).str.strip()

    return df


def main():
    merged_df = load_and_merge_terms(START_TERM, END_TERM)

    filtered_df = filter_columns(merged_df, KEEP_COLUMNS)

    final_df = add_area_name(filtered_df)

    output_file = f"malaysia_dewan_rakyat_term_{START_TERM}_to_{END_TERM}_cleaned.csv"

    final_df.to_csv(output_file, index=False)

    print(f"Saved: {output_file}")
    print(f"Rows: {len(final_df)}")


if __name__ == "__main__":
    main()