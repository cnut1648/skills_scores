import pandas as pd
import re

from bs4 import BeautifulSoup
from datetime import date
from os import path
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from time import sleep
from delivery import config
import tqdm

if __name__ == '__main__':
    url = config.LINKEDIN_URL
    batch_of_25 = config.BATCH_OF_25

    driver = webdriver.Chrome()
    driver.get(url)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.XPATH, "/html/body/main/div/section/button")
        )
    )
    action = ActionChains(driver)

    i = 1
    while i < batch_of_25:
        # scroll to bottom to load next 25 jobs
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        i += 1
        sleep(10)

    # parsing the visible wZebpage
    pageSource = driver.page_source
    lxml_soup = BeautifulSoup(pageSource, 'lxml')

    # searching for all job containers
    job_container = lxml_soup.find('ul', class_='jobs-search__results-list')

    total_jobs = len(job_container)
    print(f'scraping information about {total_jobs} jobs.')

    # setting up list for job information
    job_id = []
    post_title = []
    company_name = []
    post_date = []
    job_location = []
    job_desc = []
    level = []
    emp_type = []
    functions = []
    industries = []

    # looping job title, company, id, location and date posted
    for job in job_container:
        # job title
        job_titles = job.find("span", class_="screen-reader-text").text
        post_title.append(job_titles)

        # linkedin job id
        job_ids = job.find('a', href=True)['href']
        job_ids = re.findall(r'(?!-)([0-9]*)(?=\?)', job_ids)[0]
        job_id.append(job_ids)

        # company name
        company_names = job.select_one('img')['alt']
        company_name.append(company_names)

        # job location
        job_locations = job.find("span", class_="job-result-card__location").text
        job_location.append(job_locations)

        # posting date
        post_dates = job.select_one('time')['datetime']
        post_date.append(post_dates)

    # looping job description and criteria
    for x in tqdm.trange(1, len(job_id) + 1):
        # clicking on different job containers to view information about the job
        job_xpath = '/html/body/main/div/section/ul/li[{}]/img'.format(x)
        driver.find_element_by_xpath(job_xpath).click()
        sleep(3)

        # job description
        jobdesc_xpath = '/html/body/main/section/div[2]/section[2]/div'
        job_descs = driver.find_element_by_xpath(jobdesc_xpath).text
        job_desc.append(job_descs)

        # job criteria container below the description
        job_criteria_container = lxml_soup.find('ul', class_='job-criteria__list')
        all_job_criterias = job_criteria_container.find_all("span",
                                                            class_='job-criteria__text job-criteria__text--criteria')

        # Seniority level
        seniority_xpath = '/html/body/main/section/div[2]/section[2]/ul/li[1]'
        seniority = driver.find_element_by_xpath(seniority_xpath).text.splitlines(0)[1]
        level.append(seniority)

        # Employment type
        type_xpath = '/html/body/main/section/div[2]/section[2]/ul/li[2]'
        employment_type = driver.find_element_by_xpath(type_xpath).text.splitlines(0)[1]
        emp_type.append(employment_type)

        # Job function
        function_xpath = '/html/body/main/section/div[2]/section[2]/ul/li[3]'
        job_function = driver.find_element_by_xpath(function_xpath).text.splitlines(0)[1]
        functions.append(job_function)

        # Industries
        industry_xpath = '/html/body/main/section/div[2]/section[2]/ul/li[4]'
        industry_type = driver.find_element_by_xpath(industry_xpath).text.splitlines(0)[1]
        industries.append(industry_type)

        x = x + 1

    # creating a dataframe
    job_data = pd.DataFrame(
        {'Job ID': job_id,
         'Date': post_date,
         'Company Name': company_name,
         'Post': post_title,
         'Location': job_location,
         'Description': job_desc,
         'Level': level,
         'Type': emp_type,
         'Function': functions,
         'Industry': industries
         }
    )

    # cleaning description column
    job_data['Description'] = job_data['Description'].str.replace('\n', ' ')
    job_data["Description"] = job_data['Description'].str.replace('Show more', "")

    print(job_data.info())

    save_location = path.join(
        Path(__file__).parent.parent,
        "db",
        f"{date.today()}-linkedin.csv"
    )
    print("saving to", save_location)

    job_data.to_csv(save_location)
