from os import getenv
from datetime import datetime
import psycopg2
import argparse
from dotenv import load_dotenv

load_dotenv(override=True)
spaces_index = 5
spaces_exp_id = 8
spaces_write_up = 30
spaces_summ = 35
spaces_metric = 10

table_header = (
    f"{'Index':<{spaces_index}} "
    f"{'Exp ID':<{spaces_exp_id}} "
    f"{'Sys':<{spaces_metric+3}} "
    f"{'Date':<{spaces_metric+3}}"
    f"{'Write Up':<{spaces_write_up}} "
    f"{'Match %':<{spaces_metric}} "
    f"{'Scibert':<{spaces_metric}} "
    f"{'TF-IDF':<{spaces_metric}} "
)
separator = "-" * len(table_header)


def fetch_writeups(exp_ids):
    query = f"""
    SELECT
    e.exp_id,
    e.system_name,
    e.analysis_date,
    e.write_up,
    c.match_percentage,
    c.scibert_score,
    c.tfidf_score
FROM
    ELN_WRITEUP_COMPARISON c
INNER JOIN
    ELN_WRITEUP_API_EXTRACT e
    ON c.exp_id = e.exp_id 
    AND c.system_name_1 = e.system_name
    AND c.analysis_date = e.analysis_date
WHERE e.exp_id = ANY(%s)
GROUP BY
    e.exp_id,
    e.system_name,
    e.write_up,
    c.match_percentage,
    c.scibert_score,
    c.tfidf_score,
    e.analysis_date
ORDER BY
    e.exp_id,
    e.analysis_date;
"""

    connection = psycopg2.connect(
        dbname=getenv("DB_NAME"),
        user=getenv("DB_USER"),
        password=getenv("DB_PASS"),
        host=getenv("DB_HOST"),
    )
    cursor = connection.cursor()
    cursor.execute(query, (exp_ids,),)
    results = cursor.fetchall()
    cursor.close()
    connection.close()

    return results


def print_results(results):
    print(table_header)
    print(separator)

    for index, (
        exp_id,
        system_name,
        analysis_date,
        write_up,
        match_percentage,
        scibert_score,
        tfidf_score,
    ) in enumerate(results, start=1):
        formatted_row = (
            f"{index:<{spaces_index}} "
            f"{exp_id:<{spaces_exp_id}} "
            f"{system_name:<{spaces_metric+3}} "
            f"{analysis_date.strftime("%Y-%m-%d"):<{spaces_metric+3}}"
            f"{write_up[:spaces_write_up]:<{spaces_write_up}} "
            f"{match_percentage:<{spaces_metric}.2f} "
            f"{scibert_score:<{spaces_metric}.2f} "
            f"{tfidf_score:<{spaces_metric}.2f} "
        )
        print(formatted_row)
    print("\n")
    print("Full Write-Up Texts:")
    print("=" * 50)
    for exp_id, system_name, analysis_date, write_up, _, _, _ in results:
        print(f"Exp ID: {exp_id}")
        print(f"System Name: {system_name}")
        print(f"Analysis Date: {analysis_date.strftime('%Y-%m-%d')}")
        print(f"Write-Up:\n{write_up}\n")
        print("-" * 50)

def valid_date(date_str):
    """
    Validate that the date string is in the format YYYY-MM-DD.
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date format: {date_str}. Expected format: YYYY-MM-DD"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch and display writeups for given experiment IDs."
    )
    parser.add_argument(
        "-e",
        "--exp_ids",
        nargs="+",
        required=True,
        help="List of experiment IDs to fetch writeups for.",
    )
    parser.add_argument(
        "-d",
        "--analysis_date",
        required=True,
        type=valid_date,
        help="Analysis date in format YYYY-MM-DD",
    )
    args = parser.parse_args()
    print()
    writeups = fetch_writeups(args.exp_ids)
    print_results(writeups)
