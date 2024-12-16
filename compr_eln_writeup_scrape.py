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
from os import getenv, path, getcwd
import argparse
from datetime import datetime

dm_user = getenv("USER")
dm_pass = getenv("PASS")
date_formats = ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']

def save_to_database(exp_id, created_date, system_name, **kwargs):
    """
    Save writeup data to the psql db.

    Args:
        exp_id (str): The experiment ID.
        system_name (str): The system name.
        created_date (date): The created date
        **kwargs: Additional tables and writeup data (reactant_table, solvent_table, writeup).
    """
    try:
        connection = psycopg2.connect(**DB_CONFIG)
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

        table_columns = ", ".join(
            [
                f"{key.lower()}_table"
                for key in kwargs.keys()
                if not key.lower().startswith("write")
            ]
        ) + ', write_up'
        table_values_placeholders = ", ".join(["%s"] * len(kwargs))
        table_values = list(kwargs.values())

        query = f"""
            INSERT INTO ELN_WRITEUP_SCRAPPED (exp_id, created_date, system_name, {table_columns})
            VALUES (%s, %s, %s, {table_values_placeholders});
        """
        cursor.execute(query, [exp_id, created_date, system_name] + table_values)
        connection.commit()

    except Exception as e:
        print(f"Error saving to database: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def scrape_writeup(exp_id, domain):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    service = Service(ChromeDriverManager().install())
    service.start_timeout = 30
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        url = base_url_template.format(domain)
        print(f"Navigating to URL: {url}")
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

        print("Login successful!")

        url = url + path_url_template.format(exp_id)
        driver.get(url)

        print(f"Current URL: {driver.current_url}")

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
            print("Switched to samplenotebook iframe")

            textarea_div = WebDriverWait(driver, 12).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[@data-customlabel='Textarea']")
                )
            )
            # with open("tmp_studies_iframe.html", "w") as f:
            #     f.write(driver.page_source)

        except TimeoutException:
            print(
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

        print(f'date: {date_text}')
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
            print(f"Error extracting table element for {exp_id} - {label}: {e}")
            table_dct[label] = None

        # writeup textarea
        try:
            writeup_span = textarea_div.find_element(
                By.XPATH, ".//span[contains(@class, 'formInputArea2')]"
            )
            p_tags = writeup_span.find_elements(By.TAG_NAME, "p")
            write_up = " ".join([p.get_attribute("outerHTML") for p in p_tags])

        except NoSuchElementException as e:
            print(f"Error extracting writeup element {exp_id}: {e}")
            write_up = None

        if not write_up:
            div_tags = writeup_span.find_elements(By.TAG_NAME, "div")
            write_up = " ".join([d.get_attribute("outerHTML") for d in div_tags])

        print("=" * 42)
        save_to_database(exp_id, date_value, domain, **table_dct, write_up=write_up)

    except Exception as e:
        print("Comprehensive Error:")
        print(traceback.format_exc())
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

DOMAINS = {"dev": "prelude-dev", "up6": "prelude-upgrade6", "prod": "prelude", "clone": "prelude-clone"}
file_path_template = "exp_ids_eln_writeup_{0}.txt"
base_url_template = "https://{0}.dotmatics.net/browser"
path_url_template = (
    "/testmanager/experiment.jsp?experiment_id={0}&action=edit&tab=notebook"
)
proj_names = [
    "CRO_Affinity_Wilmington",
    "CRO_Affinity_Wuhan",
    "CRO_Viva_ChemELN",
    "ChemELN",
]


def main():
    parser = argparse.ArgumentParser(
        description="Save ELN write-up to database based on system name"
    )
    parser.add_argument(
        "-n",
        "--system_name",
        required=True,
        choices=DOMAINS.keys(),
        help=f"Specify the system name. Must be one of: {', '.join(DOMAINS.keys())}",
    )
    parser.add_argument(
        "-e",
        "--exp-id",
        help=f"Specify relatively short string of experiment ids comma delimited",
    )
    args = parser.parse_args()
    sys_name = args.system_name

    if any(value == "" or value is None for value in DB_CONFIG.values()):
        raise ValueError(
            "One or more required configurations in DB_CONFIG are missing or empty."
        )

    if not dm_user or not dm_pass:
        raise ValueError('DM user and/or pass not set')

    base_path = path.join(getcwd(), "exp_ids")
    exp_ids = []

    if args.exp_id:
        arg_exp_ids = args.exp_id.strip()
        exp_ids = [eid.strip() for eid in arg_exp_ids.split(",") if eid.strip()]
    else:
        for cro in proj_names:
            print(f"cro: {cro}")
            file_name = file_path_template.format(f"{sys_name}_{cro}")
            print(f"file_name: {file_name}")
            with open(path.join(base_path, file_name), "r") as file:
                for line in file:
                    exp_ids.extend(line.strip().split(","))

    print(exp_ids)
    domain = DOMAINS[sys_name]

    for exp_id in exp_ids:
        scrape_writeup(exp_id, domain)



if __name__ == "__main__":
    main()
