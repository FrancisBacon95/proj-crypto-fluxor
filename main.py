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
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: run()")
    kst = pytz.timezone('Asia/Seoul')
    today = datetime.combine(datetime.now(tz=kst).date(), datetime.min.time())

    args = {
        'train_size': 365*2,
        'inference_date': today - timedelta(days=1),
        'except_cryptos': ('KRW-BTC'),
    }
    obj = CTRENDAllocator(**args)
    logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: obj")
    raw, outliers = obj.preprocess()
    logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: raw, outliers")
    long, short = obj.run(raw=raw, outliers_for_train=outliers)
    obj.execute_trade_logic(cand_long=long, cand_short=short)
    return {'result': 'test'}

@app.get("/ip")
def get_ip():
    import requests
    response = requests.get("https://ifconfig.me")
    return {"ip": response.text}