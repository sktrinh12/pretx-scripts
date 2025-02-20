from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import traceback
import psycopg2
from os import getenv, path, getcwd, pardir
import argparse
from datetime import datetime
from time import sleep
from dotenv import load_dotenv
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from contextlib import contextmanager
from ml_modules import scibert_compare, tfidf_compare
from difflib import unified_diff, SequenceMatcher
from bs4 import BeautifulSoup

load_dotenv(override=True)
dm_user = getenv("DM_USER")
dm_pass = getenv("DM_PASS")
date_formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]
timestamp = datetime.now().strftime("%Y-%m-%d")
parent_dir = path.abspath(path.join(getcwd(), pardir))
log_filename = path.join(parent_dir, f"writeup_scrape_{timestamp}.log")
analysis_date = datetime.today()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_filename), logging.StreamHandler()],
)


@contextmanager
def get_db_connection():
    """Context manager for database connection."""
    connection = None
    try:
        connection = psycopg2.connect(**DB_CONFIG)
        yield connection
    except Exception as e:
        logging.error(f"Database connection error: {e}")
        raise
    finally:
        if connection:
            connection.close()


def create_table():
    """
    Create the ELN_WRITEUP_SCRAPPED table if it doesn't exist.
    """
    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ELN_WRITEUP_SCRAPPED (
                    exp_id VARCHAR(7) NOT NULL,
                    created_date DATE,
                    system_name VARCHAR(20) NOT NULL,
                    reactants_table TEXT NOT NULL,
                    solvents_table TEXT NOT NULL,
                    products_table TEXT NOT NULL,
                    write_up TEXT NOT NULL,
                    PRIMARY KEY(exp_id, system_name)
                );
                """
            )
            connection.commit()
            logging.info("Table created or already exists.")
    except Exception as e:
        logging.error(f"Error creating table: {e}")
        raise


def save_to_database(exp_id, created_date, system_name, **kwargs):
    """
    Save writeup data to the PostgreSQL database.

    Args:
        exp_id (str): The experiment ID.
        created_date (date): The created date.
        system_name (str): The system name.
        **kwargs: Additional tables and writeup data (reactant_table, solvent_table, writeup).
    """
    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()

            # Prepare the columns and values for the INSERT query
            table_columns = (
                ", ".join(
                    [
                        f"{key.lower()}_table"
                        for key in kwargs.keys()
                        if not key.lower().startswith("write")
                    ]
                )
                + ", write_up"
            )
            table_values_placeholders = ", ".join(["%s"] * len(kwargs))
            table_values = list(kwargs.values())

            # Build and execute the INSERT query
            query = f"""
                INSERT INTO ELN_WRITEUP_SCRAPPED (exp_id, created_date, system_name, {table_columns})
                VALUES (%s, %s, %s, {table_values_placeholders});
            """
            cursor.execute(query, [exp_id, created_date, system_name] + table_values)
            connection.commit()
            logging.info(f"Data saved for exp_id {exp_id} in system {system_name}.")

    except Exception as e:
        logging.error(f"Error saving to database: {e}")
        raise


def fetch_write_up(exp_id, system_name):
    """
    Fetch the write_up for a given exp_id and system_name from the database.

    Args:
        exp_id (str): The experiment ID.
        system_name (str): The system name.

    Returns:
        str: The write_up text.
    """
    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT write_up
                FROM ELN_WRITEUP_SCRAPPED
                WHERE exp_id = %s AND system_name = %s;
                """,
                (exp_id, system_name),
            )
            result = cursor.fetchone()
            if result:
                soup = BeautifulSoup(result[0], "html.parser")
                raw_text = soup.get_text(separator=" ")
                return raw_text.strip()
            else:
                logging.warning(f"No write_up found for exp_id {exp_id} in system {system_name}.")
                return ""
    except Exception as e:
        logging.error(f"Error fetching write_up: {e}")
        raise

def compare_and_save_results(exp_id, system_name_1, system_name_2, analysis_date):
    """
    Compare write-ups from two systems and save the results to the comparison table.

    Args:
        exp_id (str): The experiment ID.
        system_name_1 (str): The first system name.
        system_name_2 (str): The second system name.
        analysis_date (date): The analysis date.
    """
    try:
        writeup1 = fetch_write_up(exp_id, system_name_1)
        writeup2 = fetch_write_up(exp_id, system_name_2)

        if not writeup1 or not writeup2:
            logging.warning(f"Skipping comparison for exp_id {exp_id} due to missing write-ups.")
            return

        diff = "\n".join(
            unified_diff(writeup1.splitlines(), writeup2.splitlines(), lineterm="")
        )
        matcher = SequenceMatcher(None, writeup1, writeup2)
        match_percentage = matcher.ratio() * 100
        is_match = match_percentage >= 97

        scibert_score = float(scibert_compare(writeup1, writeup2))
        tfidf_score = float(tfidf_compare(writeup1, writeup2))

        with get_db_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO ELN_WRITEUP_COMPARISON (exp_id, system_name_1, system_name_2, diff, match_percentage, is_match, scibert_score, tfidf_score, analysis_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (exp_id, system_name_1, system_name_2, diff, match_percentage, is_match, scibert_score, tfidf_score, analysis_date),
            )
            connection.commit()
            logging.info(f"Comparison results saved for exp_id {exp_id} between {system_name_1} and {system_name_2}.")
    except Exception as e:
        logging.error(f"Error comparing and saving results: {e}")
        raise


def scrape_writeup(exp_id, domain, index):
    """
    Scrape html text from DM website.

    Args:
        exp_id (str): The experiment ID.
        domain (str): The system name or domain.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    global analysis_date

    service = Service(ChromeDriverManager().install())
    service.start_timeout = 30
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        url = base_url_template.format(domain)
        logging.info(f"Navigating to URL: {url}")
        driver.get(url)

        username_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (
                    By.ID,
                    "isid",
                )
            )
        )

        password_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (
                    By.ID,
                    "password",
                )
            )
        )

        login_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    "input[type='submit'][class='moduleButton']",
                )
            )
        )

        username_field.send_keys(dm_user)
        password_field.send_keys(dm_pass)
        login_button.click()

        logging.info("Login successful!")

        url = url + path_url_template.format(exp_id)
        driver.get(url)

        logging.info(f"Current URL: {driver.current_url}")

        # exp_input_xpath = "//input[@id='mainSearch']"
        # exp_input_xpath = "/html/body/header/div[3]/ul/li[3]/div[1]/input"
        # exp_input = WebDriverWait(driver, 10).until(
        #     EC.presence_of_element_located((By.XPATH, exp_input_xpath))
        # )
        # exp_input.clear()
        # exp_input.send_keys(exp_id)
        #
        # search_results_xpath = "//div[@id='searchResults']"
        # search_results = WebDriverWait(driver, 10).until(
        #     EC.presence_of_element_located((By.XPATH, search_results_xpath))
        # )
        #
        # exp_span_xpath = (
        #     f"//div[@id='search_results_experiments']//span[@name='exp_{exp_id}']"
        # )
        # exp_span = WebDriverWait(driver, 10).until(
        #     EC.element_to_be_clickable((By.XPATH, exp_span_xpath))
        # )
        #
        # exp_span.click()

        # exp_button_xpath = "/html/body/header/div[3]/ul/li[3]/div[2]/div[2]/div/div[2]/div/div/div[3]/div[1]/div[2]/a"
        # exp_button = WebDriverWait(driver, 10).until(
        #     EC.element_to_be_clickable((By.XPATH, exp_button_xpath))
        # )
        #
        # exp_button.click()

        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "samplenotebookiframe"))
        )

        iframe_1 = driver.find_element(By.ID, "samplenotebookiframe")

        try:
            driver.switch_to.frame(iframe_1)
            logging.info("Switched to samplenotebook iframe")

            textarea_div = WebDriverWait(driver, 12).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[@data-customlabel='Textarea']")
                )
            )
            # with open("tmp_studies_iframe.html", "w") as f:
            #     f.write(driver.page_source)

        except TimeoutException:
            logging.error(
                f"Timeout waiting for the content inside the iframe; exp id: {exp_id}."
            )
            textarea_div = None

        # created date
        date_div = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, "//div[@data-customlabel='Date']")
            )
        )

        date_table = date_div.find_element(By.XPATH, "./table")
        date_text = None
        try:
            date_tbody_span = date_table.find_element(By.XPATH, "./tbody//span")
            date_text = date_tbody_span.text.strip()
        except Exception:
            pass

        if not date_text:
            try:
                date_tbody_div = date_table.find_element(By.XPATH, "./tbody//div")
                date_text = date_tbody_div.text.strip()
            except Exception:
                pass

        logging.info(f"date: {date_text}")
        date_value = None
        for date_format in date_formats:
            try:
                date_value = datetime.strptime(date_text, date_format)
                break
            except ValueError:
                continue

        # chemical tables
        table_dct = {"Reactants": None, "Solvents": None, "Products": None}
        try:
            for label in table_dct.keys():
                parent_span = driver.find_element(
                    By.XPATH, f"//span[contains(text(), ' {label} ')]"
                )
                parent_div = parent_span.find_element(
                    By.XPATH,
                    "following-sibling::div[@data-customlabel='Table']",
                )
                table_dct[label] = parent_div.find_element(
                    By.TAG_NAME, "table"
                ).get_attribute("outerHTML")
        except NoSuchElementException as e:
            logging.error(f"Error extracting table element for {exp_id} - {label}: {e}")
            table_dct[label] = None

        # writeup textarea
        try:
            writeup_span = textarea_div.find_element(
                By.XPATH, ".//span[contains(@class, 'formInputArea2')]"
            )
        except NoSuchElementException:
            try:
                writeup_span = textarea_div.find_element(
                    By.XPATH, ".//*[@data-type='writeup']"
                )
            except NoSuchElementException as e:
                write_up = None
                logging.error(f"Error extracting writeup element {exp_id}: {e}")
            else:
                all_tags = writeup_span.find_elements(By.XPATH, ".//*")
                write_up = " ".join(
                    [tag.get_attribute("outerHTML") for tag in all_tags]
                )
        else:
            all_tags = writeup_span.find_elements(By.XPATH, ".//*")
            write_up = " ".join([tag.get_attribute("outerHTML") for tag in all_tags])

        logging.info(f"{index} [{exp_id}] {'=' * 42}")
        save_to_database(exp_id, date_value, domain, **table_dct, write_up=write_up)


    except Exception as e:
        logging.error("Comprehensive Error:")
        logging.error(traceback.format_exc())
        return None
    finally:
        driver.quit()


DB_CONFIG = {
    "dbname": getenv("DB_NAME"),
    "user": getenv("DB_USER"),
    "password": getenv("DB_PASS"),
    "host": getenv("DB_HOST"),
    "port": getenv("DB_PORT"),
}

DOMAINS = {
    "dev": "prelude-dev",
    "up6": "prelude-upgrade6",
    "prod": "prelude",
    "clone1": "prelude-masks",
    "clone2": "prelude-masks2",
}

file_name = "Affinity_match_drop_19-FEB.csv"
base_url_template = "https://{0}.dotmatics.net/browser"
path_url_template = (
    "/testmanager/experiment.jsp?experiment_id={0}&action=edit&tab=notebook"
)


def main():
    parser = argparse.ArgumentParser(
        description="Save ELN write-up to database based on system name"
    )
    parser.add_argument(
        "-c",
        "--create",
        action="store_true",
        help=f"Create the fresh new table in PSQL, defaults to false",
    )
    parser.add_argument(
        "-e",
        "--exp-id",
        help=f"Specify relatively short string of experiment ids comma delimited",
    )
    args = parser.parse_args()
    if any(value == "" or value is None for value in DB_CONFIG.values()):
        raise ValueError(
            "One or more required configurations in DB_CONFIG are missing or empty."
        )

    if not dm_user or not dm_pass:
        raise ValueError("DM user and/or pass not set")

    if args.create:
        create_table()

    base_path = path.join(getcwd(), "exp_ids")
    exp_ids = []
    clone_domains = [DOMAINS["clone1"], DOMAINS["clone2"]]

    if args.exp_id:
        arg_exp_ids = args.exp_id.strip()
        exp_ids = [eid.strip() for eid in arg_exp_ids.split(",") if eid.strip()]
    else:
        with open(path.join(base_path, file_name), "r") as file:
            reader = csv.reader(file)
            next(reader)
            for row in reader:
                exp_ids.append(row[0])

    with ThreadPoolExecutor(max_workers=2) as executor:
        for i, exp_id in enumerate(exp_ids, start=1):
            futures = [executor.submit(scrape_writeup, exp_id, domain, i) for domain in clone_domains]

            for future in as_completed(futures):
               try:
                   future.result()  # Ensure the task completed successfully
               except Exception as e:
                   logging.error(f"Error during scraping: {e}")

            # compare prelude-masks2 vs prelude-masks
            compare_and_save_results(exp_id, clone_domains[1], clone_domains[0], analysis_date)

if __name__ == "__main__":
    main()
