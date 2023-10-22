import os
import re
import shutil

# Define the source directory
source_directory = "src_hansard"

# Create a regex pattern to extract year, month, and day from the filename
pattern = r"dn_(\d{4})_(\d{2})_(\d{2}).pdf"

# Iterate through files in the source directory
for filename in os.listdir(source_directory):
    # Check if the file matches the pattern
    match = re.match(pattern, filename)
    if match:
        year, month, day = match.groups()
        # Create the target directory (if not exists)
        target_directory = os.path.join(source_directory, year)
        os.makedirs(target_directory, exist_ok=True)
        # Move the file to the target directory
        shutil.move(os.path.join(source_directory, filename), os.path.join(target_directory, filename))
        # Rename the file
        new_filename = f"DN-{day}{month}{year}.pdf"
        os.rename(os.path.join(target_directory, filename), os.path.join(target_directory, new_filename))

# Optional: Print a message indicating the process is complete
print("Files reorganized and renamed successfully.")
