
import pandas as pd
import numpy as np
from datetime import date, timedelta, datetime
from src.bithumb import BithumbClient
from src.coinmarketcap import CoinMarketCapClient

class CTREND():
    def __init__(self, data: pd.DataFrame, date_col: str) -> None:
        self.data = data.set_index(keys=[date_col]).sort_index()

        self.bithumb_client = BithumbClient()
        self.coinmarketcap_client = CoinMarketCapClient()
        # 학습을 위해 필요한 최초 시점
        self.pred_date = date.today()
        self.train_start_date = self.pred_date - timedelta(days=570)
        self.train_end_date = self.pred_date - timedelta(days=1)

        self.enable_train_tickers = self.get_enable_train_tickers_by_date()

    def set_features(self):
        self.set_RSI()
        self.set_stochK()
        self.set_stochD()
        self.set_stochRSI()
        self.set_CCI()

        # MA
        for i in [3, 5, 10, 20, 50, 100, 200]:
            self.set_SMA_based(SMA_size=i)
        
        # MACD based
        self.set_MACD()
        self.set_MACD_signal()
        
        # Chaikin (volume indicator)
        self.set_Chaikin()
        self.set_bollinger_based()

    def set_RSI(self, window:int=14):
        self.data['price_diff'] = self.data['close'].diff(periods=1)

        self.data['gain'] = np.where(self.data['price_diff'] > 0, self.data['price_diff']      , 0)
        self.data['loss'] = np.where(self.data['price_diff'] < 0, self.data['price_diff'].abs(), 0)

        self.data['AU'] = self.data['gain'].rolling(window=window).mean()
        self.data['AD'] = self.data['loss'].rolling(window=window).mean()

        self.data['RS'] = self.data['AU'] / self.data['AD']
        self.data['RSI'] = self.data['AU'] / (self.data['AU'] + self.data['AD']) * 100
        
        self.data = self.data.drop(columns=['price_diff', 'gain', 'loss', 'AU', 'AD', 'RS'])

    def set_stochK(self, window:int=14):
        self.data[f'lowest_stochK_{window}d'] = self.data['close'].rolling(window=window).min()
        self.data[f'highest_stochK_{window}d'] = self.data['close'].rolling(window=window).max()

        self.data['stochK'] = (self.data['close'] - self.data[f'lowest_stochK_{window}d']) / (self.data[f'highest_stochK_{window}d'] - self.data[f'lowest_stochK_{window}d']) * 100

        self.data = self.data.drop(columns=[f'lowest_stochK_{window}d', f'highest_stochK_{window}d'])
        
    def set_stochD(self, window:int=3):
        self.data['stochD'] = self.data['stochK'].rolling(window=window).mean()

    def set_stochRSI(self, window:int=14):
        self.data[f'lowest_RSI_{window}d']  = self.data['RSI'].rolling(window=window).min()
        self.data[f'highest_RSI_{window}d'] = self.data['RSI'].rolling(window=window).max()
        self.data['stochRSI'] = (self.data[f'RSI'] - self.data[f'lowest_RSI_{window}d']) / (self.data[f'highest_RSI_{window}d'] - self.data[f'lowest_RSI_{window}d']) * 100
        self.data = self.data.drop(columns=[f'lowest_RSI_{window}d', f'highest_RSI_{window}d'])

    def set_CCI(self, window:int=20):
        # typical_price는 실제로 해당 값들의 SUM을 의미한다.
        self.data['TP'] = (self.data['high'] + self.data['low'] + self.data['close']) / 3

        # self.data['TP'].rolling(window=window).sum()
        self.data['MA_TP'] = self.data['TP'].rolling(window=window).mean()
        self.data['mean_deviation_TP'] = self.data['TP'].rolling(window=window).apply(lambda x: abs(x - x.mean()).mean(), raw=True)
        self.data['CCI'] = (self.data['TP'] - self.data['MA_TP']) / (0.015 * self.data['mean_deviation_TP'])
        self.data = self.data.drop(columns=['MA_TP', 'mean_deviation_TP', 'CCI'])


    def set_SMA_based(self, SMA_size: int):
        self.data[f'SMA_{SMA_size}'] = self.data['close'].rolling(SMA_size).mean()
        self.data[f'volSMA_{SMA_size}'] = self.data['volume'].rolling(SMA_size).mean()

    def set_MACD(self, fast_window: int=12, slow_window: int=26):
        self.data[   'MACD'] = self.data['close' ].rolling(fast_window).mean() - self.data['close' ].rolling(slow_window).mean()
        self.data['volMACD'] = self.data['volume'].rolling(fast_window).mean() - self.data['volume'].rolling(slow_window).mean()

    def set_MACD_signal(self, window:int=9):
        self.data['MACD_diff_signal'] = self.data['MACD'] - self.data['MACD'].rolling(window=window).mean()
        self.data['volMACD_diff_signal'] = self.data['volMACD'] - self.data['volMACD'].rolling(window=window).mean()

    def set_Chaikin(self, fast_window:int=3, slow_window:int=10):
        self.data['AD'] = ((self.data['close'] - self.data['low']) - (self.data['high'] - self.data['close'])) / (self.data['high'] - self.data['low']) * self.data['volume']
        self.data[f'EMA_AD_{fast_window}d'] = self.data['AD'].rolling(window=fast_window).mean()
        self.data[f'EMA_AD_{slow_window}d'] = self.data['AD'].rolling(window=slow_window).mean()
        self.data['Chaikin'] = self.data[f'EMA_AD_{fast_window}d'] - self.data[f'EMA_AD_{slow_window}d']

        self.data = self.data.drop(columns=['AD', f'EMA_AD_{fast_window}d', f'EMA_AD_{slow_window}d'])

    def set_bollinger_based(self, window: int=20):
        # 설정 값
        k = 2   # 표준편차 배수 (일반적으로 2)

        # Step 1: 중심선 계산 (n-일 단순 이동평균)
        self.data['SMA'] = self.data['close'].rolling(window=window).mean()

        # Step 2: 표준편차 계산
        self.data['std'] = self.data['close'].rolling(window=window).std()

        # Step 3: 상한선, 하한선 계산
        self.data['Boll_up'] = self.data['SMA'] + (k * self.data['std'])
        self.data['Boll_low'] = self.data['SMA'] - (k * self.data['std'])

        # Step 4: 밴드폭 계산
        self.data['Boll_width'] = self.data['Boll_up'] - self.data['Boll_low']

        self.data = self.data.rename(columns={'SMA': 'Boll_mid'})
        self.data = self.data.drop(columns=['std'])

    def get_enable_train_tickers_by_date(self) -> list:
        # start_date 시점에 있는 ticker 확인
        enable_train_tickers = []
        for _ticker in self.bithumb_client.crypto_markets['market'].to_list():
            try:
                tmp = self.bithumb_client.get_candle_data(_ticker, 1, self.train_start_date)
                enable_train_tickers += [tmp]
            except:
                continue
        result = pd.concat(enable_train_tickers)
        return list(result['market'].unique())

    def get_raw_data(self, pred_date: date) -> pd.DataFrame:
        raw = []
        for _ticker in self.enable_train_tickers:
            tmp_1 = self.bithumb_client.get_candle_data(_ticker, 200, pred_date)
            tmp_2 = self.bithumb_client.get_candle_data(_ticker, 200, pred_date - timedelta(days=200))
            tmp_3 = self.bithumb_client.get_candle_data(_ticker, 170, pred_date - timedelta(days=200*2))
            raw += [tmp_1, tmp_2, tmp_3]
        raw = pd.concat(raw)

        raw['candle_date_time_kst'] = pd.to_datetime(raw['candle_date_time_kst'])
        raw['candle_date_time_utc'] = pd.to_datetime(raw['candle_date_time_utc'])
        return raw
    
    def get_enable_train_tickers_by_marketcap(self) -> pd.DataFrame:
        coinmarketcap_client = self.coinmarketcap_client
        latest_raw = coinmarketcap_client.listing_latest()
        latest_raw['is_stablecoin'] = latest_raw['tags'].apply(lambda x: True if 'stablecoin' in x else False)

        # exception conditions
        cand_by_marketcap = latest_raw.loc[~latest_raw['is_stablecoin']].copy()

        value_lower_bound = 1000000
        cand_by_marketcap = cand_by_marketcap.loc[cand_by_marketcap['market_cap'] > value_lower_bound]

        # 상위 0.5%, 하위 0.5%의 경계 값 계산
        except_quantile = 0.005
        quantile_lower_bound = cand_by_marketcap['market_cap'].quantile(    except_quantile)
        quantile_upper_bound = cand_by_marketcap['market_cap'].quantile(1 - except_quantile)

        cand_by_marketcap = cand_by_marketcap[
            cand_by_marketcap['market_cap'].between(quantile_lower_bound, quantile_upper_bound, inclusive="neither")
        ]

        return cand_by_marketcap

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        raw = df.rename(columns={
            'opening_price': 'open',
            'trade_price': 'close',
            'high_price': 'high',
            'low_price': 'low',
            'candle_acc_trade_volume': 'volume',
            'candle_date_time_kst': 'kst_date'
        })[
            ['kst_date', 'market', 'open', 'close', 'high', 'low', 'volume']
        ].copy()
        raw['kst_date'] = pd.to_datetime(raw['kst_date']).dt.date

        result = []
        for _, _df in raw.groupby(by=['market']):
            ctrend = CTREND(_df, 'kst_date')
            ctrend.set_features()
            result+=[ctrend.data]
        result=pd.concat(result).dropna()

        latest_raw = self.get_enable_train_tickers_by_marketcap()
        result['symbol'] = result['market'].apply(lambda x: x.split('-')[1])
        result = result.loc[result['symbol'].isin(latest_raw['symbol'])]

        # 주가 데이터를 ticker별로 그룹화한 후, 7일 뒤 종가를 shift로 구함
        result['future_close'] = result.groupby('market')['close'].shift(-7)
        # 7일 뒤 상승률 계산 ((7일 뒤 종가 - 현재 종가) / 현재 종가) * 100
        result['y'] = (result['future_close'] - result['close']) / result['close'] * 100
        result = result.drop(columns=['future_close', 'open', 'close', 'high', 'low', 'volume']).dropna()
        return result