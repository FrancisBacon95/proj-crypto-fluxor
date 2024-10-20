import os
import requests
import pandas as pd
import jwt 
import uuid
import hashlib
import time
import requests
import json
from tqdm import tqdm
from datetime import date, timedelta
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
        url = self.base_url + end_point
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