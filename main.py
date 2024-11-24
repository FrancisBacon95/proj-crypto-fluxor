import warnings
# 모든 경고 무시
warnings.filterwarnings("ignore")

import pandas as pd
import pytz
from datetime import datetime, timedelta
from src.ctrend_model import CTRENDAllocator
kst = pytz.timezone('Asia/Seoul')
today = datetime.combine(datetime.now(tz=kst).date(), datetime.min.time())

args = {
    'train_size': 365*2,
    'inference_date': today - timedelta(days=1),
    'except_cryptos': ('KRW-BTC'),
}
obj = CTRENDAllocator(**args)

raw, outliers = obj.preprocess()
long, short = obj.run(raw=raw, outliers_for_train=outliers)
obj.execute_trade_logic(cand_long=long, cand_short=short)