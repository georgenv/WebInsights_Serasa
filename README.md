
# Stocks Yahoo

  

This project aims to extract information about stocks from the Yahoo Finance website, based on the desired country.

  

## Getting Started

  

Clone this repository using the following command:

`git clone https://github.com/georgenv/WebInsights_Serasa.git`

  

After installation:

`cd WebInsights_Serasa/Stocks_Yahoo`

  

### Prerequisites

  

You must have installed on your machine:

```
Python 3

SQLite 3

Python3-Pip

Chrome WebDriver
```

  

Python packages:

  

```
APScheduler==3.7.0

Flask==1.1.2

Flask-SQLAlchemy==2.4.4

pandas==1.2.2

selenium==3.141.0

SQLAlchemy==1.3.23
```

Or simply run the following command using pip:

`pip install -r requirements.txt`

  

### App execution

On Stocks_Yahoo directory run: `python3 yahoo_stocks_app.py`

  
### Request
Make a POST request to the endpoint: **http://localhost:5000/stocks**

List of available countries: **https://finance.yahoo.com/screener/new**

**JSON body**:
```
{
  "region": "Chile"
}
```

**API response**:
```
{
  "AAPL.SN": {
    "name": "Apple Inc.",
    "price": "128.30",
    "symbol": "AAPL.SN"
  },
  "ZOFRI.SN": {
    "name": "Zona Franca de Iquique S.A.",
    "price": "469.99",
    "symbol": "ZOFRI.SN"
  }
}