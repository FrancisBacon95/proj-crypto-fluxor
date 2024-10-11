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

load_dotenv()
headers = {"accept": "application/json"}

class BithumbClient():
    def __init__(self) -> None:
        self.base_url = "https://api.bithumb.com"
        self.bithumb_key = os.getenv('BITHUMB_KEY')
        self.bithumb_secret = os.getenv('BITHUMB_SECRET')
        self.crypto_markets = self.get_crypto_markets()

    def get_crypto_markets(self) -> pd.DataFrame:
        end_point = "v1/market/all?isDetails=false"
        url = urljoin(self.base_url, end_point)
        response = requests.get(url, headers=headers).json()
        return pd.DataFrame(response)

    def get_candle_data(self, market: list,  count: int, end_date: date):
        '''
        일봉 데이터 정보(end_date 미만으로 count 만큼 출력)
        '''
        end_point = "v1/candles/days"
        url = urljoin(self.base_url, end_point)
        params = {'market': market, 'count': count, 'to': end_date.strftime('%Y-%m-%d 00:00:00')}
        response = requests.get(url, headers=headers, params=params).json()
        return pd.DataFrame(response)
    
    # crpytos = crypto_markets['market'].to_list()[:3]
    def get_current_price(self, market_list: list) -> pd.DataFrame:
        """현재가 정보
        Args:
            market (str): 마켓ID
        """
        end_point = "v1/ticker"
        url = urljoin(self.base_url, end_point)
        markets = ', '.join(market_list)
        response = requests.get(url, headers=headers, params={'markets': markets})
        return pd.DataFrame(response.json())
    
    def get_orderable_info(self, market) -> dict:
        """가상화폐 주문 가능 정보
        Args:
            market (str): 마켓ID
        """
        # Set API parameters
        param = {'market': market}

        end_point = '/v1/orders/chance'
        # Generate access token
        query = urlencode(param).encode()
        hash = hashlib.sha512()
        hash.update(query)
        query_hash = hash.hexdigest()
        payload = {
            'access_key': self.bithumb_key,
            'nonce': str(uuid.uuid4()),
            'timestamp': round(time.time() * 1000), 
            'query_hash': query_hash,
            'query_hash_alg': 'SHA512',
        }   
        jwt_token = jwt.encode(payload, self.bithumb_secret)
        authorization_token = 'Bearer {}'.format(jwt_token)
        headers = {'Authorization': authorization_token}
        url = urljoin(self.base_url, end_point)
        try:
            # Call API
            return requests.get(url, params=param, headers=headers).json()
        except Exception as err:
            # handle exception
            print(err)

    def exceute_order(self, type: str, market: str, volume: float, price: int, ord_type: str):
        """가상화폐 거래 실행
        Args:
            type (str): 주문 종류
                - buy  : 매수
                - sell : 매도 
            market (str): 마켓ID
            price (int): 주문 가격. (지정가, 시장가 매수 시 필수)
            ord_type (str): 주문 타입
                - limit : 지정가 주문
                - price : 시장가 주문(매수)
                - market : 시장가 주문(매도)
        """
        # Set API parameters
        side = 'bid' if type == 'buy' else 'ask' if type == 'sell' else None
        requestBody = dict( market=market, side=side, volume=volume, price=price, ord_type=ord_type )

        # Generate access token
        query = urlencode(requestBody).encode()
        hash = hashlib.sha512()
        hash.update(query)
        query_hash = hash.hexdigest()
        payload = {
            'access_key': self.bithumb_key,
            'nonce': str(uuid.uuid4()),
            'timestamp': round(time.time() * 1000), 
            'query_hash': query_hash,
            'query_hash_alg': 'SHA512',
        }
        jwt_token = jwt.encode(payload, self.bithumb_secret)
        authorization_token = 'Bearer {}'.format(jwt_token)
        headers = {
        'Authorization': authorization_token,
        'Content-Type': 'application/json'
        }
        end_point = 'v1/orders'
        url = urljoin(self.base_url, end_point)
        try:
            # Call API
            response = requests.post(url, data=json.dumps(requestBody), headers=headers).json()
            # handle to success or fail
        except Exception as err:
            # handle exception
            print(err)