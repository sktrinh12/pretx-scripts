import os
# test python script to check for any exp id duplicates globally within the exp_ids folder

def find_duplicates_in_folder(folder_path):
    unique_numbers = set()
    duplicates = set()

    for filename in os.listdir(folder_path):
        if filename.endswith('.txt') and 'prod' in filename:
            file_path = os.path.join(folder_path, filename)
            
            with open(file_path, 'r') as file:
                content = file.read().strip()
            
            numbers = content.split(',')
            
            for number in numbers:
                if number in unique_numbers:
                    duplicates.add(number)
                else:
                    unique_numbers.add(number)

    if duplicates:
        print("Duplicates found across all files:", ", ".join(duplicates))
    else:
        print("No duplicates found across all files.")

find_duplicates_in_folder('exp_ids')
