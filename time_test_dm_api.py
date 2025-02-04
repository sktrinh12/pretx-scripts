from dotenv import load_dotenv
import requests
import time
import csv
from os import getenv
from urllib.parse import quote

load_dotenv()
DM_USER = getenv("DM_USER")
DM_PASS = getenv("DM_PASS_ALT")
browser_url = "https://prelude-prod-sdpo-8251.dotmatics.net/browser/api"

script_start_time = time.time()
token_endpoint = f"{browser_url}/authenticate/requestToken?expiration=380"
url = token_endpoint
response = requests.get(url, auth=(DM_USER, DM_PASS)).json()
print(response)
token = response

# Use the token to interact with other API endpoints
exp_id_query_endpoint = "query/preludeadmin/98000/1403/EXPERIMENT_ID/greaterthan/1?limit=100000"
url = f"{browser_url}/{exp_id_query_endpoint}"
headers={"Authorization": f"Dotmatics {token}"}
response = requests.get(url, headers=headers)
exp_id_list = response.json()["ids"]

print(exp_id_list[:150])
csv_filename = "dm_api_fetch_times.csv"
with open(csv_filename, "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Index", "Experiment ID", "Fetch Time (seconds)"])  # CSV header

for i, exp_id in enumerate(reversed(list(exp_id_list))):
    iteration_start_time = time.time() 
    writeup_url_endpoint = f"{browser_url}/studies/experiment/{exp_id}/writeup/{{includeHtml}}"
    response = requests.get(writeup_url_endpoint, headers={"Authorization": f"Dotmatics {token}"})
    eln_writeup = response.json()
    # if type(eln_writeup) is str and "?" in eln_writeup:
        # print(exp_id)
        # print(eln_writeup)

        exp_summary_endpoint = f"{browser_url}/data/testadmin/98000/1404_PROTOCOL,1404_PROTOCOL_ID,1404_ISID,1404_CREATED_DATE/{exp_id}"
        response = requests.get(exp_summary_endpoint, headers={"Authorization": f"Dotmatics {token}"})
        # print(response.json())

    iteration_end_time = time.time()  # End timing for this iteration
    # print(f"{exp_id} took {iteration_end_time - iteration_start_time:.4f} seconds")
    with open(csv_filename, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([index, exp_id, f"{fetch_time:.4f}"])
        csvfile.flush()

script_end_time = time.time()
print(f"Total script execution time: {script_end_time - script_start_time:.4f} seconds")
