import boto3
import os
from urllib.parse import unquote_plus
import re

# Initialize a session using Amazon S3
s3 = boto3.client('s3', region_name='ap-southeast-1')

# Create a regex pattern to extract year, month, and day from the filename
pattern = re.compile(r"dr_(\d{4})_(\d{2})_(\d{2})\.pdf")


def download_files(bucket_name, prefix):
    # Create a paginator to handle pagination
    paginator = s3.get_paginator('list_objects_v2')

    # Iterate through pages of objects
    for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
        for obj in page.get('Contents', []):
            # Get the file name
            file_name = unquote_plus(obj['Key'])

            # Extract the year, month, and day from the file name
            match = pattern.match(file_name.split('/')[1])
            assert match
            year, month, day = match.groups()
            if year != '2023':
                continue
            formatted_date = f"{day}{month}{year}"

            # Create a directory for the year within src_hansard if it doesn't exist
            os.makedirs(os.path.join('src_hansard', year), exist_ok=True)

            # Define the local file path within src_hansard
            local_file_path = os.path.join('src_hansard', year, os.path.basename(file_name))
            new_file_path = os.path.join('src_hansard', year, f"DR-{formatted_date}.pdf")

            # Check if the file already exists
            if not os.path.exists(new_file_path):
                print(f"Downloading file {file_name}...")
                # Download the file if it doesn't exist
                s3.download_file(bucket_name, file_name, local_file_path)
                print(f"File {local_file_path} downloaded successfully.")
                # Rename the file to the desired format
                os.rename(local_file_path, new_file_path)
                print(f"File {new_file_path} renamed successfully.")
            else:
                print(f"File {new_file_path} already exists. Skipping.")


# Define the bucket name and prefix
bucket_name = 'downloads.parlimen.gov.my'
prefix = 'dewanrakyat/'

# Call the function to download the files
download_files(bucket_name, prefix)
