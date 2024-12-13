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
from os import getenv
import argparse


def save_to_database(sys_name, exp_id, write_up):
    try:
        connection = psycopg2.connect(**DB_CONFIG)
        cursor = connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ELN_WRITEUP_SCRAPPED (
                exp_id VARCHAR(7) NOT NULL,
                system_name VARCHAR(20) NOT NULL,
                write_up TEXT NOT NULL,
                PRIMARY KEY(exp_id, system_name)
            );
        """
        )
        connection.commit()

        cursor.execute(
            "INSERT INTO ELN_WRITEUP_SCRAPPED (system_name, exp_id, write_up) VALUES (%s, %s, %s)",
            (sys_name, exp_id, write_up),
        )
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
                    By.XPATH,
                    "/html/body/table/tbody/tr/td/div/div/div/form/table/tbody/tr[3]/td/label/input",
                )
            )
        )

        password_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "/html/body/table/tbody/tr/td/div/div/div/form/table/tbody/tr[4]/td/label/input",
                )
            )
        )

        login_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "/html/body/table/tbody/tr/td/div/div/div/form/table/tbody/tr[6]/td/input",
                )
            )
        )

        username_field.send_keys(getenv("USER"))
        password_field.send_keys(getenv("PASS"))
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

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "samplenotebookiframe"))
        )

        iframe_1 = driver.find_element(By.ID, "samplenotebookiframe")

        driver.switch_to.frame(iframe_1)
        print("Switched to samplenotebook iframe")

        textarea_div = WebDriverWait(driver, 12).until(
            EC.presence_of_element_located(
                (By.XPATH, "//div[@data-customlabel='Textarea']")
            )
        )

        # with open('tmp1.html', 'w') as f:
        #     f.write(driver.page_source)

        span_with_paragraphs = textarea_div.find_element(
            By.XPATH, ".//span[contains(@class, 'formInputArea2')]"
        )

        write_up = None

        try:

            p_tags = span_with_paragraphs.find_elements(By.TAG_NAME, "p")
            # for p in p_tags:
            #     print(p.text)

            write_up = " ".join([p.get_attribute("outerHTML") for p in p_tags])

        except TimeoutException:
            print(
                f"Timeout waiting for the content inside the iframe; exp id: {exp_id}."
            )
        finally:
            driver.switch_to.default_content()

        if write_up:
            save_to_database(domain, exp_id, write_up)

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

DOMAINS = {"dev": "prelude-dev", "up6": "prelude-upgrade6", "prod": "prelude"}
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
    parser = argparse.ArgumentParser(description="Save ELN write-up to database based on system name")
    parser.add_argument(
        "-n",
        "--system_name",
        choices=DOMAINS.keys(),
        help=f"Specify the system name. Must be one of: {', '.join(DOMAINS.keys())}",
    )
    args = parser.parse_args()
    sys_name = args.system_name

    for cro in proj_names:
        print(f"cro: {cro}")
        file_name = file_path_template.format(f"{sys_name}_{cro}")
        print(f"file_name: {file_name}")
        exp_ids = []
        with open(file_name, "r") as file:
            for line in file:
                exp_ids.extend(line.strip().split(","))

        print(exp_ids)
        domain = DOMAINS[sys_name]

        for exp_id in exp_ids:
            scrape_writeup(exp_id, domain)
            print('-'*42)

        print('='*42)


if __name__ == "__main__":
    main()
