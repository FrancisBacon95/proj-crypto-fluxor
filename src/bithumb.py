import os
import requests
import pandas as pd
import jwt 
import uuid
import hashlib
import time
import requests
import json
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from urllib.parse import urlencode, urljoin
from src.config.env import BITHUMB_KEY, BITHUMB_SECRET
from src.config.helper import log_method_call
from src.connection.bigquery import BigQueryConn
headers = {"accept": "application/json"}

class BithumbClient():
    def __init__(self) -> None:
        self.base_url = "https://api.bithumb.com"
        self.bithumb_key = BITHUMB_KEY
        self.bithumb_secret = BITHUMB_SECRET
        self.crypto_markets = self.get_crypto_markets()
        self.bq_conn = BigQueryConn()

    @log_method_call
    def get_crypto_markets(self) -> pd.DataFrame:
        end_point = "v1/market/all"
        url = urljoin(self.base_url, end_point)
        response = requests.get(url, headers=headers).json()
        return pd.DataFrame(response)

    def get_candle_data(self, market: list,  count: int, end_date: date):
        '''
        일봉 데이터 정보(end_date 미만으로 count 만큼 출력)
        캔들 개수(최대 200개까지 요청 가능)
        '''
        end_point = "v1/candles/days"
        url = urljoin(self.base_url, end_point)
        params = {'market': market, 'count': count, 'to': end_date.strftime('%Y-%m-%d 00:00:00')}
        response = requests.get(url, headers=headers, params=params).json()
        return pd.DataFrame(response)
    
    @log_method_call
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

    @log_method_call
    def get_account_info(self) -> pd.DataFrame:
        """전체 계좌 조회
        """
        end_point = "v1/accounts"
        url = urljoin(self.base_url, end_point)
        # Generate access token
        payload = {
            'access_key': self.bithumb_key,
            'nonce': str(uuid.uuid4()),
            'timestamp': round(time.time() * 1000)
        }
        jwt_token = jwt.encode(payload, self.bithumb_secret)
        authorization_token = 'Bearer {}'.format(jwt_token)
        auth_headers = {'Authorization': authorization_token}
        try:
            # Call API
            response = requests.get(url=url, headers=auth_headers)
            response.raise_for_status()
            result = pd.DataFrame(response.json())
            result['balance'] = result['balance'].astype('Float64')
            result['avg_buy_price'] = result['avg_buy_price'].astype('Float64')
            result['locked'] = result['locked'].astype('Int64')
            result['avg_buy_price_modified'] = result['avg_buy_price_modified'].astype(bool)
            except_elements = ['P', 'LUNA2', 'LUNC']
            return result.loc[~result['currency'].isin(except_elements)]
        except Exception as err:
            # handle exception
            print(err)

    @log_method_call
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
        headers = {
            'Authorization': authorization_token, 
            'Content-Type': 'application/json'
        }
        url = urljoin(self.base_url, end_point)
        try:
            # Call API
            return requests.get(url, params=param, headers=headers).json()
        except Exception as err:
            # handle exception
            print(err)

    @log_method_call
    def exceute_order(self, type: str, market: str, ord_type: str, volume: float=None, price: int=None):
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
        requestBody = dict(market=market, side=side, ord_type=ord_type)
        if volume:
            requestBody['volume'] = volume
        if price:
            requestBody['price'] = price

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
        auth_headers = {
            'Authorization': authorization_token,
            'Content-Type': 'application/json'
        }
        end_point = 'v1/orders'
        url = urljoin(self.base_url, end_point)
        try:
            # Call API
            response = requests.post(url, data=json.dumps(requestBody), headers=auth_headers)
            response.raise_for_status()
            return response
            # handle to success or fail
        except Exception as err:
            # handle exception
            print(err)

    @log_method_call
    def enable_cryptos_by_date(self, target_date: date, threshold: int):
        start_date = target_date - timedelta(days=threshold)

        # start_date 시점에 있는 ticker 확인
        result = []
        raw_market_list = self.get_crypto_markets()['market']
        for _ticker in raw_market_list:
            try:
                tmp = self.get_candle_data(_ticker, 1, start_date)
                result += [tmp]
            except:
                continue
        result = pd.concat(result)
        return result

    @log_method_call
    def get_raw_data_1d(self, target_cryptos: list, target_date) -> pd.DataFrame:
        raw = []
        for _ticker in target_cryptos:
            tmp = self.get_candle_data(_ticker, 1, target_date)
            raw += [tmp]
        raw = pd.concat(raw)
        raw['candle_date_time_kst'] = pd.to_datetime(raw['candle_date_time_kst'])
        raw['reg_date'] = raw['candle_date_time_kst']
        raw = raw.drop(columns=['candle_date_time_kst', 'candle_date_time_utc', 'timestamp', 'prev_closing_price'])
        raw = raw.rename(columns={
            'opening_price': 'open',
            'trade_price': 'close',
            'high_price': 'high',
            'low_price': 'low',
            'candle_acc_trade_volume': 'volume',
        'candle_acc_trade_price':  'acc_trade_sum'
        })
        raw = raw.sort_values(by=['reg_date', 'market']).reset_index(drop=True)
        return raw
    
    @log_method_call
    def backfill_data_1d(self, target_market: str, target_date: date, threshold:int=600):
        divide = 100
        result = []
        for i in range(threshold//divide):
            tmp = target_date - timedelta(days=i*divide)
            result += [self.get_candle_data([target_market], count=divide, end_date=tmp)]
        
        result = pd.concat(result).reset_index(drop=True)
        result['candle_date_time_kst'] = pd.to_datetime(result['candle_date_time_kst'])
        result['reg_date'] = result['candle_date_time_kst']
        result = result.drop(columns=['candle_date_time_kst', 'candle_date_time_utc', 'timestamp', 'prev_closing_price'])
        result = result.rename(columns={
            'opening_price': 'open',
            'trade_price': 'close',
            'high_price': 'high',
            'low_price': 'low',
            'candle_acc_trade_volume': 'volume',
        'candle_acc_trade_price':  'acc_trade_sum'
        })
        return result.sort_values(by=['reg_date', 'market']).reset_index(drop=True)
