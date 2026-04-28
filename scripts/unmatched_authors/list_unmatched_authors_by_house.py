"""
Unmatched Authors from S3

This script reads unmatched authors JSON files from S3 bucket:

Output:
    s3://<bucket>/unmatched_authors/unmatched_authors_years/{house}_unmatched_authors.csv
    s3://<bucket>/unmatched_authors/unmatched_authors_years/{house}_unmatched_authors.xlsx

Output format:
    author | total_mentions | years_appeared | documents_list
"""

import os
import argparse

from _utils import (
    S3_BUCKET,
    S3_UNMATCHED_AUTHORS,
    HOUSES,
    get_s3_client,
    extract_date_from_filename,
    extract_year_from_date,
    list_json_files,
    read_json_from_s3,
    create_summary_dataframe,
    save_dataframe_to_s3,
    save_dataframe_to_local,
)


def aggregate_house_data(s3_client, bucket: str, house: str) -> list:
    """
    Aggregate all unmatched authors for a given house.
    
    Returns:
        list: [{"author": ..., "document": ..., "year": ...}, ...]
    """
    prefix = f"{S3_UNMATCHED_AUTHORS}/{house}/"
    files = list_json_files(s3_client, bucket, prefix)
    
    print(f"Found {len(files)} files for house: {house}")
    
    all_records = []
    
    for file_key in files:
        filename = os.path.basename(file_key)
        date_str = extract_date_from_filename(filename)
        
        if not date_str:
            print(f"Skipping file with unrecognized format: {filename}")
            continue
            
        year = extract_year_from_date(date_str)
        if not year:
            print(f"Could not extract year from: {date_str}")
            continue
        
        # Read the JSON file
        authors = read_json_from_s3(s3_client, bucket, file_key)
        
        # Add each author to records
        for author in authors:
            # Normalize None and empty/whitespace-only strings
            author_name = "(NULL/EMPTY)" if author is None or not str(author).strip() else author
            all_records.append({
                "author": author_name,
                "document": filename.replace(".json", ""),
                "year": year
            })
    
    return all_records


def run(profile_name: str = None, local_output: str = None):
    """
    Main function to aggregate unmatched authors by house.
    
    Args:
        profile_name: AWS profile name to use. If None, uses default credentials.
        local_output: If provided, save files locally to this directory instead of S3.
    """
    print("=" * 60)
    print("Aggregating Unmatched Authors by House")
    print(f"Bucket: {S3_BUCKET}")
    if profile_name:
        print(f"AWS Profile: {profile_name}")
    if local_output:
        print(f"Local Output: {local_output}")
    print("=" * 60)
    
    s3_client = get_s3_client(profile_name)
    
    for house in HOUSES:
        print(f"\n{'='*40}")
        print(f"Processing house: {house.upper()}")
        print(f"{'='*40}")
        
        # Aggregate all data for this house
        all_records = aggregate_house_data(s3_client, S3_BUCKET, house)
        
        if not all_records:
            print(f"No data found for house: {house}")
            continue
        
        # Create summary dataframe
        df = create_summary_dataframe(all_records)
        
        # Count unique authors and years
        unique_authors = df["author"].nunique()
        total_mentions = df["total_mentions"].sum()
        
        print(f"\nSummary: {unique_authors} unique authors, {total_mentions} total mentions")
        
        # Save
        base_key = f"{S3_UNMATCHED_AUTHORS}/unmatched_authors_years/{house}_unmatched_authors"
        
        if local_output:
            save_dataframe_to_local(df, local_output, f"{house}_unmatched_authors")
        else:
            save_dataframe_to_s3(s3_client, S3_BUCKET, df, base_key)
    
    print(f"\n{'='*60}")
    print("Done!")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate unmatched authors from S3 and save as CSV/XLSX by house"
    )
    parser.add_argument(
        "--profile", "-p",
        type=str,
        default=None,
        help="AWS profile name to use (e.g., 'govtech-dev')"
    )
    parser.add_argument(
        "--local", "-l",
        type=str,
        default=None,
        help="Save files locally to this directory instead of uploading to S3"
    )
    args = parser.parse_args()

    run(profile_name=args.profile, local_output=args.local)


if __name__ == "__main__":
    main()
