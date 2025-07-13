# 모든 경고 무시
import logging
import time
import warnings
from datetime import datetime, timedelta

import pytz
from fastapi import FastAPI

from src.ctrend_model_v2 import CTRENDAllocator
from src.trader import execute_buy_logic, execute_sell_logic, sell_expired_crypto

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
sleep_sec = 30
kst = pytz.timezone("Asia/Seoul")
today = datetime.combine(datetime.now(tz=kst).date(), datetime.min.time())
app = FastAPI()


def run_strategy():
    args = {
        "train_size": 365 * 2,
        "inference_date": today - timedelta(days=1),
        "except_cryptos": ("KRW-BTC"),
    }
    obj = CTRENDAllocator(**args)
    sell_expired_crypto(target_date=today, expire_range=40)

    pred_result = obj.run()
    long = pred_result.loc[pred_result["pred"] >= pred_result["pred"].quantile(1 - 0.2)]
    short = pred_result.loc[pred_result["pred"] <= pred_result["pred"].quantile(0.2)]

    execute_sell_logic(cand_short=short, except_cryptos=args["except_cryptos"])
    logger.info(f"WAIT {str(sleep_sec)}sec. FOR SELLING SETTLEMENT")
    time.sleep(sleep_sec)
    execute_buy_logic(cand_long=long, except_cryptos=args["except_cryptos"])
    return {"result": "test"}


# health check
@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/run")
def run():
    return run_strategy()


if __name__ == "__main__":
    logger.info("로컬 단독 실행: 전략을 바로 실행합니다.")
    run_strategy()
    logger.info("로컬 전략 실행 완료")
