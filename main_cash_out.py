import warnings
# 모든 경고 무시
import pandas as pd
import pytz
from datetime import datetime, timedelta
from src.ctrend_model import CTRENDAllocator
from fastapi import FastAPI
warnings.filterwarnings("ignore")
kst = pytz.timezone('Asia/Seoul')
today = datetime.combine(datetime.now(tz=kst).date(), datetime.min.time())

target_value = 50000

args = {
    'train_size': 365*2,
    'inference_date': today - timedelta(days=1),
    'except_cryptos': ('KRW-BTC'),
}
obj = CTRENDAllocator(**args)
raw, outliers = obj.preprocess()
pred_result = obj.run(raw=raw, outliers_for_train=outliers)

sorted_cand = pred_result.sort_values(by=['pred']).reset_index(drop=True)
current_price = obj.bithumb.get_current_price(sorted_cand['market'].to_list())[['market', 'trade_price']]
sorted_cand = sorted_cand.merge(obj.account_df, on='symbol', how='inner').merge(
    current_price, on='market', how='left'
)
sorted_cand['total_value'] = sorted_cand['balance'] * sorted_cand['trade_price']

for i in sorted_cand.index:
    if target_value == 0:
        break
    market = sorted_cand.at[i, 'market']
    trade_price = sorted_cand.at[i, 'trade_price']
    balance = sorted_cand.at[i, 'balance']
    sell_volume = min(target_value / trade_price, balance)
    sell_value = sell_volume * trade_price
    target_value -= sell_value
    print({'market': market, 'sell_volume': sell_volume, 'sell_value': sell_value})
    obj.bithumb.exceute_order(type='sell', market=market, ord_type='market', volume=sell_volume)