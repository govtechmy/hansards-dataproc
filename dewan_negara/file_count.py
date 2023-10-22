import os

# Specify the directory path where you want to count files
directory_path = 'src_hansard'

# Initialize a dictionary to store folder names as keys and file counts as values
folder_counts = {}

# Iterate through the directory
for folder_name in os.listdir(directory_path):
    # Check if the folder name is a number between 2008 and 2023
    if folder_name.isdigit() and 2008 <= int(folder_name) <= 2023:
        folder_path = os.path.join(directory_path, folder_name)
        # Count the files in the folder
        file_count = len([f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))])
        # Store the folder name and file count in the dictionary
        folder_counts[folder_name] = file_count

# Output the counts for each folder
for folder_name, file_count in folder_counts.items():
    print(f'Folder {folder_name}: {file_count} files')

# If you want to save the counts to a file, you can use the following code
# with open('file_counts.txt', 'w') as file:
#     for folder_name, file_count in folder_counts.items():
#         file.write(f'Folder {folder_name}: {file_count} files\n')
