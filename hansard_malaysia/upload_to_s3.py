import boto3
import os

IGNORED_FILES = ['.DS_Store', '.gitignore']
IGNORED_FOLDERS = ['archive_14th_parliament_4th_session']

def upload_files_to_s3(folder_path, bucket_name, destination_folder):
    # Initialize the S3 client
    s3 = boto3.client('s3')

    # Iterate through files in the folder
    for root, dirs, files in os.walk(folder_path):
        # Remove ignored folders from the iteration
        dirs[:] = [d for d in dirs if d not in IGNORED_FOLDERS]

        for file in files:
            file_path = os.path.join(root, file)

            # Skip files in the IGNORED_FILES list
            if file in IGNORED_FILES:
                continue

            # Generate the S3 object key (path within the bucket)
            relative_path = os.path.relpath(file_path, folder_path)
            s3_key = os.path.join(destination_folder, relative_path)

            try:
                # Upload the file to S3
                s3.upload_file(file_path, bucket_name, s3_key)

                # Print success message
                print(f"Uploaded '{file_path}' to '{bucket_name}/{s3_key}'")
            except Exception as e:
                # Handle any errors that might occur during the upload
                print(f"Error uploading '{file_path}' to S3: {e}")

if __name__ == "__main__":
    folder_path = "analysis_hansard"
    bucket_name = "dgmy-private-hansards"
    destination_folder = "processed"  # Specify the desired folder inside the bucket

