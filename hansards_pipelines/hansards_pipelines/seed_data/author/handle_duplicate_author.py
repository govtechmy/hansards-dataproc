import os
import logging
import psycopg
from pathlib import Path
import pandas as pd
from hansards_pipelines import settings

logger = logging.getLogger(__name__)


def load_csv_data(csv_path):
    """Load author data from CSV file"""
    logger.info("LOADING CSV DATA")
    logger.info(f"Reading from: {csv_path}")
    
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    df = pd.read_csv(csv_path)
    logger.info(f"Loaded {len(df)} records from CSV")
    logger.info(f"Columns: {list(df.columns)}")
    
    return df


def load_db_data(db_url):
    """Load author data from database"""
    logger.info("LOADING DATABASE DATA")
    
    if not db_url:
        logger.warning("Database URL not provided, skipping DB check")
        return pd.DataFrame()
    
    try:
        with psycopg.connect(db_url) as conn:
            query = "SELECT new_author_id, name, birth_year, ethnicity, sex FROM api_author"
            df = pd.read_sql_query(query, conn)
            logger.info(f"Loaded {len(df)} records from database")
            return df
    except Exception as e:
        logger.error(f"Error loading from database: {e}")
        raise


def check_duplicates(df, source_name="CSV"):
    """Check for duplicates within a dataframe"""
    logger.info(f"CHECKING {source_name} DUPLICATES")
    
    if 'name' not in df.columns:
        logger.error(f"Missing 'name' column in {source_name}")
        return
    
    # Create normalized name as a local Series (don't mutate input DataFrame)
    normalized_names = df['name'].str.lower().str.strip()
    
    # Create a temporary DataFrame with normalized names for duplicate detection
    temp_df = df.copy()
    temp_df['_normalized_name'] = normalized_names
    
    # Find duplicates
    duplicates_mask = temp_df.duplicated(subset=['_normalized_name'], keep=False)
    duplicates = temp_df[duplicates_mask].sort_values('_normalized_name')
    
    if duplicates.empty:
        logger.info(f"✓ No duplicates found in {source_name}")
    else:
        dup_count = len(duplicates)
        unique_dup_names = duplicates['_normalized_name'].nunique()
        logger.warning(f"✗ Found {dup_count} duplicate records ({unique_dup_names} unique names)")
        
        logger.info(f"\nDuplicate names in {source_name}:")
        for name in duplicates['_normalized_name'].unique()[:20]:  # Show first 20
            instances = duplicates[duplicates['_normalized_name'] == name]
            logger.info(f"\n  '{instances.iloc[0]['name']}' appears {len(instances)} times:")
            for idx, row in instances.iterrows():
                logger.info(f" - ID: {row.get('new_author_id', 'N/A')}, Name: {row['name']}")
    
    return duplicates


def check_cross_duplicates(csv_df, db_df):
    """Check for duplicates between CSV and Database"""
    logger.info("CHECKING CROSS-DUPLICATES (CSV vs DATABASE)")
    
    if db_df.empty:
        logger.info("Skipping cross-check (no database data)")
        return
    
    # Create normalized names as local Series (don't mutate input DataFrames)
    csv_normalized = csv_df['name'].str.lower().str.strip()
    db_normalized = db_df['name'].str.lower().str.strip()
    
    # Find overlaps
    csv_names = set(csv_normalized)
    db_names = set(db_normalized)
    
    overlapping_names = csv_names.intersection(db_names)
    
    logger.info(f"CSV unique names: {len(csv_names)}")
    logger.info(f"DB unique names: {len(db_names)}")
    logger.info(f"Overlapping names: {len(overlapping_names)}")
    
    if overlapping_names:
        logger.warning(f"\n✗ Found {len(overlapping_names)} names that exist in BOTH CSV and Database")
        logger.info("\nFirst 20 overlapping names:")
        for name in list(overlapping_names)[:20]:
            # Use the normalized Series for comparison
            csv_instance = csv_df[csv_normalized == name].iloc[0]
            db_instance = db_df[db_normalized == name].iloc[0]
            logger.info(f" '{csv_instance['name']}'")
            logger.info(f" CSV ID: {csv_instance.get('new_author_id', 'N/A')}")
            logger.info(f" DB ID:  {db_instance.get('new_author_id', 'N/A')}")
    else:
        logger.info("✓ No overlapping names between CSV and Database")


def merge_and_deduplicate(csv_df, db_df):
    """
    Merge CSV and DB data, then deduplicate.
    Priority: Keep DB records over CSV records for same name
    """
    logger.info("MERGING AND DEDUPLICATING")
    
    # Add source column to track origin
    csv_df_copy = csv_df.copy()
    csv_df_copy['_source'] = 'CSV'
    
    if not db_df.empty:
        db_df_copy = db_df.copy()
        db_df_copy['_source'] = 'DB'
        
        # Combine both dataframes
        combined = pd.concat([db_df_copy, csv_df_copy], ignore_index=True)
    else:
        combined = csv_df_copy
    
    logger.info(f"Total records before deduplication: {len(combined)}")
    
    # Normalize names for deduplication
    combined['_normalized_name'] = combined['name'].str.lower().str.strip()
    
    # Before deduplication, log cases where the same normalized name has conflicting attributes
    conflict_cols = [col for col in ['new_author_id', 'birth_year', 'ethnicity', 'sex'] if col in combined.columns]
    if conflict_cols:
        grouped = combined.groupby('_normalized_name', dropna=False)
        for normalized_name, group in grouped:
            if len(group) < 2:
                continue
            has_conflict = False
            for col in conflict_cols:
                if group[col].nunique(dropna=False) > 1:
                    has_conflict = True
                    break
            if has_conflict:
                cols_to_show = ['name'] + conflict_cols + ['_source']
                logger.warning(
                    "Deduplicating authors with same normalized name '%s' but conflicting attributes; "
                    "keeping first occurrence based on source priority. Conflicting rows:\n%s",
                    normalized_name,
                    group[cols_to_show].to_string(index=False),
                )
    
    # Sort by source (DB first, then CSV) so DB records are kept
    combined['_source_priority'] = combined['_source'].map({'DB': 0, 'CSV': 1})
    combined = combined.sort_values('_source_priority')
    
    # Remove duplicates (keeps first occurrence = DB record if exists)
    deduped = combined.drop_duplicates(subset=['_normalized_name'], keep='first').copy()
    
    logger.info(f"Records after deduplication: {len(deduped)}")
    logger.info(f"Removed: {len(combined) - len(deduped)} duplicate records")
    
    # Show source breakdown
    source_counts = deduped['_source'].value_counts()
    logger.info(f"\nFinal records by source:")
    for source, count in source_counts.items():
        logger.info(f"  {source}: {count}")
    
    # Clean up temporary columns
    deduped = deduped.drop(columns=['_normalized_name', '_source', '_source_priority'])
    
    return deduped


def save_output(df, output_dir):
    """Save deduplicated data to CSV"""
    logger.info("SAVING OUTPUT")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Remove full_name column if it exists (DB doesn't have it)
    if 'full_name' in df.columns:
        df = df.drop(columns=['full_name'])
        logger.info("Removed 'full_name' column (not in database schema)")
    
    output_path = os.path.join(output_dir, 'author.csv')
    
    # Save to CSV
    df.to_csv(output_path, index=False)
    
    logger.info(f"Saved {len(df)} records to: {output_path}")
    logger.info(f"Columns: {list(df.columns)}")
    
    return output_path


def main():
    """Main execution"""
    logger.info("AUTHOR DUPLICATE HANDLER")
    
    # Configuration
    project_root = Path(__file__).parent.parent.parent.parent.parent
    csv_path = project_root / "scripts" / "ahli_parlimen" / "outputs" / "author.csv"
    output_dir = Path(__file__).parent / "output"
    db_url = settings.HANSARD_DB_URL
    
    logger.info(f"\nConfiguration:")
    logger.info(f"  CSV Input: {csv_path}")
    logger.info(f"  Output Dir: {output_dir}")
    logger.info(f"  DB URL: {'Configured' if db_url else 'Not configured'}")
    
    # Step 1: Load CSV data
    csv_df = load_csv_data(str(csv_path))
    
    # Step 2: Load DB data (if available)
    db_df = load_db_data(db_url) if db_url else pd.DataFrame()
    
    # Step 3: Check for duplicates in CSV
    check_duplicates(csv_df, "CSV")
    
    # Step 4: Check for duplicates in DB (if available)
    if not db_df.empty:
        check_duplicates(db_df, "DATABASE")
    
    # Step 5: Check for cross-duplicates
    if not db_df.empty:
        check_cross_duplicates(csv_df, db_df)
    
    # Step 6: Merge and deduplicate
    final_df = merge_and_deduplicate(csv_df, db_df)
    
    # Step 7: Save output
    output_path = save_output(final_df, str(output_dir))
    
    # Summary
    logger.info("SUMMARY")
    logger.info(f"CSV records: {len(csv_df)}")
    logger.info(f"DB records: {len(db_df)}")
    logger.info(f"Final deduplicated records: {len(final_df)}")
    logger.info(f"Output saved to: {output_path}")
    logger.info("\n✓ COMPLETE!")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    main()
