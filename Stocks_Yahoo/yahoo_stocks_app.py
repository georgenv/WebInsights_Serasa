import atexit
import datetime
import os
import time
import pandas as pd

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from selenium import webdriver
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait

# Flask and SQLAlchemy configuration
app = Flask(__name__)
project_dir = os.path.dirname(os.path.abspath(__file__))
database_uri = f"sqlite:///{os.path.join(project_dir, 'stocksinfo.db')}"
app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
db.init_app(app)

# Selenium configuration
DRIVER_PATH = "C:\\Users\\georg\\Documents\\Development\\Chrome_Webdriver\\chromedriver.exe"
WEBSITE = "https://finance.yahoo.com/screener/new"


class StockInfoModel(db.Model):
    """
    This class defines the data model that will be stored in the cache (database)
    """

    region = db.Column(db.String(100), primary_key=True, unique=True)
    content = db.Column(db.JSON)
    timestamp = db.Column(db.TIMESTAMP)

    def __init__(self, region, content, timestamp):
        self.region = region
        self.content = content
        self.timestamp = timestamp

    def __repr__(self):
        return f"{self.region}:{self.content}"


class SingletonMeta(type):
    """
    The design pattern Singleton implemented as metaclass, it ensures that will be only
    one instance of StocksRetriever class.
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class StocksRetriever(metaclass=SingletonMeta):
    """
    StocksRetriever is the class where the browser is initialised and reponsible to
    retrieve stocks information based on the region sent through post request.
    """

    def __init__(self):
        # Create a headless browser
        opts = Options()
        opts.headless = True
        opts.add_argument('--ignore-certificate-errors')
        opts.add_argument('--ignore-ssl-errors')
        opts.add_argument('log-level=3')

        self.browser = webdriver.Chrome(executable_path=DRIVER_PATH, options=opts)
        self.browser.get(WEBSITE)
        self.timer = WebDriverWait(self.browser, 120)
        self.first_req = True


    def get_country(self, region):
        """
        If region is valid, this method returns the name of the country to be ticked on
        countries list. Else, it returns False.

        Params:
            region (str): Region name.
            country (str): Country name.
        """

        self.browser.find_element_by_xpath('//*[@id="screener-criteria"]/div[2]/div[1]/div[1]\
                                            /div[1]/div/div[2]/ul/li[1]/button/span').click()
        self.browser.find_element_by_xpath('//*[@id="screener-criteria"]/div[2]/div[1]/div[1]\
                                            /div[1]/div/div[2]/ul/li/div').click()
        input_element = self.browser.find_element_by_xpath('//input[@placeholder="Find filters"]')
        input_element.click()
        input_element.send_keys(region)
        time.sleep(0.5)

        result_set = self.browser.find_element_by_xpath('//div[@id="dropdown-menu"]\
                                                        /div[@data-test="itm-menu-cntr"]/div/ul')
        country_list = result_set.text.split('\n')
        if country_list == [''] or len(country_list) > 1:
            return False

        country = country_list[0]
        return country


    def wait_table(self):
        """
        This method forces the application to wait for the results table to be fully loaded,
        before performing the next step.

        Returns:
            table_id (object): Reference to the loaded table.
        """

        table_id = self.timer.until(expected_conditions.presence_of_element_located((\
                                    By.XPATH, '//div[@id="scr-res-table"]/div/table')))

        return table_id


    def get_table_data(self, table_id):
        """
        This method scrapes all data contained on each page of the table.

        Params:
            table_id (object): Reference to the loaded table.

        Returns:
            rows (list): List containing the data for each row in the table.
            col_names (list): List with the name of each column in the table.
        """

        cols_id = table_id.find_elements_by_xpath('//thead/tr/th')

        rows = []
        idx = 0

        while True:

            if idx > 0:
                time.sleep(2)

            for row in table_id.find_elements_by_xpath('.//tr'):
                line = [td.text for td in row.find_elements_by_xpath('.//td')]
                if line:
                    rows.append(line)
            try:
                # Iterates over all the data in the table, by clicking on the Next button
                self.browser.find_element_by_xpath('//div[@id="scr-res-table"]\
                                                    /div/button/span/span[text()="Next"]').click()
                print(f'LOG - Scrapping table page {idx + 1}')
                idx += 1
            except ElementClickInterceptedException:
                # Stop condition: When Next button is not clickable anymore
                break

        col_names = [col.text for col in cols_id]

        return rows, col_names


    def process_table_data(self, rows, col_names):
        """
        Acquire all the data in the table and format the request response.

        Params:
            rows (list): List containing the data for each row in the table.
            col_names (list): List with the name of each column in the table.

        Returns:
            res_dict (dict): dictionary containing formatted data.
        """

        table_df = pd.DataFrame(data=rows, columns=col_names)
        # remove duplicated rows
        table_df = table_df.drop_duplicates(subset=['Symbol'], keep='last')

        res_dict = {}

        for _, row in table_df.iterrows():
            if row["Symbol"] not in res_dict:
                res_dict[row["Symbol"]] = dict()
                res_dict[row["Symbol"]]["symbol"] = row["Symbol"]
                res_dict[row["Symbol"]]["name"] = row["Name"]
                res_dict[row["Symbol"]]["price"] = row["Price (Intraday)"]

        return res_dict


    def process_request(self, region):
        """
        Process the request based on given region

        Params:
            region (str): country name

        Returns:
            reponse (json): response containing the desired information on an error.
        """

        db_query = StockInfoModel.query.get(region)
        if db_query:
            final_response = make_response(jsonify(db_query.content), 200)
        else:
            if not self.first_req:
                self.browser.get(WEBSITE)
                time.sleep(0.5)

            self.first_req = False

            country = self.get_country(region)

            if not country:
                return make_response("There is an error in your request.Please re-enter the desired region name.",
                                     400)

            # tick the target country on the list
            self.browser.find_element_by_xpath(f'//span[text()="{country}"]').click()
            time.sleep(1)
            # click on find stocks button
            self.browser.find_element_by_xpath('.//button[@data-test="find-stock"]').click()

            # wait for the table to be fully loaded
            table_id = self.wait_table()
            # click on 'Show 25 rows' button
            self.browser.find_element_by_xpath('//div[@id="scr-res-table"]/div/span/\
                                                div[@data-test="select-container"]').click()
            time.sleep(0.5)

            # select 100 rows to be displayed
            self.browser.find_element_by_xpath('//div[@data-test="showRows-select-menu"]\
                                                /div[@data-value="100"]').click()
            # wait for the table to be fully loaded
            table_id = self.wait_table()

            # get all data from table
            rows, col_names = self.get_table_data(table_id)

            # process table data using dataframe
            final_response = self.process_table_data(rows, col_names)

            stock_info = StockInfoModel(region=region,
                                        content=final_response,
                                        timestamp=datetime.datetime.now())
            db.session.add(stock_info)
            db.session.commit()
            final_response = make_response(jsonify(final_response), 200)

        return final_response


@app.route('/stocks', methods=['POST'])
def get_stocks():
    """
    Retrieve stocks information abount an specific region.
    """

    req = request.json
    region = req.get('region', None)
    stocks_ret = StocksRetriever()

    if not region:
        return make_response("You request was sent with an invalid key.", 400)

    response = stocks_ret.process_request(region.lower())

    return response


def delete_cache_routine():
    """
    Routine that deletes information that has been cached for more than 3 minutes
    and 13 seconds.
    """

    stocks_regions = StockInfoModel.query.all()

    if stocks_regions:
        for elem in stocks_regions:
            ts_now = datetime.datetime.now()
            elem_ts = elem.timestamp
            cache_time = (ts_now - elem_ts).total_seconds()

            if cache_time > 193:
                db.session.delete(elem)
                db.session.commit()


scheduler = BackgroundScheduler()
scheduler.add_job(func=delete_cache_routine, trigger="interval", seconds=1)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

if __name__ == '__main__':
    db.drop_all()
    db.create_all()
    app.run()
    