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


def calculate_name_specificity_score(input_name, candidate_name):
    """
    Calculate a specificity score to prefer more complete name matches.
    Helps distinguish cases like "Abdul Razak" vs "Najib bin Abdul Razak".
    
    Returns an integer adjustment score (bonus or penalty), typically in the
    range -10 to +5, to add to the fuzzy match score.
    """
    # Handle None or NaN values
    if not input_name or pd.isna(input_name) or not candidate_name or pd.isna(candidate_name):
        return 0
    
    # Ensure strings
    input_name = str(input_name)
    candidate_name = str(candidate_name)
    
    input_parts = set(input_name.upper().split())
    candidate_parts = set(candidate_name.upper().split())
    
    # If all input parts are in candidate but candidate has more, it's less specific
    if input_parts.issubset(candidate_parts):
        extra_parts = len(candidate_parts - input_parts)
        if extra_parts > 0:
            # Penalize matches where the candidate has many extra words
            # This helps prevent "Abdul Razak" matching "Najib bin Abdul Razak"
            return -5 * min(extra_parts, 2)
    
    # If candidate parts are subset of input, give bonus
    if candidate_parts.issubset(input_parts):
        return 5
    
    # Calculate overlap ratio
    overlap = len(input_parts & candidate_parts)
    max_parts = max(len(input_parts), len(candidate_parts))
    if max_parts > 0:
        overlap_ratio = overlap / max_parts
        # Prefer matches with higher overlap
        if overlap_ratio > 0.8:
            return 3
    
    return 0


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
    name, clean_names_list, scorer=fuzz.token_set_ratio, threshold=70, limit=5
):
    """
    Function to match a name to a list of names with enhanced scoring.
    Returns all matches above threshold for better disambiguation.
    """
    # Skip empty strings
    if not name or pd.isna(name) or name.strip() == "":
        return []

    # Get all matches
    matches = process.extract(name, clean_names_list, scorer=scorer, limit=limit)
    
    # Adjust scores based on name specificity to better handle father/son cases
    adjusted_matches = []
    for match, score in matches:
        # Skip None or empty matches
        if not match or pd.isna(match):
            continue
        # Add specificity adjustment
        specificity_bonus = calculate_name_specificity_score(name, match)
        adjusted_score = min(100, max(0, score + specificity_bonus))
        adjusted_matches.append((match, adjusted_score))
    
    # Re-sort by adjusted score
    adjusted_matches.sort(key=lambda x: x[1], reverse=True)
    
    # Filter by threshold
    valid_matches = [(match, score) for match, score in adjusted_matches if score >= threshold]
    
    if not valid_matches:
        # Log unmatched names for review
        best_match = matches[0] if matches else None
        if best_match:
            with open("unmatched_names.json", "a+", encoding="utf-8") as f:
                # Ensure we maintain a valid JSON array of unmatched names
                f.seek(0)
                try:
                    existing_data = json.load(f)
                    if not isinstance(existing_data, list):
                        existing_data = [existing_data]
                except json.JSONDecodeError:
                    existing_data = []
                existing_data.append(
                    {"name": name, "matched_with": best_match[0], "score": best_match[1]}
                )
                f.seek(0)
                f.truncate()
                json.dump(existing_data, f, indent=4)
        return []
    
    return valid_matches


def _is_temporally_valid(author_id, speech_dates, author_hist_df):
    """Check if any speech date falls within author's active period"""
    author_history = author_hist_df[author_hist_df["new_author_id"] == author_id]
    if author_history.empty:
        return False
    
    for speech_date in speech_dates:
        # Check if speech_date falls within any history record's date range
        for _, hist_row in author_history.iterrows():
            start_date, end_date = hist_row["start_date"], hist_row["end_date"]
            if pd.notna(start_date):
                if pd.isna(end_date) and speech_date >= start_date:
                    return True
                elif pd.notna(end_date) and start_date <= speech_date <= end_date:
                    return True
    return False


def match_by_name(speech_df, author_df, author_hist_df=None, column_name="name", threshold=70):
    """
    Match speech records to authors by name with temporal validation"""
    matches = {}

    for name in speech_df[column_name].dropna().unique():
        # Get speech dates for this name
        name_speeches = speech_df[speech_df[column_name] == name]
        speech_dates = name_speeches["date"].dropna() if "date" in name_speeches.columns else pd.Series()
        
        # Get multiple candidate matches
        # Filter out None/NaN values from author names
        clean_author_names = [n for n in author_df["name_up"].unique() if n and not pd.isna(n)]
        match_results = enhanced_match_names(
            name, clean_author_names, threshold=threshold, limit=5
        )
        
        if not match_results:
            matches[name] = None
            continue
            
        # Collect all potential author matches with their scores
        candidate_authors = [
            (author["new_author_id"], score, matched_name)
            for matched_name, score in match_results
            for _, author in author_df[author_df["name_up"] == matched_name].iterrows()
        ]
        
        if not candidate_authors:
            matches[name] = None
            continue
        
        # Apply temporal validation if we have date data
        if author_hist_df is not None and not speech_dates.empty:
            valid_temporal_matches = [
                (author_id, score, matched_name)
                for author_id, score, matched_name in candidate_authors
                if _is_temporally_valid(author_id, speech_dates, author_hist_df)
            ]
            # If temporal validation is applicable but no valid matches found, leave blank
            if not valid_temporal_matches:
                matches[name] = None
                continue
            candidates_to_use = valid_temporal_matches
        else:
            # No temporal validation possible, use all candidates
            candidates_to_use = candidate_authors
        
        # Select best match by score
        best_match = max(candidates_to_use, key=lambda x: x[1])[0]
        matches[name] = best_match

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

        # Filter out None/NaN values from constituency areas
        clean_areas = [a for a in author_hist_df["area_up"].unique() if a and not pd.isna(a)]
        match_results = enhanced_match_names(
            constituency, clean_areas, threshold=threshold, limit=3
        )
        if match_results:
            # Take the best match
            match, score = match_results[0]
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


def author_period_lookup(author_hist_df):

    author_periods = {}
    for _, row in author_hist_df.iterrows():
        author_id = row["record_id"]
        if author_id not in author_periods:
            author_periods[author_id] = []
        author_periods[author_id].append((row["start_date"], row["end_date"]))

    return author_periods


def apply_matches_with_date_context(
    speech_df,
    author_hist_df,
    name_matches_a,
    name_matches_b,
    constituency_matches_a,
    constituency_matches_b,
    position_matches_a,
    position_matches_b,
    author_periods,
    ah_to_author_id,
    context,
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

    # Ensure ID columns are object dtype so assigning None doesn't trigger dtype warnings
    id_columns = [
        "author_a_id",
        "author_b_id",
        "constituency_a_id",
        "constituency_b_id",
        "position_a_id",
        "position_b_id",
    ]
    for col in id_columns:
        result_df[col] = result_df[col].astype("object")

    # Date-based verification (vectorized approach)
    if "date" in result_df.columns:

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
        def validate_date_vectorized(df, context):
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

            context.log.info(f"Valid position a: {valid_position_a_mask.sum()}")
            context.log.info(f"Valid position b: {valid_position_b_mask.sum()}")

            # Apply masks to set invalid matches to None
            df.loc[~valid_position_a_mask, "position_a_id"] = None
            df.loc[~valid_position_b_mask, "position_b_id"] = None

            return df

        # Apply the vectorized date validation
        result_df = validate_date_vectorized(result_df, context)

    # Combine matches using vectorized operations with priority order:
    # 1. author_a_id or author_b_id (name matches)
    # 2. constituency_a_id or constituency_b_id (constituency matches)
    # 3. position_a_id or position_b_id (position matches)

    # Start with name matches
    result_df["author_id"] = result_df["author_a_id"].combine_first(
        result_df["author_b_id"]
    ).astype("object")
    context.log.info(
        f"Name matches: {(~result_df['author_id'].isna()).sum()}/{len(result_df)}"
    )

    # map author_id to new_author_id
    result_df["constituency_a_author_id"] = result_df["constituency_a_id"].map(
        ah_to_author_id
    )
    result_df["constituency_b_author_id"] = result_df["constituency_b_id"].map(
        ah_to_author_id
    )
    result_df["position_a_author_id"] = result_df["position_a_id"].map(ah_to_author_id)
    result_df["position_b_author_id"] = result_df["position_b_id"].map(ah_to_author_id)

    # Use constituency matches as fallback where author_id is null
    null_mask = result_df["author_id"].isna()
    context.log.info(f"Null authors: {null_mask.sum()}/{len(result_df)}")
    result_df.loc[null_mask, "author_id"] = result_df.loc[
        null_mask, "constituency_a_id"
    ]
    context.log.info(
        f"Constituency A matches: {(~result_df['author_id'].isna()).sum()}/{len(result_df)}"
    )

    still_null_mask = result_df["author_id"].isna()
    context.log.info(f"Still null authors: {still_null_mask.sum()}/{len(result_df)}")
    result_df.loc[still_null_mask, "author_id"] = result_df.loc[
        still_null_mask, "constituency_b_id"
    ]
    context.log.info(
        f"Constituency B matches: {(~result_df['author_id'].isna()).sum()}/{len(result_df)}"
    )

    # Use position matches as a final fallback
    still_null_mask = result_df["author_id"].isna()
    context.log.info(f"Still null authors: {still_null_mask.sum()}/{len(result_df)}")
    result_df.loc[still_null_mask, "author_id"] = result_df.loc[
        still_null_mask, "position_a_id"
    ]
    context.log.info(
        f"Position A matches: {(~result_df['author_id'].isna()).sum()}/{len(result_df)}"
    )
    still_null_mask = result_df["author_id"].isna()
    context.log.info(f"Still null authors: {still_null_mask.sum()}/{len(result_df)}")
    result_df.loc[still_null_mask, "author_id"] = result_df.loc[
        still_null_mask, "position_b_id"
    ]
    context.log.info(
        f"Position B matches: {(~result_df['author_id'].isna()).sum()}/{len(result_df)}"
    )

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

    df_speech_only["date"] = pd.to_datetime(df_speech_only["date"])

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
    # 1. Get matches by name with temporal validation
    name_matches_a = match_by_name(
        df_speech_only, author_df, author_hist_df, "author_a_up", threshold=70
    )
    name_matches_b = match_by_name(
        df_speech_only, author_df, author_hist_df, "author_b_up", threshold=70
    )

    # 2. Get matches by constituency
    constituency_matches_a = match_by_constituency(
        df_speech_only, author_hist_df, "author_a_up", threshold=70
    )
    constituency_matches_b = match_by_constituency(
        df_speech_only, author_hist_df, "author_b_up", threshold=70
    )

    # 3. Get matches by position/jawatan
    position_to_author = match_position_to_author(author_hist_df)
    position_matches_a = match_author_by_position(
        df_speech_only, position_to_author, "author_a_up", date_column="date"
    )
    position_matches_b = match_author_by_position(
        df_speech_only, position_to_author, "author_b_up", date_column="date"
    )

    # generate lookups
    author_periods = author_period_lookup(author_hist_df)
    ah_to_author_id = author_hist_df.set_index("record_id")["new_author_id"].to_dict()

    df_result = apply_matches_with_date_context(
        df_speech_only,
        author_hist_df,
        name_matches_a,
        name_matches_b,
        constituency_matches_a,
        constituency_matches_b,
        position_matches_a,
        position_matches_b,
        author_periods,
        ah_to_author_id,
        context,
    )

    # 4. Analyze match rate
    match_rate = (df_result["author_id"] != "NO MATCH").mean() * 100

    # Check if any matched author_ids are invalid (not in author_df)
    # These should be treated as unmatched
    matched_mask = df_result["author_id"] != "NO MATCH"
    if matched_mask.any():
        author_id_to_name = author_df.set_index("new_author_id")["name"].to_dict()
        invalid_matches = df_result[matched_mask].copy()
        invalid_matches["test_name"] = invalid_matches["author_id"].map(author_id_to_name)
        invalid_mask = invalid_matches["test_name"].isna()
        if invalid_mask.any():
            df_result.loc[invalid_matches[invalid_mask].index, "author_id"] = "NO MATCH"
            
    # 5. Review unmatched records
    unmatched = df_result[df_result["author_id"] == "NO MATCH"]
    context.log.info(
        f"Match rate: {match_rate:.2f}% ({len(df_result) - len(unmatched)}/{len(df_result)} records)"
    )

    # Log unmatched authors before setting NO MATCH to None
    if not unmatched.empty:
        unmatched_counts = unmatched["author"].value_counts(dropna=False)
        unique_unmatched = unmatched["author"].unique()
        total_unmatched_mentions = len(unmatched)
        if len(unique_unmatched) > 0:
            unmatched_log_lines = [f"Authors that could not be matched (Total: {len(unique_unmatched)}, {total_unmatched_mentions} mentions):"]
            for author in sorted(unique_unmatched, key=lambda x: str(x)):
                if pd.isna(author):
                    count = unmatched["author"].isna().sum()
                else:
                    count = unmatched_counts[author]
                unmatched_log_lines.append(f"  {author} ({count} mention{'s' if count > 1 else ''})")
            context.log.info("\n".join(unmatched_log_lines))

    df_result.loc[df_result["author_id"] == "NO MATCH", "author_id"] = None

    # Log author matching results
    matched_authors = df_result[df_result["author_id"].notna()].copy()
    if not matched_authors.empty:
        author_id_to_name = author_df.set_index("new_author_id")["name"].to_dict()
        matched_authors["matched_name"] = matched_authors["author_id"].map(author_id_to_name)
        matched_counts = matched_authors["author"].value_counts()
        total_matched_mentions = len(matched_authors)
        unique_matches = matched_authors[["author", "matched_name"]].drop_duplicates()
        unique_matches = unique_matches.sort_values("matched_name", na_position="last")
        
        log_lines = [f"Final author matching results (Total: {len(unique_matches)}, {total_matched_mentions} mentions):"]
        for _, row in unique_matches.iterrows():
            author = row["author"]
            if pd.isna(author):
                count = matched_authors["author"].isna().sum()
            else:
                count = matched_counts[author]
            log_lines.append(f"  {author} → {row['matched_name']} ({count} mention{'s' if count > 1 else ''})")
        
        context.log.info("\n".join(log_lines))

    # Merge with original speech dataframe
    speech_df_final = speech_df.merge(
        df_result[["date", "house", "index", "author_id"]],
        on=["date", "house", "index"],
        how="left",
    )

    return speech_df_final