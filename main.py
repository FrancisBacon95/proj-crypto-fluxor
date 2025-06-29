import warnings
# 모든 경고 무시
import logging
import time
import pandas as pd
import pytz
from datetime import datetime, timedelta
from src.ctrend_model_v2 import CTRENDAllocator
from src.trader import execute_sell_logic, execute_buy_logic, sell_expired_crypto
from fastapi import FastAPI
warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)
sleep_sec = 30
kst = pytz.timezone('Asia/Seoul')
today = datetime.combine(datetime.now(tz=kst).date(), datetime.min.time())
app = FastAPI()
# health check
@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get('/run')
def run():
    args = {
        'train_size': 365*2,
        'inference_date': today - timedelta(days=1),
        'except_cryptos': ('KRW-BTC'),
    }
    obj = CTRENDAllocator(**args)
    sell_expired_crypto(target_date=today, expire_range=40)

    pred_result = obj.run()

    long  = pred_result.loc[pred_result['pred'] >= pred_result['pred'].quantile(1-0.2)]
    short = pred_result.loc[pred_result['pred'] <= pred_result['pred'].quantile(0.2)]

    execute_sell_logic(cand_short=short, except_cryptos=args['except_cryptos'])
    logger.info(f'WAIT {str(sleep_sec)}sec. FOR SELLING SETTLEMENT')
    time.sleep(sleep_sec)
    execute_buy_logic(cand_long=long, except_cryptos=args['except_cryptos'])
    return {'result': 'test'}