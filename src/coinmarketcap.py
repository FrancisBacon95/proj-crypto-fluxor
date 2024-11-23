import os
import pytz
import requests
import pandas as pd
import jwt 
import uuid
import hashlib
import time
import requests
import json
from tqdm import tqdm
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from urllib.parse import urlencode, urljoin

from src.config.env import COINMARKETCAP_KEY
class CoinMarketCapClient():
    base_url = 'https://pro-api.coinmarketcap.com'
    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': COINMARKETCAP_KEY,
    }

    def listing_latest(self) -> pd.DataFrame:
        end_point = '/v1/cryptocurrency/listings/latest'
        url = urljoin(self.base_url,end_point)
        params = {
            "tag": "all",
            "cryptocurrency_type": "all", 
            "sort_dir":"desc",
            "sort": "market_cap",
            "limit": 5000,
        }
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        result = pd.DataFrame(response.json()['data'])
        quote = pd.DataFrame(map(lambda x: x['USD'], result['quote'].values)).drop(columns='last_updated')
        return pd.concat([result, quote], axis=1)
    
    def get_fear_and_greed_latest(self) -> pd.DataFrame:
        end_point = '/v3/fear-and-greed/latest'
        url = urljoin(self.base_url,end_point)
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        result = response.json()['data']
        result = pd.DataFrame([result]).rename(columns={'update_time': 'created_at'})
        result['created_at'] = pd.to_datetime(result['created_at']).dt.tz_convert('Asia/Seoul')
        result['reg_date'] = pd.to_datetime(result['created_at'].dt.date)
        return result[['reg_date', 'value', 'value_classification', 'created_at']]
    
    def get_fear_and_greed_historical(self) -> pd.DataFrame:
        end_point = '/v3/fear-and-greed/historical'
        url = urljoin(self.base_url,end_point)
        params = {'start': 1, 'limit': 500}
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        result = response.json()['data']
        result = pd.DataFrame(result).rename(columns={'timestamp': 'created_at'})
        result['created_at'] = result['created_at'].astype(int)
        result['created_at'] = result['created_at'].apply(lambda x: datetime.fromtimestamp(x, tz=pytz.timezone('Asia/Seoul')))
        result['reg_date'] = pd.to_datetime(result['created_at'].dt.date)
        return result[['reg_date', 'value', 'value_classification', 'created_at']]