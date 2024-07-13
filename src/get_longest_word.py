"""To search for stitched sentences like 18102021"""

import os
import re


def find_longest_alphabetical_word(file_path):
    with open(file_path, 'r') as file:
        content = file.read()
        words = re.findall(r'\b[a-zA-Z]+\b', content)
        if words:
            longest_word = max(words, key=lambda word: (len(word), word))
            return longest_word
        else:
            return None


def search_and_log(start_directory):
    log_entries = []  # Store log entries in a list
    for foldername, subfolders, filenames in os.walk(start_directory):
        if 'plaintext.txt' in filenames:
            file_path = os.path.join(foldername, 'plaintext.txt')
            longest_word = find_longest_alphabetical_word(file_path)
            if longest_word:
                log_entries.append((file_path, longest_word))  # Add (file_path, longest_word) tuple to the list

    # Sort log entries by word length in descending order
    sorted_entries = sorted(log_entries, key=lambda entry: len(entry[1]), reverse=True)

    # Write sorted log entries to the log file
    log_file_path = 'dump/stitched.txt'
    with open(log_file_path, 'a') as log_file:
        for file_path, longest_word in sorted_entries:
            log_file.write(f'Found in {file_path}: {longest_word}\n')
            print(f'Found in {file_path}: {longest_word}')


# Example usage
search_and_log('parsed_pdf')
