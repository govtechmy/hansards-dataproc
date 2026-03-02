import os
import argparse
import sys
import io
import pandas as pd
import boto3
from dotenv import load_dotenv
import psycopg

# Load environment variables
load_dotenv()
db_url = os.environ.get("HANSARD_DB_URL")


def get_db_connection():
    if not db_url:
        print("Error: HANSARD_DB_URL environment variable is missing.")
        sys.exit(1)
    try:
        return psycopg.connect(db_url)
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)


def prompt_input(prompt_text, required=False, type_func=str, default=None):
    """Helper to prompt for user input with optional validation."""
    while True:
        display_prompt = prompt_text
        if default is not None:
            display_prompt += f" [{default}]"
        
        value = input(f"{display_prompt}: ").strip()
        
        if not value:
            if default is not None:
                return default
            if required:
                print("This field is required.")
                continue
            return None
        
        try:
            return type_func(value)
        except ValueError:
            print(f"Invalid input. Expected type {type_func.__name__}.")


def prompt_choice(prompt_text, choices, required=False, default=None):
    """Helper to prompt for a multiple-choice selection."""
    while True:
        display_prompt = f"{prompt_text}\n"
        for i, choice in enumerate(choices, 1):
            display_prompt += f"  {i}. {choice}\n"
        
        display_prompt += f"Select an option (1-{len(choices)})"
        if default is not None:
             # Find the index of the default value to show as the default option number
             try:
                 default_idx = choices.index(default) + 1
                 display_prompt += f" [{default_idx}]"
             except ValueError:
                 display_prompt += f" [{default}]"
                 
        display_prompt += ": "
        
        value = input(display_prompt).strip()
        
        if not value:
            if default is not None:
                return default
            if required:
                print("This field is required.")
                continue
            return None
            
        try:
            choice_idx = int(value)
            if 1 <= choice_idx <= len(choices):
                return choices[choice_idx - 1]
            else:
                print(f"Invalid selection. Please choose a number between 1 and {len(choices)}.")
        except ValueError:
            # Maybe they typed the exact value instead of the number
            if value in choices:
                return value
            print("Invalid input. Please enter a number corresponding to your choice.")


def lookup_area(conn):
    """Helper function to look up an Area ID based on name or state."""
    print("\n--- Area Lookup ---")
    search_term = prompt_input("Enter area name or state to search (or press Enter to skip search)", required=False)
    
    if not search_term:
        return prompt_input("Enter Area ID directly (leave blank if none)", required=False, type_func=int)
    
    with conn.cursor() as cur:
        # Search by name or state (case-insensitive)
        query = """
            SELECT id, name, type, state 
            FROM api_area 
            WHERE name ILIKE %s OR state ILIKE %s
            ORDER BY state, name
            LIMIT 20
        """
        search_pattern = f"%{search_term}%"
        cur.execute(query, (search_pattern, search_pattern))
        results = cur.fetchall()
        
        if not results:
            print(f"No areas found matching '{search_term}'.")
            return prompt_input("Enter Area ID directly (leave blank if none)", required=False, type_func=int)
            
        print("\nFound the following areas:")
        print(f"{'ID':<6} | {'Name':<30} | {'Type':<12} | {'State':<20}")
        print("-" * 75)
        for row in results:
            area_id, name, area_type, state = row
            # Handle potentially null values
            name_str = name if name else ""
            type_str = area_type if area_type else ""
            state_str = state if state else ""
            print(f"{area_id:<6} | {name_str:<30} | {type_str:<12} | {state_str:<20}")
            
        print("-" * 75)
        
        return prompt_input("Enter the Area ID from the list above (leave blank if none)", required=False, type_func=int)


def handle_manual_entry():
    """Interactive mode for adding an author and optionally their history."""
    print("=== Manual Author Entry ===")
    conn = get_db_connection()
    
    try:
        with conn.cursor() as cur:
            # 1. Prompt for Author details
            print("\n--- Author Details ---")
            author_id_input = prompt_input("Author ID (new_author_id) [Leave blank to auto-generate]", required=False)
            
            if not author_id_input:
                cur.execute("SELECT COALESCE(MAX(new_author_id), 0) + 1 FROM api_author")
                author_id = cur.fetchone()[0]
                print(f"Auto-generated Author ID: {author_id}")
                existing_author = None
            else:
                author_id = int(author_id_input)
                # Check if author already exists to pre-fill or warn
                cur.execute("SELECT name, birth_year, ethnicity, sex FROM api_author WHERE new_author_id = %s", (author_id,))
                existing_author = cur.fetchone()
            
            # Predefined choices for ethnicity and sex
            ethnicity_choices = ["bumiputera", "chinese", "indian", "others"]
            sex_choices = ["m", "f"]
            
            if existing_author:
                print(f"\nAuthor ID {author_id} already exists in the database.")
                print(f"Current details: Name='{existing_author[0]}', Birth Year={existing_author[1]}, Ethnicity='{existing_author[2]}', Sex='{existing_author[3]}'")
                proceed = prompt_input("Do you want to update this author? (y/n)", required=True).lower()
                if proceed != 'y':
                    print("Aborting author update.")
                    # We might still want to add history, so we don't exit entirely
                else:
                    name = prompt_input("Name", required=True, default=existing_author[0])
                    if name:
                        name = name.upper()
                    birth_year = prompt_input("Birth Year (YYYY)", required=False, type_func=int, default=existing_author[1])
                    ethnicity = prompt_choice("Ethnicity", choices=ethnicity_choices, required=False, default=existing_author[2])
                    sex = prompt_choice("Sex", choices=sex_choices, required=False, default=existing_author[3])
                    
                    cur.execute("""
                        UPDATE api_author 
                        SET name = %s, birth_year = %s, ethnicity = %s, sex = %s 
                        WHERE new_author_id = %s
                    """, (name, birth_year, ethnicity, sex, author_id))
                    print(f"Author {author_id} updated successfully.")
            else:
                name = prompt_input("Name", required=True)
                if name:
                    name = name.upper()
                birth_year = prompt_input("Birth Year (YYYY)", required=False, type_func=int)
                ethnicity = prompt_choice("Ethnicity", choices=ethnicity_choices, required=False)
                sex = prompt_choice("Sex", choices=sex_choices, required=False)
                
                cur.execute("""
                    INSERT INTO api_author (new_author_id, name, birth_year, ethnicity, sex) 
                    VALUES (%s, %s, %s, %s, %s)
                """, (author_id, name, birth_year, ethnicity, sex))
                print(f"Author {author_id} added successfully.")

            # 2. Prompt for AuthorHistory details
            print("\n--- Author History Details ---")
            add_history = prompt_input("Do you want to add an author history record? (y/n)", required=True).lower()
            
            if add_history == 'y':
                record_id_input = prompt_input("Record ID (Primary Key) [Leave blank to auto-generate]", required=False)
                
                if not record_id_input:
                    cur.execute("SELECT COALESCE(MAX(record_id), 0) + 1 FROM api_author_history")
                    record_id = cur.fetchone()[0]
                    print(f"Auto-generated Record ID: {record_id}")
                    history_exists = False
                else:
                    record_id = int(record_id_input)
                    # Check for existing history
                    cur.execute("SELECT 1 FROM api_author_history WHERE record_id = %s", (record_id,))
                    history_exists = cur.fetchone() is not None

                if history_exists:
                    print(f"Error: AuthorHistory with Record ID {record_id} already exists. Aborting history insertion.")
                else:
                    party = prompt_input("Party", required=False)
                    if party:
                        party = party.upper()
                    exec_posts = prompt_input("Executive Posts", required=False)
                    service_posts = prompt_input("Service Posts", required=False)
                    
                    # Look up area
                    area_id = lookup_area(conn)
                    
                    # Verify area exists if provided
                    area_exists = True
                    if area_id is not None:
                        cur.execute("SELECT 1 FROM api_area WHERE id = %s", (area_id,))
                        if not cur.fetchone():
                            print(f"Error: Area ID {area_id} does not exist in the database. Aborting history insertion.")
                            area_exists = False
                    
                    if area_exists:
                        start_date = prompt_input("Start Date (YYYY-MM-DD)", required=False)
                        end_date = prompt_input("End Date (YYYY-MM-DD)", required=False)
                        
                        cur.execute("""
                            INSERT INTO api_author_history (record_id, author_id, party, area_id, exec_posts, service_posts, start_date, end_date) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (record_id, author_id, party, area_id, exec_posts, service_posts, start_date, end_date))
                        print(f"Author History {record_id} added successfully.")
            
            # Commit the transaction
            conn.commit()
            print("\nAll changes committed to the database.")
            
    except Exception as e:
        conn.rollback()
        print(f"\nAn error occurred: {e}")
        print("All changes have been rolled back.")
    finally:
        conn.close()


def handle_s3_sync(s3_bucket, author_key, history_key):
    """Syncs authors and author histories from S3 to the database."""
    print("=== S3 Author Sync ===")
    conn = get_db_connection()
    
    # We will use the region from the environment, defaulting to ap-southeast-5
    aws_region = os.environ.get("AWS_REGION", "ap-southeast-5")
    s3_client = boto3.client("s3", region_name=aws_region)
    
    try:
        with conn.cursor() as cur:
            # 1. Sync Authors
            print(f"\n--- Syncing Authors from s3://{s3_bucket}/{author_key} ---")
            try:
                response = s3_client.get_object(Bucket=s3_bucket, Key=author_key)
                csv_content = response["Body"].read()
                df_author = pd.read_csv(io.BytesIO(csv_content))
                print(f"Loaded {len(df_author)} author records from S3.")
            except Exception as e:
                print(f"Failed to read author CSV from S3: {e}")
                sys.exit(1)
            
            # Ensure proper column names
            if "author_id" in df_author.columns:
                df_author.rename(columns={"author_id": "new_author_id"}, inplace=True)
                
            optional_cols_author = ["birth_year", "ethnicity", "sex"]
            for col in optional_cols_author:
                if col not in df_author.columns:
                    df_author[col] = None
            
            author_upsert_count = 0
            for _, row in df_author.iterrows():
                new_author_id = int(row["new_author_id"])
                name = row["name"]
                birth_year = None if pd.isna(row["birth_year"]) or row["birth_year"] == "" else int(row["birth_year"])
                ethnicity = None if pd.isna(row["ethnicity"]) or row["ethnicity"] == "" else row["ethnicity"]
                sex = None if pd.isna(row["sex"]) or row["sex"] == "" else row["sex"]
                
                cur.execute("""
                    INSERT INTO api_author (new_author_id, name, birth_year, ethnicity, sex)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (new_author_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        birth_year = EXCLUDED.birth_year,
                        ethnicity = EXCLUDED.ethnicity,
                        sex = EXCLUDED.sex
                """, (new_author_id, name, birth_year, ethnicity, sex))
                author_upsert_count += 1
            print(f"Upserted {author_upsert_count} authors.")

            # 2. Sync Author Histories
            if history_key:
                print(f"\n--- Syncing Author Histories from s3://{s3_bucket}/{history_key} ---")
                try:
                    response = s3_client.get_object(Bucket=s3_bucket, Key=history_key)
                    csv_content = response["Body"].read()
                    df_history = pd.read_csv(io.BytesIO(csv_content))
                    print(f"Loaded {len(df_history)} history records from S3.")
                except Exception as e:
                    print(f"Failed to read author history CSV from S3: {e}")
                    sys.exit(1)
                
                optional_cols_hist = ["party", "area_id", "exec_posts", "service_posts", "start_date", "end_date"]
                for col in optional_cols_hist:
                    if col not in df_history.columns:
                        df_history[col] = None

                history_upsert_count = 0
                for _, row in df_history.iterrows():
                    record_id_col = "record_id" if "record_id" in row else "history_id"
                    record_id = int(row[record_id_col])
                    author_id = int(row["author_id"]) if not pd.isna(row["author_id"]) else None
                    if not author_id:
                        continue # Cannot insert history without an author
                    
                    party = None if pd.isna(row["party"]) or row["party"] == "" else row["party"]
                    area_id_val = row["area_id"]
                    area_id = None if pd.isna(area_id_val) or area_id_val == "" else int(area_id_val)
                    exec_posts = None if pd.isna(row["exec_posts"]) or row["exec_posts"] == "" else row["exec_posts"]
                    service_posts = None if pd.isna(row["service_posts"]) or row["service_posts"] == "" else row["service_posts"]
                    start_date = None if pd.isna(row["start_date"]) or row["start_date"] == "" else row["start_date"]
                    end_date = None if pd.isna(row["end_date"]) or row["end_date"] == "" else row["end_date"]
                    
                    cur.execute("""
                        INSERT INTO api_author_history (record_id, author_id, party, area_id, exec_posts, service_posts, start_date, end_date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (record_id) DO UPDATE SET
                            author_id = EXCLUDED.author_id,
                            party = EXCLUDED.party,
                            area_id = EXCLUDED.area_id,
                            exec_posts = EXCLUDED.exec_posts,
                            service_posts = EXCLUDED.service_posts,
                            start_date = EXCLUDED.start_date,
                            end_date = EXCLUDED.end_date
                    """, (record_id, author_id, party, area_id, exec_posts, service_posts, start_date, end_date))
                    history_upsert_count += 1
                
                print(f"Upserted {history_upsert_count} author history records.")

            # Commit the transaction
            conn.commit()
            print("\nS3 Sync completed successfully.")

    except Exception as e:
        conn.rollback()
        print(f"\nAn error occurred during sync: {e}")
        print("All changes have been rolled back.")
    finally:
        conn.close()



def handle_local_csv():
    """Syncs authors and author histories from local CSV files defined in .env."""
    print("=== Local CSV Author Sync ===")

    author_csv_path = os.environ.get("LOCAL_AUTHOR_CSV")
    history_csv_path = os.environ.get("LOCAL_AUTHOR_HISTORY_CSV")

    if not author_csv_path:
        print("Error: LOCAL_AUTHOR_CSV environment variable is not set in .env.")
        sys.exit(1)

    assert author_csv_path is not None  # narrowed above
    if not os.path.isfile(author_csv_path):
        print(f"Error: Author CSV file not found at path: {author_csv_path}")
        sys.exit(1)

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            # 1. Sync Authors
            print(f"\n--- Syncing Authors from {author_csv_path} ---")
            try:
                df_author = pd.read_csv(author_csv_path)
                print(f"Loaded {len(df_author)} author records from local CSV.")
            except Exception as e:
                print(f"Failed to read author CSV: {e}")
                sys.exit(1)

            if "author_id" in df_author.columns:
                df_author.rename(columns={"author_id": "new_author_id"}, inplace=True)

            optional_cols_author = ["birth_year", "ethnicity", "sex"]
            for col in optional_cols_author:
                if col not in df_author.columns:
                    df_author[col] = None

            author_upsert_count = 0
            ethnicity_defaulted = 0
            for _, row in df_author.iterrows():
                new_author_id = int(row["new_author_id"])
                name = row["name"]
                birth_year = None if pd.isna(row["birth_year"]) or row["birth_year"] == "" else int(row["birth_year"])
                sex = None if pd.isna(row["sex"]) or row["sex"] == "" else row["sex"]

                # ethnicity is NOT NULL in the DB — default to 'others' if missing
                if pd.isna(row["ethnicity"]) or row["ethnicity"] == "":
                    ethnicity = "others"
                    ethnicity_defaulted += 1
                else:
                    ethnicity = row["ethnicity"]

                cur.execute("""
                    INSERT INTO api_author (new_author_id, name, birth_year, ethnicity, sex)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (new_author_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        birth_year = EXCLUDED.birth_year,
                        ethnicity = EXCLUDED.ethnicity,
                        sex = EXCLUDED.sex
                """, (new_author_id, name, birth_year, ethnicity, sex))
                author_upsert_count += 1

            if ethnicity_defaulted:
                print(f"  ⚠ {ethnicity_defaulted} row(s) had null ethnicity — defaulted to 'others'.")
            print(f"Upserted {author_upsert_count} authors.")

            # 2. Sync Author Histories (optional)
            if isinstance(history_csv_path, str):
                if not os.path.isfile(history_csv_path):
                    print(f"Warning: Author history CSV not found at path: {history_csv_path}. Skipping history sync.")
                else:
                    print(f"\n--- Syncing Author Histories from {history_csv_path} ---")
                    try:
                        df_history = pd.read_csv(history_csv_path)
                        print(f"Loaded {len(df_history)} history records from local CSV.")
                    except Exception as e:
                        print(f"Failed to read author history CSV: {e}")
                        sys.exit(1)

                    optional_cols_hist = ["party", "area_id", "exec_posts", "service_posts", "start_date", "end_date"]
                    for col in optional_cols_hist:
                        if col not in df_history.columns:
                            df_history[col] = None

                    history_upsert_count = 0
                    for _, row in df_history.iterrows():
                        record_id_col = "record_id" if "record_id" in row else "history_id"
                        record_id = int(row[record_id_col])
                        author_id = int(row["author_id"]) if not pd.isna(row["author_id"]) else None
                        if not author_id:
                            continue  # Cannot insert history without an author

                        party = None if pd.isna(row["party"]) or row["party"] == "" else row["party"]
                        area_id_val = row["area_id"]
                        area_id = None if pd.isna(area_id_val) or area_id_val == "" else int(area_id_val)
                        exec_posts = None if pd.isna(row["exec_posts"]) or row["exec_posts"] == "" else row["exec_posts"]
                        service_posts = None if pd.isna(row["service_posts"]) or row["service_posts"] == "" else row["service_posts"]
                        start_date = None if pd.isna(row["start_date"]) or row["start_date"] == "" else row["start_date"]
                        end_date = None if pd.isna(row["end_date"]) or row["end_date"] == "" else row["end_date"]

                        cur.execute("""
                            INSERT INTO api_author_history (record_id, author_id, party, area_id, exec_posts, service_posts, start_date, end_date)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (record_id) DO UPDATE SET
                                author_id = EXCLUDED.author_id,
                                party = EXCLUDED.party,
                                area_id = EXCLUDED.area_id,
                                exec_posts = EXCLUDED.exec_posts,
                                service_posts = EXCLUDED.service_posts,
                                start_date = EXCLUDED.start_date,
                                end_date = EXCLUDED.end_date
                        """, (record_id, author_id, party, area_id, exec_posts, service_posts, start_date, end_date))
                        history_upsert_count += 1

                    print(f"Upserted {history_upsert_count} author history records.")
            else:
                print("LOCAL_AUTHOR_HISTORY_CSV not set — skipping history sync.")

            conn.commit()
            print("\nLocal CSV sync completed successfully.")

    except Exception as e:
        conn.rollback()
        print(f"\nAn error occurred during sync: {e}")
        print("All changes have been rolled back.")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Manage authors in the Hansards database.")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Check if we were called without arguments or with valid commands
    
    # manual mode subparser
    parser_manual = subparsers.add_parser("manual", help="Add or update an author interactively.")
    
    # s3 mode subparser
    parser_sync = subparsers.add_parser("s3", help="Sync authors from S3.")
    parser_sync.add_argument("--bucket", type=str, default=os.getenv("S3_DATAPROC_BUCKET"), help="S3 bucket name")
    parser_sync.add_argument("--author-key", type=str, default=os.getenv("S3_AUTHOR_KEY", "canonical/author.csv"), help="S3 key for author.csv")
    parser_sync.add_argument("--history-key", type=str, default=os.getenv("S3_AUTHOR_HISTORY_KEY", "canonical/author_history.csv"), help="S3 key for author_history.csv (optional)")

    # local mode subparser
    subparsers.add_parser("local", help="Sync authors from local CSV files (paths set in .env).")
    
    args = parser.parse_args()
    
    # If no arguments provided, default to manual
    if len(sys.argv) == 1:
        handle_manual_entry()
    elif args.command == "manual":
        handle_manual_entry()
    elif args.command == "s3":
        handle_s3_sync(args.bucket, args.author_key, args.history_key)
    elif args.command == "local":
        handle_local_csv()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
