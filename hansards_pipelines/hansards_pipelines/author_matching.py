import re
import pandas as pd
from thefuzz import fuzz, process
import json


def normalize_malaysian_name(name, remove_titles=True, standardize_spacing=True):
    """
    Normalize Malaysian politician names by handling titles, honorifics, and formatting issues.

    Parameters:
    -----------
    name : str
        The name to normalize
    remove_titles : bool, default=True
        Whether to remove honorific titles or keep them in standardized form
    standardize_spacing : bool, default=True
        Whether to standardize spacing in the name

    Returns:
    --------
    str
        Normalized name
    """
    if not name or pd.isna(name):
        return name

    # Convert to uppercase for processing
    name = name.upper().strip()

    # Define title patterns to handle
    titles = {
        # Royal and noble titles
        "royal": [
            "YANG DI-PERTUAN AGONG",
            "YANG DIPERTUAN AGONG",
            "YDP AGONG",
            "SULTAN",
            "RAJA",
            "TENGKU",
            "TUNKU",
            "YANG AMAT MULIA",
            "YANG MULIA",
            "YAMTUAN",
            "YANG TERAMAT MULIA",
            "YAM",
            "YTM",
            "YAMDIPERTUAN",
            "YAB DATUK SERI UTAMA",
            "YAB DATUK SERI",
            "YAB DATO SERI",
            "YB DATUK",
            "YB DATO",
            "YB",
            "YANG BERHORMAT",
        ],
        # Federal and state titles
        "federal": [
            "TUN",
            "TUAN",
            "TAN SRI",
            "PUAN SRI",
            "DATUK SERI",
            "DATUK SERI PANGLIMA",
            "DATUK SERI UTAMA",
            "DATO' SERI",
            "DATO SERI",
            "DATO SRI",
            "DATO'",
            "DATO",
            "DATUK",
            "DATIN SERI",
            "DATIN PADUKA",
            "DATIN",
            "TOH PUAN",
        ],
        # Religious titles
        "religious": [
            "HAJI",
            "HJ",
            "HAJJAH",
            "HJH",
            "USTAZ",
            "USTAZAH",
            "AL-HAFIZ",
            "HAFIZ",
            "MUFTI",
            "SHEIKH",
            "SYEIKH",
        ],
        # Professional titles
        "professional": [
            "DR",
            "DR.",
            "DOKTOR",
            "PROFESOR",
            "PROF",
            "PROF.",
            "IR",
            "IR.",
            "INSINYUR",
            "ENGR",
            "ENGINEER",
        ],
        # Military and police titles
        "military": [
            "JENERAL",
            "JEN",
            "GENERAL",
            "LAKSAMANA",
            "LEFTENAN",
            "KAPTEN",
            "MEJAR",
            "KOLONEL",
            "KOMANDER",
            "ACP",
            "ASP",
            "DSP",
            "SAC",
            "DCP",
            "CP",
            "IGP",
        ],
        # Positions and roles
        # "position": [
        #     "MENTERI",
        #     "TIMBALAN MENTERI",
        #     "SETIAUSAHA",
        #     "PARLIMEN",
        #     "PENGERUSI",
        #     "SPEAKER",
        #     "TIMBALAN SPEAKER",
        #     "PERDANA MENTERI",
        #     "TIMBALAN PERDANA MENTERI",
        #     "KETUA MENTERI",
        #     "MENTERI BESAR",
        # ],
    }

    # Flatten the titles list for efficient processing
    all_titles = []
    for category in titles.values():
        all_titles.extend(category)

    # Sort titles by length (descending) to ensure longer titles are matched first
    all_titles.sort(key=len, reverse=True)

    # Name components
    name_components = {
        "connectors": [
            "BIN",
            "BINTI",
            "B.",
            "BT.",
            "BT",
            "ANAK",
            "A/L",
            "A/P",
            "S/O",
            "D/O",
        ],
        "ignored": ["AND", "&", "@"],
    }

    # Create a working copy
    normalized_name = name

    # First pass: Remove quotes and standardize spacing
    normalized_name = normalized_name.replace('"', "").replace("'", "").replace("’", "")
    if standardize_spacing:
        # Replace multiple spaces with a single space
        normalized_name = " ".join(normalized_name.split())

    # Second pass: Remove or mark titles if requested
    if remove_titles:
        for title in all_titles:
            # Add word boundaries to avoid partial matches
            pattern = r"(?i)(\b" + title + r"\b)"
            # Remove the title
            normalized_name = re.sub(pattern, "", normalized_name)

        # Remove parenthesized content (often contains titles or alternate names)
        normalized_name = re.sub(r"\([^)]*\)", "", normalized_name)

        # Clean up any resulting multiple spaces
        if standardize_spacing:
            normalized_name = " ".join(normalized_name.split())
    else:
        # Option to standardize titles instead of removing them
        # Implementation would go here
        pass

    # Third pass: Handle special cases
    # Replace apostrophes in names like "Mu'adz" consistently
    normalized_name = re.sub(r"(\w)\'(\w)", r"\1\2", normalized_name)

    # Final cleanup
    normalized_name = normalized_name.strip()

    # Fix repeat words that might appear after title removal
    words = normalized_name.split()
    unique_words = []
    for word in words:
        if not unique_words or word != unique_words[-1]:
            unique_words.append(word)
    normalized_name = " ".join(unique_words)

    return normalized_name


def preprocess_names_for_matching(df, name_column, output_column=None):
    """
    Preprocess a column of names in a dataframe for better matching

    Parameters:
    -----------
    df : pandas.DataFrame
        The dataframe containing names
    name_column : str
        The column containing names
    output_column : str, optional
        Column to store normalized names. If None, overwrites the input column.

    Returns:
    --------
    pandas.DataFrame
        DataFrame with normalized names
    """
    if output_column is None:
        output_column = name_column + "_normalized"

    # Copy the dataframe to avoid modifying the original
    result_df = df.copy()

    # Apply normalization to all names
    result_df[output_column] = result_df[name_column].apply(
        lambda x: normalize_malaysian_name(x) if not pd.isna(x) else x
    )

    return result_df


def enhanced_match_names(
    name, clean_names_list, scorer=fuzz.token_set_ratio, threshold=70
):
    """
    Function to match a name to a list of names with enhanced scoring
    Returns the matched name and score if above threshold, otherwise None
    """
    # Skip empty strings
    if not name or pd.isna(name) or name.strip() == "":
        return None, None

    match, score = process.extractOne(name, clean_names_list, scorer=scorer)

    if score < threshold:
        # Log unmatched names for review
        with open("unmatched_names.json", "a+") as f:
            json.dump(
                {"name": name, "matched_with": match, "score": score}, f, indent=4
            )
        return None, None
    else:
        return match, score


def match_by_name(speech_df, author_df, column_name, threshold=70):
    """Match speech records to authors by name"""
    matches = {}

    for name in speech_df[column_name].dropna().unique():
        result = enhanced_match_names(
            name, author_df["name_up"].unique(), threshold=threshold
        )
        if result[0] is not None:
            match, score = result
            matched_author = author_df[author_df["name_up"] == match]
            if not matched_author.empty:
                matches[name] = matched_author.iloc[0]["new_author_id"]
            else:
                matches[name] = None
        else:
            matches[name] = None

    return matches


def match_by_constituency(speech_df, author_hist_df, column_name, threshold=70):
    """Match speech records to authors by constituency"""
    constituency_matches = {}

    for constituency in speech_df[column_name].dropna().unique():
        # Skip if it doesn't look like a constituency (e.g., is a title or position)
        if any(
            title in constituency.lower()
            for title in ["menteri", "tuan", "puan", "dato", "datuk", "speaker"]
        ):
            constituency_matches[constituency] = None
            continue

        result = enhanced_match_names(
            constituency, author_hist_df["area_up"].unique(), threshold=threshold
        )
        if result[0] is not None:
            match, score = result
            matched_records = author_hist_df[author_hist_df["area_up"] == match]
            if not matched_records.empty:
                # Get the most recent record if multiple matches (MPs may change over time)
                # Assuming there's a date field to sort by
                matched_records = matched_records.sort_values(
                    "end_date", ascending=False
                )
                constituency_matches[constituency] = matched_records.iloc[0][
                    "record_id"
                ]
            else:
                constituency_matches[constituency] = None
        else:
            constituency_matches[constituency] = None

    return constituency_matches


def apply_matches_with_date_context(
    speech_df,
    author_hist_df,
    name_matches_a,
    name_matches_b,
    constituency_matches_a,
    constituency_matches_b,
    position_matches_a,
    position_matches_b,
):
    """Apply matches with date context using vectorized operations for better performance"""
    # Create result DataFrame to avoid modifying the original
    result_df = speech_df.copy()

    # Apply name matches (vectorized operations)
    result_df["author_a_id"] = result_df["author_a_up"].map(name_matches_a)
    result_df["author_b_id"] = result_df["author_b_up"].map(name_matches_b)

    # Apply constituency matches (vectorized operations)
    result_df["constituency_a_id"] = result_df["author_a_up"].map(
        constituency_matches_a
    )
    result_df["constituency_b_id"] = result_df["author_b_up"].map(
        constituency_matches_b
    )

    # Apply position matches (vectorized operations)
    result_df["position_a_id"] = result_df["author_a_up"].map(position_matches_a)
    result_df["position_b_id"] = result_df["author_b_up"].map(position_matches_b)

    # Date-based verification (vectorized approach)
    if "date" in result_df.columns:
        # Create efficient lookup dictionaries for author time periods
        author_periods = {}
        for _, row in author_hist_df.iterrows():
            author_id = row["record_id"]
            if author_id not in author_periods:
                author_periods[author_id] = []
            author_periods[author_id].append((row["start_date"], row["end_date"]))

        # Function to check if a date falls within any period for an author
        def is_date_valid(author_id, date):
            if pd.isna(date) or author_id is None or author_id not in author_periods:
                return False

            for start_date, end_date in author_periods[author_id]:
                # If start_date is null, skip this period
                if pd.isna(start_date):
                    continue

                # If end_date is null, it means the term is still active
                # So any date after start_date is valid
                if pd.isna(end_date):
                    if date >= start_date:
                        return True
                # Normal case where both start and end dates exist
                elif start_date <= date <= end_date:
                    return True
            return False

        # Vectorize the date validation (still creating a helper function for clarity)
        def validate_date_vectorized(df):
            # Create masks for valid date ranges
            valid_a_mask = df.apply(
                lambda row: (
                    is_date_valid(row["author_a_id"], row["date"])
                    if not pd.isna(row["author_a_id"])
                    else False
                ),
                axis=1,
            )

            valid_b_mask = df.apply(
                lambda row: (
                    is_date_valid(row["author_b_id"], row["date"])
                    if not pd.isna(row["author_b_id"])
                    else False
                ),
                axis=1,
            )

            # Add validation for position matches
            valid_position_a_mask = df.apply(
                lambda row: (
                    is_date_valid(row["position_a_id"], row["date"])
                    if not pd.isna(row["position_a_id"])
                    else False
                ),
                axis=1,
            )

            valid_position_b_mask = df.apply(
                lambda row: (
                    is_date_valid(row["position_b_id"], row["date"])
                    if not pd.isna(row["position_b_id"])
                    else False
                ),
                axis=1,
            )

            # Apply masks to set invalid matches to None
            df.loc[~valid_a_mask, "author_a_id"] = None
            df.loc[~valid_b_mask, "author_b_id"] = None
            df.loc[~valid_position_a_mask, "position_a_id"] = None
            df.loc[~valid_position_b_mask, "position_b_id"] = None
            return df

        # Apply the vectorized date validation
        result_df = validate_date_vectorized(result_df)

    # Combine matches using vectorized operations with priority order:
    # 1. author_a_id or author_b_id (name matches)
    # 2. constituency_a_id or constituency_b_id (constituency matches)
    # 3. position_a_id or position_b_id (position matches)

    # Start with name matches
    result_df["author_id"] = result_df["author_a_id"].combine_first(
        result_df["author_b_id"]
    )

    # Use constituency matches as fallback where author_id is null
    null_mask = result_df["author_id"].isna()
    result_df.loc[null_mask, "author_id"] = result_df.loc[
        null_mask, "constituency_a_id"
    ]

    still_null_mask = result_df["author_id"].isna()
    result_df.loc[still_null_mask, "author_id"] = result_df.loc[
        still_null_mask, "constituency_b_id"
    ]

    # Use position matches as a final fallback
    still_null_mask = result_df["author_id"].isna()
    result_df.loc[still_null_mask, "author_id"] = result_df.loc[
        still_null_mask, "position_a_id"
    ]

    still_null_mask = result_df["author_id"].isna()
    result_df.loc[still_null_mask, "author_id"] = result_df.loc[
        still_null_mask, "position_b_id"
    ]

    # Fill remaining NAs with 'NO MATCH'
    result_df["author_id"] = result_df["author_id"].fillna("NO MATCH")

    return result_df


# position/jawatan matching
def match_position_to_author(author_hist_df):
    """
    Create a mapping from positions to author IDs

    Parameters:
    -----------
    author_hist_df : pandas.DataFrame
        The author history dataframe with exec_posts and service_posts

    Returns:
    --------
    dict
        Dictionary mapping positions to author IDs
    """
    position_to_author = {}

    # For each author in the history dataframe
    for _, row in author_hist_df.iterrows():
        author_id = row["record_id"]
        # author_name = row["author"]

        # Process exec_posts (already a list or can be converted to one)
        if "exec_posts" in row and pd.notna(row["exec_posts"]):
            exec_posts = row["exec_posts"]
            # Handle different data formats (string, list, etc.)
            if isinstance(exec_posts, str):
                try:
                    exec_posts = eval(
                        exec_posts
                    )  # If stored as string representation of list
                except:
                    exec_posts = [exec_posts]  # Single string
            elif not isinstance(exec_posts, list):
                exec_posts = [exec_posts]  # Convert other types to list

            # Add each position to the mapping
            for position in exec_posts:
                if position:
                    position = position.upper()  # Standardize case
                    if position not in position_to_author:
                        position_to_author[position] = []

                    position_to_author[position].append(
                        {
                            "author_id": author_id,
                            # "author": author_name,
                            "start_date": (
                                row["start_date"] if "start_date" in row else None
                            ),
                            "end_date": row["end_date"] if "end_date" in row else None,
                        }
                    )

        # Same for service_posts
        if "service_posts" in row and pd.notna(row["service_posts"]):
            service_posts = row["service_posts"]
            # Handle different data formats
            if isinstance(service_posts, str):
                try:
                    service_posts = eval(service_posts)
                except:
                    service_posts = [service_posts]
            elif not isinstance(service_posts, list):
                service_posts = [service_posts]

            # Add each position to the mapping
            for position in service_posts:
                if position:
                    position = position.upper()  # Standardize case
                    if position not in position_to_author:
                        position_to_author[position] = []

                    position_to_author[position].append(
                        {
                            "author_id": author_id,
                            # "author": author_name,
                            "start_date": (
                                row["start_date"] if "start_date" in row else None
                            ),
                            "end_date": row["end_date"] if "end_date" in row else None,
                        }
                    )

    return position_to_author


def match_author_by_position(
    speech_df, position_to_author, column_name, date_column=None, threshold=70
):
    """
    Match author_a values to positions and find corresponding authors

    Parameters:
    -----------
    speech_df : pandas.DataFrame
        DataFrame with author_a_up column containing positions
    position_to_author : dict
        Mapping from positions to author IDs
    date_column : str, optional
        Column name containing speech date for temporal verification
    threshold : int, default=70
        Threshold for fuzzy matching

    Returns:
    --------
    dict
        Dictionary mapping author_a values to author IDs
    """
    position_matches = {}
    all_positions = list(position_to_author.keys())

    # For each unique position in column_name
    for position in speech_df[column_name].dropna().unique():
        # Skip if it doesn't look like a position
        if any(term in position.upper() for term in ["area", "PARLIMEN", "P."]):
            continue

        # Try exact match first
        if position.upper() in position_to_author:
            matches = position_to_author[position.upper()]
            if matches:
                # Sort by recency if multiple matches
                recent_matches = sorted(
                    [m for m in matches if pd.notna(m["end_date"])],
                    key=lambda x: x["end_date"],
                    reverse=True,
                )
                position_matches[position] = (
                    recent_matches[0]["author_id"]
                    if recent_matches
                    else matches[0]["author_id"]
                )
                continue

        # Try fuzzy matching if no exact match
        match_result = process.extractOne(
            position.upper(), all_positions, scorer=fuzz.token_set_ratio
        )
        if match_result and match_result[1] >= threshold:
            matched_position = match_result[0]
            matches = position_to_author[matched_position]
            if matches:
                # Sort by recency if multiple matches
                recent_matches = sorted(
                    [m for m in matches if pd.notna(m["end_date"])],
                    key=lambda x: x["end_date"],
                    reverse=True,
                )
                position_matches[position] = (
                    recent_matches[0]["author_id"]
                    if recent_matches
                    else matches[0]["author_id"]
                )

    return position_matches


def apply_position_matches_to_speeches(
    speech_df, position_matches, column_name, date_column=None
):
    """
    Apply position matches to speech dataframe

    Parameters:
    -----------
    speech_df : pandas.DataFrame
        DataFrame with author_a and author_b columns
    position_matches : dict
        Mapping from positions to author IDs
    date_column : str, optional
        Column with speech dates for temporal verification

    Returns:
    --------
    pandas.DataFrame
        DataFrame with position matches applied
    """
    result_df = speech_df.copy()

    # Create position match column
    result_df["position_match_id"] = None

    # Apply matches
    for idx, row in result_df.iterrows():
        if pd.notna(row[column_name]) and row[column_name] in position_matches:
            # If we have a date, verify the match is temporally valid
            if (
                date_column
                and pd.notna(row[date_column])
                and isinstance(position_matches[row[column_name]], dict)
            ):
                match_info = position_matches[row[column_name]]
                if (
                    pd.isna(match_info["start_date"])
                    or pd.isna(match_info["end_date"])
                    or (
                        match_info["start_date"]
                        <= row[date_column]
                        <= match_info["end_date"]
                    )
                ):
                    result_df.at[idx, "position_match_id"] = match_info["author_id"]
            else:
                # No date verification needed
                result_df.at[idx, "position_match_id"] = position_matches[
                    row[column_name]
                ]

    return result_df


def perform_author_matching(speech_df, author_df, author_hist_df, context):
    """Perform author matching on speech dataframe"""

    # filter out annotation rows
    df_speech_only = speech_df[speech_df["is_annotation"] == False].drop(
        columns=["is_annotation"]
    )

    context.log.info(f"Speech columns: {df_speech_only.columns}")

    columns_to_keep = ["index", "author", "speech", "date", "house"]

    df_speech_only = df_speech_only.loc[:, columns_to_keep]

    # extract author_a [author_b] from author column
    df_speech_only["author_a"] = df_speech_only["author"].str.extract(
        r"^(.*?)(?:\s*\[(.*?)\])?$"
    )[0]
    df_speech_only["author_b"] = df_speech_only["author"].str.extract(
        r"^(.*?)\s*\[(.*?)\]$"
    )[1]

    # preprocess names for matching
    df_speech_only = preprocess_names_for_matching(
        df_speech_only, "author_a", "author_a_up"
    )
    df_speech_only = preprocess_names_for_matching(
        df_speech_only, "author_b", "author_b_up"
    )
    author_df = preprocess_names_for_matching(author_df, "name", "name_norm")

    # Ensure consistent case for matching
    author_hist_df["area_up"] = author_hist_df["area"].str.upper()
    author_df["name_up"] = author_df["name_norm"].str.upper()

    # Ensure the date column is in datetime format
    author_hist_df["start_date"] = pd.to_datetime(author_hist_df["start_date"])
    author_hist_df["end_date"] = pd.to_datetime(author_hist_df["end_date"])

    # Perform matching
    # 1. Get matches by name
    name_matches_a = match_by_name(
        df_speech_only, author_df, "author_a_up", threshold=70
    )
    name_matches_b = match_by_name(
        df_speech_only, author_df, "author_b_up", threshold=70
    )
    context.log.info(f"Matches by name results:")
    context.log.info(f"Author A: {len(name_matches_a)}")
    context.log.info(f"Author B: {len(name_matches_b)}")

    # 2. Get matches by constituency
    constituency_matches_a = match_by_constituency(
        df_speech_only, author_hist_df, "author_a_up", threshold=70
    )
    constituency_matches_b = match_by_constituency(
        df_speech_only, author_hist_df, "author_b_up", threshold=70
    )
    context.log.info(f"Matches by constituency results:")
    context.log.info(f"Author A: {len(constituency_matches_a)}")
    context.log.info(f"Author B: {len(constituency_matches_b)}")

    # 3. Get matches by position/jawatan
    position_to_author = match_position_to_author(author_hist_df)
    position_matches_a = match_author_by_position(
        df_speech_only, position_to_author, "author_a_up", date_column="date"
    )
    position_matches_b = match_author_by_position(
        df_speech_only, position_to_author, "author_b_up", date_column="date"
    )

    context.log.info(f"Matches by position results:")
    context.log.info(f"Author A: {len(position_matches_a)}")
    context.log.info(f"Author B: {len(position_matches_b)}")

    df_result = apply_matches_with_date_context(
        df_speech_only,
        author_hist_df,
        name_matches_a,
        name_matches_b,
        constituency_matches_a,
        constituency_matches_b,
        position_matches_a,
        position_matches_b,
    )

    # 4. Analyze match rate
    match_rate = (df_result["author_id"] != "NO MATCH").mean() * 100

    # 5. Review unmatched records
    unmatched = df_result[df_result["author_id"] == "NO MATCH"]
    context.log.info(
        f"Match rate: {match_rate:.2f}% ({len(df_result) - len(unmatched)}/{len(df_result)} records)"
    )

    df_result.loc[df_result["author_id"] == "NO MATCH", "author_id"] = None

    # Merge with original speech dataframe
    speech_df_final = speech_df.merge(
        df_result[["date", "house", "index", "author_id"]],
        on=["date", "house", "index"],
        how="left",
    )

    return speech_df_final
