if __name__ == '__main__':
    import sys
    from pathlib import Path
    # 현재 파일의 절대 경로를 기준으로 루트 디렉토리로 이동
    current_dir = Path(__file__).resolve()  # 현재 파일의 절대 경로
    project_root = current_dir.parent.parent  # 두 단계 위의 디렉토리(프로젝트 루트)
    sys.path.append(str(project_root))

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

#This example uses Python 2.7 and the python-request library.

from requests import Request, Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
import json

from src.config.env import COINMARKETCAP_KEY

class CoinMarketCapClient():
    base_url = 'https://sandbox-api.coinmarketcap.com'
    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': COINMARKETCAP_KEY,
    }

    def listing_latest(self):
        end_point = '/v1/cryptocurrency/listings/latest'
        url = self.base_url + end_point
        return requests.get(url, headers=self.headers, params={"tag": "all", "cryptocurrency_type": "all", "sort_dir":"desc"})
client = CoinMarketCapClient()
result = client.listing_latest().json()