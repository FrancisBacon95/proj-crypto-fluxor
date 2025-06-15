
import pytz
import time
import logging
from typing import Tuple

from datetime import date, datetime, timedelta
import pandas as pd
from lightgbm import LGBMRegressor

from src.feature_store import FeatureStoreByCrypto, FeatureStoreByDate
from src.connection.bigquery import get_bq_conn
from src.bithumb import get_bithumb_client

logger = logging.getLogger(__name__)
RANDOM_STATE = 950223
kst = pytz.timezone('Asia/Seoul')

bq_conn = get_bq_conn()
bithumb_client = get_bithumb_client()

class CTRENDAllocator():
    def __init__(self, **kwargs):
        self.is_real = kwargs.get('is_real', False)
        self.train_size = kwargs.get('train_size')
        self.inference_date = kwargs.get('inference_date')
        self.except_cryptos = kwargs.get('except_cryptos', ('KRW-BTC'))
        self.model = LGBMRegressor(random_state=RANDOM_STATE)

    def get_bithumb_raw_from_bq(self, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str   =   end_date.strftime('%Y-%m-%d')
        result = bq_conn.query(f'''
        DECLARE start_date DATETIME DEFAULT '{start_date_str}';
        DECLARE   end_date DATETIME DEFAULT '{  end_date_str}';
        SELECT
            reg_date,
            market, 
            SPLIT(market, '-')[1] AS symbol,
            open, 
            close, 
            high, 
            low, 
            volume,
        FROM `proj-asset-allocation.crypto_fluxor.bithumb_crypto_1d`
        WHERE 1=1
        AND reg_date BETWEEN start_date AND DATETIME_ADD(end_date, INTERVAL 7 DAY)
        AND STARTS_WITH(market, 'BTC') IS NOT TRUE
        ORDER BY reg_date, market
        ''')
        result['reg_date'] = pd.to_datetime(result['reg_date']).dt.date
        return result

    def get_marketcaps_from_bq(self, target_date: datetime, lower_bound: int) -> pd.DataFrame:
        target_date_str = target_date.strftime('%Y-%m-%d')
        query = f'''
        DECLARE target_date DATETIME DEFAULT '{target_date_str}';
        DECLARE lower_bound INT64 DEFAULT {lower_bound};
        SELECT *
        FROM `proj-asset-allocation.crypto_fluxor.crypto_market_cap_1d`
        WHERE 1=1
        AND reg_date = target_date
        AND market_cap > lower_bound
        ORDER BY reg_date, symbol
        '''
        result = bq_conn.query(query)
        result['is_stablecoin'] = result['tags'].apply(lambda x: True if 'stablecoin' in x else False)
        result = result.loc[~result['is_stablecoin']].copy()
        return result

    def get_features(self, df: pd.DataFrame) -> pd.DataFrame:
        result = []
        # crypto단위 feature 추가
        for _, _df in df.groupby(by=['market']):
            ctrend = FeatureStoreByCrypto(_df, 'reg_date')
            ctrend.set_features()
            result+=[ctrend.data]
        result=pd.concat(result).dropna()
        
        # 일단위 feature 추가
        fear_greed = FeatureStoreByDate().get_fear_and_greed_indicator(
            start_date=result.index.min(), 
            end_date=result.index.max()
        ).set_index(keys='reg_date')
        result = result.merge(fear_greed, how='left', left_index=True, right_index=True)

        # 주가 데이터를 ticker별로 그룹화한 후, 7일 뒤 종가를 shift로 구함
        result['future_close'] = result.groupby('market')['close'].shift(-7)
        # 7일 뒤 상승률 계산 ((7일 뒤 종가 - 현재 종가) / 현재 종가) * 100
        result['y'] = (result['future_close'] - result['close']) / result['close'] * 100
        result = result.drop(
            columns=['future_close', 'open', 'close', 'high', 'low', 'volume']
        )
        label_cols = ['market', 'symbol']
        obj_col = 'y'
        feature_cols = list(set(result.columns) - set(label_cols) - set(obj_col))
        result = result.dropna(subset=feature_cols)
        return result.reset_index()

    def get_raw_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        train_end_date = self.inference_date - timedelta(days=1)
        train_start_date = train_end_date - timedelta(days=self.train_size)
        raw_bithumb = self.get_bithumb_raw_from_bq(start_date=train_start_date, end_date=self.inference_date)
        raw_marketcap = self.get_marketcaps_from_bq(target_date=self.inference_date, lower_bound=1000000)

        quantile = 0.005
        quantile_lower_bound = raw_marketcap['market_cap'].quantile(    quantile)
        quantile_upper_bound = raw_marketcap['market_cap'].quantile(1 - quantile)
        outliers_for_train = raw_marketcap[
            (raw_marketcap['market_cap'] < quantile_lower_bound) & (raw_marketcap['market_cap'] > quantile_upper_bound)
        ]

        filtered_bithumb = raw_bithumb.loc[raw_bithumb['symbol'].isin(raw_marketcap['symbol'])]
        return filtered_bithumb, outliers_for_train
    
    def run(self):
        filtered_bithumb, outliers_for_train = self.get_raw_data()
        raw_features = self.get_features(filtered_bithumb)

        train_set     = raw_features.loc[(raw_features['reg_date'] <  self.inference_date) & ~(raw_features['symbol'].isin(outliers_for_train))].dropna().reset_index(drop=True)
        inference_set = raw_features.loc[(raw_features['reg_date'] == self.inference_date)].reset_index(drop=True)
        label_cols = ['reg_date', 'market', 'symbol']

        train_label, train_y, train_X = train_set[label_cols], train_set['y'], train_set.drop(columns=['y'] + label_cols)
        inference_label, inference_y, inference_X = inference_set[label_cols], inference_set['y'], inference_set.drop(columns=['y'] + label_cols)
        self.model.fit(train_X, train_y)
        pred = self.model.predict(inference_X)

        pred_result = pd.concat([
            inference_label,
            inference_y.rename('real').reset_index(drop=True),
            pd.Series(pred).rename('pred'),
        ], axis=1)

        return pred_result
