"""
Website: https://data.mysociety.org/datasets/everypolitician-malaysia-dewan-rakyat/
"""
import pandas as pd
import json
import re

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


def add_party_columns(
    df: pd.DataFrame,
    party_en_path: str,
    party_bm_path: str,
) -> pd.DataFrame:

    with open(party_en_path, "r") as f:
        party_en = json.load(f)

    with open(party_bm_path, "r") as f:
        party_bm = json.load(f)

    # Build reverse lookup for EN
    reverse_en = {}
    for key, value in party_en.items():
        base = re.sub(r"\s*\(.*?\)\s*$", "", value).strip().lower()
        reverse_en[base] = key

    # Build reverse lookup for BM
    reverse_bm = {}
    for key, value in party_bm.items():
        base = re.sub(r"\s*\(.*?\)\s*$", "", value).strip().lower()
        reverse_bm[base] = key

    def resolve_party(group_value):

        if not isinstance(group_value, str):
            return (None, None, None)

        party_en_keys_lower = {k.lower(): k for k in party_en.keys()}
        party_bm_keys_lower = {k.lower(): k for k in party_bm.keys()}

        g = group_value.strip().lower()

        # Direct key match (EN)
        if g in party_en:
            key = g.upper()
            return (key, party_en.get(key), party_bm.get(key))

        # Direct key match (BM)
        if g in party_bm:
            key = g.upper()
            return (key, party_en.get(key), party_bm.get(key))

        # English long name match
        if g in reverse_en:
            key = reverse_en[g]
            return (key, party_en.get(key), party_bm.get(key))

        # BM long name match
        if g in reverse_bm:
            key = reverse_bm[g]
            return (key, party_en.get(key), party_bm.get(key))

        # Partial EN match
        for base, key in reverse_en.items():
            if base in g:
                return (key, party_en.get(key), party_bm.get(key))

        # Partial BM match
        for base, key in reverse_bm.items():
            if base in g:
                return (key, party_en.get(key), party_bm.get(key))

        return (None, None, None)

    df[["party", "party_name_en", "party_name_bm"]] = df["group"].apply(
        lambda x: pd.Series(resolve_party(x))
    )

    return df

def main():
    PARTY_BM_PATH = "utils/party-bm.json"
    PARTY_EN_PATH = "utils/party-en.json"

    merged_df = load_and_merge_terms(START_TERM, END_TERM)

    filtered_df = filter_columns(merged_df, KEEP_COLUMNS)

    filtered_df = add_area_name(filtered_df)

    final_df = add_party_columns(filtered_df,PARTY_EN_PATH, PARTY_BM_PATH)

    unmapped = final_df[final_df["party"].isna()]["group"].unique()
    if len(unmapped) > 0:
        print("Unmapped parties found:")
        print(unmapped)

    output_file = f"outputs/politicians_dr_term_{START_TERM}_{END_TERM}_cleaned.csv"

    final_df.to_csv(output_file, index=False)

    print(f"Saved: {output_file}")
    print(f"Rows: {len(final_df)}")


if __name__ == "__main__":
    main()