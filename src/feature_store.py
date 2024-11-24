import pandas as pd
import numpy as np
from datetime import date, timedelta, datetime
from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression
from src.connection.bigquery import BigQueryConn
from src.config.helper import log_method_call
class FeatureStoreByCrypto():
    def __init__(self, data: pd.DataFrame, date_col: str) -> None:
        self.data = data.set_index(keys=[date_col]).sort_index()

        # 학습을 위해 필요한 최초 시점
        self.pred_date = date.today()
        self.train_start_date = self.pred_date - timedelta(days=570)
        self.train_end_date = self.pred_date - timedelta(days=1)

        # self.enable_train_tickers = self.get_enable_train_tickers_by_date()

    def set_features(self):
        # CTREND standard features
        self.set_momentum_oscillators()
        self.set_SMA_indicators()
        self.set_volume_indicators()
        self.set_volatility_based_indicators()
    
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

    def set_SMA_based(self, SMA_size: int, for_volume: bool=False):
        if for_volume:
            using_col = 'volume'
            result_col = f'volSMA_{SMA_size}'
        else:
            using_col = 'close'
            result_col = f'SMA_{SMA_size}'
        self.data[result_col] = self.data[using_col].rolling(SMA_size).mean()

    def set_MACD(self, fast_window: int=12, slow_window: int=26, for_volume: bool=False):
        if for_volume:
            using_col = 'volume'
            result_col = 'volMACD'
        else:
            using_col = 'close'
            result_col = 'MACD'

        self.data[result_col] = self.data[using_col].rolling(fast_window).mean() - self.data['close' ].rolling(slow_window).mean()

    def set_MACD_signal(self, window:int=9, for_volume: bool=False):
        if for_volume:
            using_col = 'volMACD'
            result_col = 'volMACD_diff_signal'
        else:
            using_col = 'MACD'
            result_col = 'MACD_diff_signal'
        self.data[result_col] = self.data[using_col] - self.data[using_col].rolling(window=window).mean()

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

    def set_markov_regime_switching(self):
        df = self.data.copy()
        df['returns'] = np.log(df['close'] / df['close'].shift(1))  # Log returns
        df = df.dropna()

        model = MarkovRegression(df['returns'], k_regimes=2, switching_variance=True).fit()
        smoothed_marginal_probabilities = model.smoothed_marginal_probabilities
        result = pd.DataFrame(smoothed_marginal_probabilities[0].rename('regime_prob'))

        cutoff = result['regime_prob'].mean()
        result['regime'] = np.where(result['regime_prob'] >= cutoff, 0, 1)
        self.data = self.data.merge(
            result[['regime']],
            left_index=True,
            right_index=True,
            how='left'
        )

        max_counted_regime = result['regime'].value_counts().index[0]
        self.data['regime'].fillna(max_counted_regime)

    def set_momentum_oscillators(self):
        self.set_RSI()
        self.set_stochK()
        self.set_stochD()
        self.set_stochRSI()
        self.set_CCI()

    def set_SMA_indicators(self):
        for i in [3, 5, 10, 20, 50, 100, 200]:
            self.set_SMA_based(SMA_size=i, for_volume=False)
        self.set_MACD(fast_window=12, slow_window=26, for_volume=False)
        self.set_MACD_signal(window=9, for_volume=False)

    def set_volume_indicators(self):
        for i in [3, 5, 10, 20, 50, 100, 200]:
            self.set_SMA_based(SMA_size=i, for_volume=True)
        self.set_MACD(fast_window=12, slow_window=26, for_volume=True)
        self.set_MACD_signal(window=9, for_volume=True)
        self.set_Chaikin()

    def set_volatility_based_indicators(self):
        self.set_bollinger_based()
        self.set_markov_regime_switching()


class FeatureStoreByDate():
    def __init__(self):
        self.bq_conn = BigQueryConn()

    def get_fear_and_greed_indicator(self, start_date: date, end_date: date) -> pd.DataFrame:
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        result = self.bq_conn.query(f"""
        DECLARE start_date DATE DEFAULT '{start_date_str}';
        DECLARE   end_date DATE DEFAULT '{  end_date_str}';
        SELECT
            reg_date,
            value AS fear_greed_value,
            CASE
                WHEN value_classification = 'Extreme fear'  THEN -2
                WHEN value_classification = 'Fear'          THEN -1
                WHEN value_classification = 'Neutral'       THEN  0
                WHEN value_classification = 'Greed'         THEN  1
                WHEN value_classification = 'Extreme greed' THEN  2
            END AS fear_greed_level,
        FROM `proj-asset-allocation.crypto_fluxor.fear_and_greed`
        WHERE 1=1
        AND reg_date BETWEEN start_date AND end_date
        """)
        return result
