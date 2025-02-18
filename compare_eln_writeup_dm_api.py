"""
The script automates the process of fetching experimental IDs from a Dotmatics API, processes them asynchronously, and performs comparisons between experiment write-ups using diff, SciBERT and TF-IDF models for text similarity.

Token Authentication:
    Authenticates with multiple Dotmatics systems using the provided credentials and retrieves access tokens.

Experiment ID Retrieval:
    Fetches a list of experiment IDs from the API endpoint for a specified domain and project.

Text Comparison:
    Compares write-ups using three methods:
        Diff: Executes a diff between the two writeups similar to git diff.
        SciBERT: Utilizes a pre-trained BERT model fine-tuned on scientific literature.
        TF-IDF: Applies vector-based similarity on word importance.

Asynchronous Processing:
    Uses Python’s asyncio to parallelize API calls and efficiently process a large number of experiments.
"""

import psycopg2
from os import getenv
from dotenv import load_dotenv
from urllib.parse import quote
import argparse
import aiohttp
import asyncio
import asyncpg
from difflib import unified_diff, SequenceMatcher
import json
import torch
from datetime import date, datetime
from transformers import AutoTokenizer, AutoModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


load_dotenv(override=True)
DM_USER = getenv("DM_USER")
DM_PASS = quote(getenv("DM_PASS"))
DM_PASS_ALT = quote(getenv("DM_PASS_ALT"))
SYS_NAMES = ["prelude-masks2", "prelude-masks"]
DS_IDS = {
    SYS_NAMES[0]: {"proj_id": 100000, "exp_ids": 1425, "summary": 1426},
    SYS_NAMES[1]: {"proj_id": 100000, "exp_ids": 1422, "summary": 1423},
}
BASE_URL = "dotmatics.net/browser/api"
EXPIRE = 1 * 60 * 60
DB_POOL = None
DB_CONFIG = {
    "dbname": getenv("DB_NAME"),
    "user": getenv("DB_USER"),
    "password": getenv("DB_PASS"),
    "host": getenv("DB_HOST"),
    "port": getenv("DB_PORT"),
}
MODEL_NAME = "allenai/scibert_scivocab_uncased"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModel.from_pretrained(MODEL_NAME)
exp_id_list = []


async def init_db(max_size: int):
    """
    Initializes the database connection pool.
    Args:
        max_size (int): Max number of connections in the pool.
    """
    global DB_POOL
    DB_POOL = await asyncpg.create_pool(
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["dbname"],
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        min_size=1,
        max_size=max_size,
    )


def create_tables(delete=False, cont=True):
    """
    create or drop psql db tables. The two tables are related.
    ELN_WRITEUP_COMPARISON contains calculated similarity values from a diff,
    scibert cosine similarity and tf-idf cosine similarity

    """
    global exp_id_list
    connection = psycopg2.connect(**DB_CONFIG)
    cursor = connection.cursor()
    if delete:
        cursor.execute("DROP TABLE IF EXISTS ELN_WRITEUP_API_EXTRACT CASCADE")
        cursor.execute("DROP TABLE IF EXISTS ELN_WRITEUP_COMPARISON CASCADE")
    else:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ELN_WRITEUP_API_EXTRACT (
                exp_id VARCHAR(7) NOT NULL,
                system_name VARCHAR(100) NOT NULL,
                write_up TEXT NOT NULL,
                summary_data TEXT NOT NULL,
                analysis_date DATE NOT NULL,
                PRIMARY KEY(exp_id, system_name, analysis_date)
            );
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ELN_WRITEUP_COMPARISON (
                exp_id VARCHAR NOT NULL,
                system_name_1 VARCHAR NOT NULL,
                system_name_2 VARCHAR NOT NULL,
                diff TEXT,
                match_percentage NUMERIC,
                is_match BOOLEAN,
                scibert_score NUMERIC,
                tfidf_score NUMERIC,
                analysis_date DATE NOT NULL,
                PRIMARY KEY (exp_id, system_name_1, system_name_2, analysis_date),
                FOREIGN KEY (exp_id, system_name_1, analysis_date) REFERENCES eln_writeup_api_extract (exp_id, system_name, analysis_date)
            );
        """
        )
    if cont and not delete:
        cursor.execute(
            "SELECT distinct exp_id from ELN_WRITEUP_API_EXTRACT where analysis_date NOT IN ('2025-01-30', '2025-02-05')"
        )
        stored_exp_ids = cursor.fetchall()
        exp_id_list = [row[0] for row in stored_exp_ids]
        print(exp_id_list[:100])
        print(
            f"showing up to first 100 records of {len(exp_id_list)}, from PostgreSQL database fetched..."
        )

    connection.commit()
    cursor.close()
    connection.close()


async def fetch_get(url, headers):
    """
    async method to fetch or get data to DTX api

    Args:
        url (str): url address of the DTX server
        headers (dict): headers that contain the token
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            return await response.json()


async def fetch_post(url, headers, data):
    """
    async method to post data to DTX api

    Args:
        url (str): url address of the DTX server
        headers (dict): headers that contain the token
        data (dict): JSON data to send in the POST request
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=data) as response:
            return await response.json()


async def save_writeup_to_db(exp_id, system_name, writeup, summary, analysis_date):
    """
    Saves writeup data to the database.

    Args:
        exp_id (str): Experiment ID.
        system_name (str): System name.
        writeup (str): The writeup content.
        summary (dict): Summary data.
        analysis_date (date): Date analysed.
    """
    async with DB_POOL.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO ELN_WRITEUP_API_EXTRACT (exp_id, system_name, write_up, summary_data, analysis_date)
            VALUES ($1, $2, $3, $4, $5)
            """,
            exp_id,
            system_name,
            writeup,
            summary,
            analysis_date,
        )


async def save_compr_to_db(
    exp_id,
    system_name_1,
    system_name_2,
    diff,
    match_percentage,
    is_match,
    scibert_score,
    tfidf_score,
    analysis_date,
):
    """
    Saves comparison data to the database.

    Args:
        exp_id (str): Experiment ID.
        system_name_1 (str): First system name.
        system_name_2 (str): Second system name.
        diff (str): Diff content.
        match_percentage (float): Match percentage.
        is_match (bool): Whether the match percentage meets the threshold.
        scibertt_score (float): scibert model cosine similarity score.
        tfidf_score (float): tf-idf model cosine similarity score.
        analysis_date (date): Date analysed.
    """
    async with DB_POOL.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO ELN_WRITEUP_COMPARISON (exp_id, system_name_1, system_name_2, diff, match_percentage, is_match, scibert_score, tfidf_score, analysis_date)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            exp_id,
            system_name_1,
            system_name_2,
            diff,
            match_percentage,
            is_match,
            scibert_score,
            tfidf_score,
            analysis_date,
        )


async def update_compr(
    exp_id,
    system_name_1,
    system_name_2,
    diff,
    match_percentage,
    is_match,
    scibert_score,
    tfidf_score,
    analysis_date,
):
    """
    Updates comparison data to the database.

    Args:
        exp_id (str): Experiment ID.
        system_name_1 (str): First system name.
        system_name_2 (str): Second system name.
        diff (str): Diff content.
        match_percentage (float): Match percentage.
        is_match (bool): Whether the match percentage meets the threshold.
        scibert_score (float): scibert model cosine similarity score.
        tfidf_score (float): tf-idf model cosine similarity score.
        analysis_date (date): Date analysed.
    """
    async with DB_POOL.acquire() as conn:
        await conn.execute(
            """
            UPDATE ELN_WRITEUP_COMPARISON
            SET diff =  $4,
            match_percentage = $5,
            is_match = $6,
            scibert_score = $7,
            tfidf_score = $8
            WHERE
            exp_id = $1
            AND system_name_1 = $2
            AND system_name_2 = $3
            AND analysis_date = $9
            """,
            exp_id,
            system_name_1,
            system_name_2,
            diff,
            match_percentage,
            is_match,
            scibert_score,
            tfidf_score,
            analysis_date,
        )


async def fetch_write_up(exp_id: str, system_name: str, analysis_date: date):
    """Fetch the write_up from eln_writeup_api_extract based on exp_id and system_name.

    Args:
        exp_id (str): Experiment ID.
        system_name (str): System name.
        analysis_date (date): Date analysed.
    """
    async with DB_POOL.acquire() as conn:
        return await conn.fetchval(
            """
            SELECT write_up
            FROM eln_writeup_api_extract
            WHERE exp_id = $1 AND system_name = $2
            AND analysis_date = $3
            """,
            exp_id,
            system_name,
            analysis_date,
        )


def get_embedding(text):
    """
    Generate embedding for a given text using SciBERT.
    """
    inputs = tokenizer(
        text, return_tensors="pt", truncation=True, padding=True, max_length=512
    )
    with torch.no_grad():
        outputs = model(**inputs)
        embedding = outputs.last_hidden_state[:, 0, :]  # CLS token embedding
    return embedding


def scibert_compare(text1, text2):
    """
    Compare two texts using scibert model followed by cosine similarity.

    Pre-trained BERT: Good for general understanding including scientific texts.
    SciBERT is trained on papers from the corpus of semanticscholar.org.
    Corpus size is 1.14M papers, 3.1B tokens
    """
    try:
        embedding1 = get_embedding(text1)
        embedding2 = get_embedding(text2)
        similarity = cosine_similarity(embedding1.numpy(), embedding2.numpy())
        return similarity[0][0]
    except Exception:
        return 0


def tfidf_compare(text1, text2):
    """
    Compare two texts using TF-IDF and cosine similarity.

    TF-IDF: Measures word importance in documents.
    Matrix of Vectors: Represents documents in a high-dimensional space.
    Cosine Similarity: Measures similarity between these vectors.
    """
    try:
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform([text1, text2])
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
        return similarity[0][0]
    except Exception:
        return 0


# async def process_exp_id(exp_id_chunk, semaphore, analysis_date_1, analysis_date_2):
async def process_exp_id(
    token_dct, exp_id_chunk, semaphore, analysis_date_1, analysis_date_2
):
    """
    Processes an individual experiment ID by fetching data, computing differences,
    and saving to the database.

    Args:
        token_dct (dict): Dictionary of tokens for authentication.
        exp_id_chunk (list): List of experiment ids as 6-digit numerals.
        semaphore (semphore): The semaphore object that is based on limited concurrent tasks.
        analysis_date_1 (date): First date analysed.
        analysis_date_2 (date): Second date analysed, as comparator.
    """

    async with semaphore:

        # first request summary data since using batch api (post request)
        sdata = {}

        # only fetch from production
        for sname in [SYS_NAMES[0]]:
            exp_summary_endpoint = f"https://{sname}.{BASE_URL}/data/{DM_USER}/{DS_IDS[sname]['proj_id']}/{DS_IDS[sname]["summary"]}"
            # print(f"Requesting summary data: {exp_summary_endpoint}")
            headers = {
                "Authorization": f"Dotmatics {token_dct[sname]}",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            data = {"data": json.dumps(exp_id_chunk)}
            summary_data = await fetch_post(exp_summary_endpoint, headers, data)
            for exp_id, exp_details in summary_data.items():
                primary = exp_details["primary"]
                ds_summary = exp_details["dataSources"][str(DS_IDS[sname]["summary"])][
                    "1"
                ]
                sdata.setdefault(sname, {})[primary] = json.dumps(ds_summary)

        # second request writeup data for single exp_id using get request
        for exp_id in exp_id_chunk:
            compr_data = {}

            # only fetch from production
            for sname in [SYS_NAMES[0]]:
                writeup_url_endpoint = f"https://{sname}.{BASE_URL}/studies/experiment/{exp_id}/writeup/{{includeHtml}}"
                headers = {"Authorization": f"Dotmatics {token_dct[sname]}"}
                writeup_data = await fetch_get(writeup_url_endpoint, headers)
                compr_data[sname] = {"writeup": writeup_data}

                await save_writeup_to_db(
                    exp_id, sname, writeup_data, sdata[sname][exp_id], analysis_date_1
                )

            writeup1 = compr_data[SYS_NAMES[0]]["writeup"]
            # writeup2 = compr_data[SYS_NAMES[2]]["writeup"]

            # for exp_id in exp_id_chunk:
            # writeup1 = await fetch_write_up(exp_id, SYS_NAMES[1], analysis_date_1)
            writeup2 = await fetch_write_up(exp_id, SYS_NAMES[2], analysis_date_2)

            diff = "\n".join(
                unified_diff(writeup1.splitlines(), writeup2.splitlines(), lineterm="")
            )
            matcher = SequenceMatcher(None, writeup1, writeup2)
            match_percentage = matcher.ratio() * 100
            is_match = match_percentage >= 97

            scibert_score = float(scibert_compare(writeup1, writeup2))
            tfidf_score = float(tfidf_compare(writeup1, writeup2))

            # await update_compr(
            #     exp_id,
            #     SYS_NAMES[1],
            #     SYS_NAMES[2],
            #     diff,
            #     match_percentage,
            #     is_match,
            #     scibert_score,
            #     tfidf_score,
            #     analysis_date_1,
            # )

            await save_compr_to_db(
                exp_id,
                SYS_NAMES[0],
                SYS_NAMES[2],
                diff,
                match_percentage,
                is_match,
                scibert_score,
                tfidf_score,
                analysis_date_1,
            )

            await asyncio.sleep(0.1)


async def main(limit: int, max_size: int, cardinal: int):
    """
    Main function to handle the asynchronous logic for fetching, comparing,
    and saving data.

    Args:
        limit (int): Limit the number of experiment ids fetched
        max_size (int): Max number of connections in the pool
        cardinal (int): Max number of concurrent asyncio tasks and semaphores
    """
    global exp_id_list 
    await init_db(max_size)
    semaphore = asyncio.Semaphore(cardinal)
    chunk_size = cardinal
    tasks = []
    analysis_date_1 = date.today()
    analysis_date_2 = datetime.strptime("2025-01-30", "%Y-%m-%d").date()

    # get the prod-masks2 clone domain exp ids bc DTX just applied bug-fix 2025-02-17
    DOMAIN = SYS_NAMES[1]
    token_dct = {}

    for sname in SYS_NAMES:
        token_endpoint = f"https://{sname}.{BASE_URL}/authenticate/requestToken?isid={DM_USER}&password={DM_PASS_ALT if sname.endswith('8251') else DM_PASS}&expiration={EXPIRE}"
        token_dct[sname] = await fetch_get(token_endpoint, {})

    print("Tokens fetched successfully.")

    exp_id_query_endpoint = f"query/{DM_USER}/{DS_IDS[DOMAIN]['proj_id']}/{DS_IDS[DOMAIN]['exp_ids']}/EXPERIMENT_ID/greaterthan/1?limit={limit}"
    url = f"https://{DOMAIN}.{BASE_URL}/{exp_id_query_endpoint}"
    headers = {"Authorization": f"Dotmatics {token_dct[DOMAIN]}"}
    print(f"Fetching experiment IDs from: {url}")
    exp_id_list_api = await fetch_get(url, headers)
    exp_id_list_api = [
        exp_id for exp_id in exp_id_list_api["ids"] if exp_id not in exp_id_list
    ]
    # print(exp_id_list_api)

    # priority for CRO affinity
    # async with DB_POOL.acquire() as conn:
    #     exp_id_list = await conn.fetch(
    #         """
    #         SELECT exp_id
    #         from prioritized_experiments
    #         """
    #     )

    rev_exp_id_list = list(reversed(exp_id_list_api))
    # rev_exp_id_list = [str(record["exp_id"]) for record in exp_id_list]

    # release from memory for GC
    del exp_id_list
    print("release 'exp_id_list' from memory...")

    print(f"{len(rev_exp_id_list)} experiment IDs to process...")
    print()
    print("showing up to first 200 experiment ids fetched...")
    print(rev_exp_id_list[:200])
    print()
    input("Press any key to continue...")
    for i in range(0, len(rev_exp_id_list), chunk_size):
        chunk = rev_exp_id_list[i : i + chunk_size]
        print(
            f"Queuing task for exp_id: {', '.join(chunk)} ({i + 1}/{len(rev_exp_id_list)})"
        )
        tasks.append(
            process_exp_id(
                token_dct,
                chunk,
                semaphore,
                analysis_date_1,
                analysis_date_2,
            )
        )
        # tasks.append(process_exp_id(chunk, semaphore, analysis_date_1, analysis_date_2))

        print(f"Asyncio processing {chunk_size} experiment IDs...")
        await asyncio.gather(*tasks)
        print("All Asyncio tasks completed")
        tasks.clear()

    await DB_POOL.close()
    print("Database connection pool closed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Call Dotmatics API to fetch writeup text and analyse for similarity"
    )
    parser.add_argument(
        "-d",
        "--delete",
        action="store_true",
        help="Specify whether to delete the table in the PostgreSQL database. If not provided, defaults to create (False).",
    )
    parser.add_argument(
        "-l",
        "--limit",
        default=1000,
        type=int,
        help=f"Specify the limit of experiment ids to fetch; must be integer number.",
    )
    parser.add_argument(
        "-m",
        "--max_size",
        default=25,
        type=int,
        help=f"Specify the max number of connections for db connection pool; must be integer number.",
    )
    parser.add_argument(
        "-s",
        "--semaphore",
        default=25,
        type=int,
        help=f"Specify the max number of semaphore connections; must be integer number.",
    )
    parser.add_argument(
        "-c",
        "--continue",
        dest="continue_flag",
        action="store_false",
        help="Specify whether to continue from where left off from the PostgreSQL database. If not provided, defaults to continue (True).",
    )
    args = parser.parse_args()
    create_tables(delete=args.delete, cont=args.continue_flag)
    if not args.delete:
        asyncio.run(main(args.limit, int(args.max_size), int(args.semaphore)))
