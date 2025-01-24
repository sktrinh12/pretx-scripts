import aiohttp
import asyncio
import asyncpg
import psycopg2
from os import getenv
from dotenv import load_dotenv
from urllib.parse import quote
from difflib import unified_diff, SequenceMatcher
import json
import argparse
import pandas as pd
import torch
from transformers import AutoTokenizer, AutoModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


load_dotenv(override=True)
DM_USER = getenv("DM_USER")
DM_PASS = quote(getenv("DM_PASS"))
DM_PASS_ALT = quote(getenv("DM_PASS_ALT"))
SYS_NAMES = ["prelude", "prelude-masks", "prelude-prod-sdpo-8251"]
DS_IDS = {
    "prelude": {"proj_id": 100000, "exp_ids": 1425, "summary": 1426},
    "prelude-masks": {"proj_id": 100000, "exp_ids": 1422, "summary": 1423},
    "prelude-prod-sdpo-8251": {"proj_id": 98000, "exp_ids": 1403, "summary": 1404},
}
BASE_URL = "dotmatics.net/browser/api"
EXPIRE = 1*60*60
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


def create_tables(delete=False):
    """
    create or drop psql db tables. The two tables are related. ELN_WRITEUP_COMPARISON contains calculated similarity values from a diff, scibert cosine similarity and tf-idf cosine similarity

    """
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
                PRIMARY KEY(exp_id, system_name)
            );
        """
        )
        cursor.execute(
            """
            CREATE TABLE ELN_WRITEUP_COMPARISON (
                exp_id VARCHAR NOT NULL,
                system_name_1 VARCHAR NOT NULL,
                system_name_2 VARCHAR NOT NULL,
                diff TEXT,
                match_percentage NUMERIC,
                is_match BOOLEAN,
                scibert_score NUMERIC,
                tfidf_score NUMERIC,
                PRIMARY KEY (exp_id, system_name_1, system_name_2),
                FOREIGN KEY (exp_id, system_name_1) REFERENCES eln_writeup_api_extract (exp_id, system_name),
                FOREIGN KEY (exp_id, system_name_2) REFERENCES eln_writeup_api_extract (exp_id, system_name)
            ); 
        """
        )
    connection.commit()
    cursor.close()
    connection.close()


async def fetch(url, headers):
    """
    async method to fetch or get data from DTX api

    Args:
        url (str): url address of the DTX server
        headers (dict): headers that contain the token
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            return await response.json()


async def save_writeup_to_db(exp_id, system_name, writeup, summary):
    """
    Saves writeup data to the database.

    Args:
        exp_id (str): Experiment ID.
        system_name (str): System name.
        writeup (str): The writeup content.
        summary (dict): Summary data.
    """
    async with DB_POOL.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO ELN_WRITEUP_API_EXTRACT (exp_id, system_name, write_up, summary_data)
            VALUES ($1, $2, $3, $4)
            """,
            exp_id,
            system_name,
            writeup,
            summary,
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
    """
    async with DB_POOL.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO ELN_WRITEUP_COMPARISON (exp_id, system_name_1, system_name_2, diff, match_percentage, is_match, scibert_score, tfidf_score)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            exp_id,
            system_name_1,
            system_name_2,
            diff,
            match_percentage,
            is_match,
            scibert_score,
            tfidf_score,
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


async def process_exp_id(exp_id, token_dct, semaphore):
    """
    Processes an individual experiment ID by fetching data, computing differences,
    and saving to the database.

    Args:
        exp_id (str): The experiment ID.
        token_dct (dict): Dictionary of tokens for authentication.
    """
    async with semaphore:
        compr_data = {}
        # exclude prod for this first test 2025-24-01
        for sname in SYS_NAMES[1:]:
            writeup_url_endpoint = f"https://{sname}.{BASE_URL}/studies/experiment/{exp_id}/writeup/{{includeHtml}}"
            headers = {"Authorization": f"Dotmatics {token_dct[sname]}"}
            writeup_data = await fetch(writeup_url_endpoint, headers)
            compr_data[sname] = {"writeup": writeup_data}

            dsid_string = "{0}_PROTOCOL,{0}_PROTOCOL_ID,{0}_ISID,{0}_CREATED_DATE".format(
                DS_IDS[sname]["summary"]
            )
            exp_summary_endpoint = f"https://{sname}.{BASE_URL}/data/{DM_USER}/{DS_IDS[sname]['proj_id']}/{dsid_string}/{exp_id}"
            summary_data = await fetch(exp_summary_endpoint, headers)
            compr_data[sname]["summary"] = json.dumps(summary_data)

            await save_writeup_to_db(exp_id, sname, writeup_data, json.dumps(summary_data))

        writeup1 = compr_data[SYS_NAMES[1]]["writeup"]
        writeup2 = compr_data[SYS_NAMES[2]]["writeup"]
        diff = "\n".join(
            unified_diff(writeup1.splitlines(), writeup2.splitlines(), lineterm="")
        )
        matcher = SequenceMatcher(None, writeup1, writeup2)
        match_percentage = matcher.ratio() * 100
        is_match = match_percentage >= 95

        scibert_score = float(scibert_compare(writeup1, writeup2))
        tfidf_score = float(tfidf_compare(writeup1, writeup2))

        await save_compr_to_db(
            exp_id,
            SYS_NAMES[1],
            SYS_NAMES[2],
            diff,
            match_percentage,
            is_match,
            scibert_score,
            tfidf_score,
        )


async def main(limit: int, max_size: int, cardinal: int):
    """
    Main function to handle the asynchronous logic for fetching, comparing,
    and saving data.

    Args:
        limit (int): Limit the number of experiment ids fetched
        max_size (int): Max number of connections in the pool
    """
    await init_db(max_size)
    semaphore = asyncio.Semaphore(cardinal)
    chunk_size = cardinal
    tasks = []
    # get the prod-sdpo-8251 domain exp ids bc from 2024-AUG
    # has only subset of exp ids from prod
    DOMAIN = SYS_NAMES[2]
    token_dct = {}
    # exclude prod for this first test 2025-24-01
    for sname in SYS_NAMES[1:]:
        token_endpoint = f"https://{sname}.{BASE_URL}/authenticate/requestToken?isid={DM_USER}&password={DM_PASS_ALT if sname.endswith('8251') else DM_PASS}&expiration={EXPIRE}"
        token_dct[sname] = await fetch(token_endpoint, {})
    print("Tokens fetched successfully.")

    exp_id_query_endpoint = f"query/{DM_USER}/{DS_IDS[DOMAIN]['proj_id']}/{DS_IDS[DOMAIN]['exp_ids']}/EXPERIMENT_ID/greaterthan/1?limit={limit}"
    url = f"https://{DOMAIN}.{BASE_URL}/{exp_id_query_endpoint}"
    headers = {"Authorization": f"Dotmatics {token_dct[DOMAIN]}"}
    print(f"Fetching experiment IDs from: {url}")
    exp_id_list = await fetch(url, headers)
    print(exp_id_list)
    rev_exp_id_list = list(reversed(exp_id_list["ids"]))

    print(f"Found {len(rev_exp_id_list)} experiment IDs to process.")
    print()
    input("Press any key to continue...")
    for i in range(0, len(rev_exp_id_list), chunk_size):
        chunk = rev_exp_id_list[i:i+chunk_size]
        for exp_id in chunk:
            print(f"Queuing task for exp_id: {exp_id} ({i + 1}/{len(rev_exp_id_list)})")
            tasks.append(process_exp_id(exp_id, token_dct, semaphore))

        print("Asyncio processing all experiment IDs...")
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
        default=10,
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
    args = parser.parse_args()
    limit = args.limit
    create_tables(delete=args.delete)
    if not args.delete:
        asyncio.run(main(limit, int(args.max_size), int(args.semaphore)))
