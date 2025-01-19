import warnings
# 모든 경고 무시
import pandas as pd
import pytz
from datetime import datetime, timedelta
from src.ctrend_model import CTRENDAllocator
from fastapi import FastAPI
warnings.filterwarnings("ignore")

app = FastAPI()
# health check
@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get('/run')
def run():
    kst = pytz.timezone('Asia/Seoul')
    today = datetime.combine(datetime.now(tz=kst).date(), datetime.min.time())

    args = {
        'train_size': 365*2,
        'inference_date': today - timedelta(days=1),
        'except_cryptos': ('KRW-BTC'),
    }
    obj = CTRENDAllocator(**args)
    obj.sell_expired_crypto(target_date=today, date_range=40)
    raw, outliers = obj.preprocess()
    pred_result = obj.run(raw=raw, outliers_for_train=outliers)
    long  = pred_result.loc[pred_result['pred'] >= pred_result['pred'].quantile(1-0.2)]
    short = pred_result.loc[pred_result['pred'] <= pred_result['pred'].quantile(0.2)]
    obj.execute_trade_logic(cand_long=long, cand_short=short)
    return {'result': 'test'}