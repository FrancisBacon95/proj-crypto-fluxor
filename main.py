import pandas as pd
import pytz
from datetime import datetime, timedelta
from src.ctrend_model import CTRENDAllocator
kst = pytz.timezone('Asia/Seoul')
today = datetime.now(tz=kst).date()

args = {
    'train_size': 365*2,
    'inference_date': today - timedelta(days=1),
    'except_cryptos': ('KRW-BTC'),
}
obj = CTRENDAllocator(**args)
obj.run()