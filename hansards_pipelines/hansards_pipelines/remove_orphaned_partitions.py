"""
This standalone script identifies and removes orphaned partitions from Dagster.

Orphaned partitions are partitions that exist in Dagster's dynamic_partitions table
but do not have corresponding sittings in the application database (api_sitting table).

The script performs the following steps:
1. Fetches all dynamic partitions from Dagster DB for 'house_sittings' partition definition
2. Fetches all sitting filenames from the Hansard application database
3. Converts partition keys to filename format to match against database records
4. Identifies orphaned partitions (in Dagster but not in DB)
5. Optionally removes them from Dagster (with dry-run mode for safety)

Usage:
    # Dry run (default) - only shows what would be deleted
    python remove_orphaned_partitions.py
    
    # Check legacy partitions
    python remove_orphaned_partitions.py --partition-def house_sittings_legacy
    
    # Actually delete orphaned partitions
    python remove_orphaned_partitions.py --execute
    
    # Delete orphaned legacy partitions
    python remove_orphaned_partitions.py --partition-def house_sittings_legacy --execute
    
    # Limit to specific houses
    python remove_orphaned_partitions.py --houses DR DN
    
    # Save results to file
    python remove_orphaned_partitions.py --output orphaned.json

Reason: Over time, partitions may be created in Dagster but fail to insert into the database,
or sittings may be manually removed from the database.
"""

import argparse
import json
import psycopg2
from datetime import datetime, timezone
from typing import Set, List, Dict, Optional

from hansards_pipelines.settings import DAGSTER_DB_URL, HANSARD_DB_URL

# Constants
DEFAULT_PARTITION_DEF_NAME = "house_sittings"


def partition_key_to_filename(partition_key: str) -> str:
    """
    Convert Dagster partition key to database filename format.
    
    Example:
        DR-31122024 -> dr_2024-12-31
        DN-01012025 -> dn_2025-01-01
    """
    try:
        house_code, dmy = partition_key.split("-", 1)
        
        # Parse DDMMYYYY
        day = dmy[0:2]
        month = dmy[2:4]
        year = dmy[4:8]
        
        # Convert to house_YYYY-MM-DD format
        house_lower = house_code.lower()
        filename = f"{house_lower}_{year}-{month}-{day}"
        
        return filename
    except Exception as e:
        print(f"Warning: Failed to convert partition key '{partition_key}': {e}")
        return None


def get_dagster_partitions(houses: Optional[List[str]] = None, partition_def_name: str = DEFAULT_PARTITION_DEF_NAME) -> Set[str]:
    """Fetch all partitions from Dagster database."""
    conn_str = DAGSTER_DB_URL.replace("postgresql+psycopg2://", "postgresql://")
    with psycopg2.connect(conn_str) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT partition
                FROM dynamic_partitions
                WHERE partitions_def_name = %s
                ORDER BY partition
            """, (partition_def_name,))

            all_partitions = {row[0] for row in cur.fetchall()}

            # Filter by house if specified
            if houses:
                houses_upper = [h.upper() for h in houses]
                all_partitions = {
                    p for p in all_partitions
                    if any(p.startswith(f"{h}-") for h in houses_upper)
                }

            return all_partitions


def get_hansard_db_filenames(houses: Optional[List[str]] = None) -> Set[str]:
    """Fetch all sitting filenames from Hansard application database."""
    conn_str = HANSARD_DB_URL.replace("postgresql+psycopg2://", "postgresql://")
    with psycopg2.connect(conn_str) as conn:
        with conn.cursor() as cur:
            if houses:
                # Filter by house prefix in filename
                houses_lower = [h.lower() for h in houses]
                placeholders = ','.join(['%s'] * len(houses_lower))
                query = f"""
                    SELECT DISTINCT filename
                    FROM api_sitting
                    WHERE filename LIKE ANY(ARRAY[{','.join([f"'{h}_%'" for h in houses_lower])}])
                    ORDER BY filename
                """
                cur.execute(query)
            else:
                cur.execute("""
                    SELECT DISTINCT filename
                    FROM api_sitting
                    ORDER BY filename
                """)

            filenames = {row[0] for row in cur.fetchall()}
            return filenames
def find_orphaned_partitions(
    dagster_partitions: Set[str], 
    db_filenames: Set[str]
) -> List[Dict[str, str]]:
    """
    Identify partitions in Dagster that don't have corresponding records in the database.
    
    Returns a list of dictionaries with partition key and converted filename.
    """
    orphaned = []
    
    for partition in dagster_partitions:
        filename = partition_key_to_filename(partition)
        
        if filename is None:
            # Conversion failed, mark as potentially problematic
            orphaned.append({
                "partition": partition,
                "expected_filename": "INVALID_FORMAT",
                "reason": "Failed to convert partition key"
            })
        elif filename not in db_filenames:
            # Partition exists but no corresponding sitting in DB
            orphaned.append({
                "partition": partition,
                "expected_filename": filename,
                "reason": "Not found in database"
            })
    
    return orphaned


def delete_orphaned_partitions(partitions: List[str], partition_def_name: str = DEFAULT_PARTITION_DEF_NAME, dry_run: bool = True) -> int:
    """
    Delete orphaned partitions from Dagster database.
    
    Args:
        partitions: List of partition keys to delete
        partition_def_name: Name of the partition definition
        dry_run: If True, don't actually delete (default: True)
    
    Returns:
        Number of partitions deleted (or would be deleted in dry-run)
    """
    if not partitions:
        return 0
    
    if dry_run:
        print(f"\n[DRY RUN] Would delete {len(partitions)} orphaned partitions")
        return len(partitions)
    
    conn = psycopg2.connect(DAGSTER_DB_URL.replace("postgresql+psycopg2://", "postgresql://"))
    cur = conn.cursor()
    
    try:
        # Delete partitions
        cur.execute("""
            DELETE FROM dynamic_partitions
            WHERE partitions_def_name = %s
              AND partition = ANY(%s)
        """, (partition_def_name, partitions))
        
        deleted_count = cur.rowcount
        conn.commit()
        
        print(f"\n✓ Successfully deleted {deleted_count} orphaned partitions from Dagster")
        return deleted_count
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error deleting partitions: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def save_results(orphaned: List[Dict[str, str]], output_file: str):
    """Save orphaned partitions to JSON file."""
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_orphaned": len(orphaned),
        "orphaned_partitions": orphaned,
    }
    
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Identify and remove orphaned partitions from Dagster"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete orphaned partitions (default is dry-run only)"
    )
    parser.add_argument(
        "--partition-def",
        type=str,
        default=DEFAULT_PARTITION_DEF_NAME,
        choices=["house_sittings", "house_sittings_legacy"],
        help="Partition definition name (default: house_sittings)"
    )
    parser.add_argument(
        "--houses",
        nargs="+",
        choices=["DR", "DN", "KK", "dr", "dn", "kk"],
        help="Limit to specific houses (DR=Dewan Rakyat, DN=Dewan Negara, KK=Kamar Khas)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Save results to JSON file"
    )
    
    args = parser.parse_args()
    
    # Normalize house codes to uppercase
    houses = [h.upper() for h in args.houses] if args.houses else None
    
    print("=" * 70)
    print("REMOVE ORPHANED PARTITIONS")
    print("=" * 70)
    print(f"Mode: {'EXECUTE' if args.execute else 'DRY RUN'}")
    print(f"Partition Definition: {args.partition_def}")
    if houses:
        print(f"Houses: {', '.join(houses)}")
    else:
        print("Houses: All")
    print("=" * 70)
    
    # Step 1: Get all partitions from Dagster
    print("\n1. Fetching partitions from Dagster...")
    dagster_partitions = get_dagster_partitions(houses, args.partition_def)
    print(f"   Found {len(dagster_partitions)} partitions in Dagster")
    
    # Step 2: Get all filenames from Hansard DB
    print("\n2. Fetching sittings from Hansard DB...")
    db_filenames = get_hansard_db_filenames(houses)
    print(f"   Found {len(db_filenames)} sittings in database")
    
    # Step 3: Identify orphaned partitions
    print("\n3. Identifying orphaned partitions...")
    orphaned = find_orphaned_partitions(dagster_partitions, db_filenames)
    print(f"   Found {len(orphaned)} orphaned partitions")
    
    if not orphaned:
        print("\n✓ No orphaned partitions found. All Dagster partitions have corresponding database records.")
        return
    
    # Display orphaned partitions
    print("\n" + "=" * 70)
    print("ORPHANED PARTITIONS")
    print("=" * 70)
    print(f"{'Partition Key':<20} {'Expected Filename':<25} {'Reason'}")
    print("-" * 70)
    
    for item in orphaned[:50]:  # Show first 50
        print(f"{item['partition']:<20} {item['expected_filename']:<25} {item['reason']}")
    
    if len(orphaned) > 50:
        print(f"\n... and {len(orphaned) - 50} more")
    
    # Step 4: Save results if requested
    if args.output:
        save_results(orphaned, args.output)
    
    # Step 5: Delete orphaned partitions
    orphaned_keys = [item["partition"] for item in orphaned]
    deleted_count = delete_orphaned_partitions(orphaned_keys, args.partition_def, dry_run=not args.execute)
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total partitions in Dagster: {len(dagster_partitions)}")
    print(f"Total sittings in database:  {len(db_filenames)}")
    print(f"Orphaned partitions found:   {len(orphaned)}")
    
    if args.execute:
        print(f"Partitions deleted:          {deleted_count}")
    else:
        print(f"\nRun with --execute to actually delete these partitions")
    
    print("=" * 70)


if __name__ == "__main__":
    main()