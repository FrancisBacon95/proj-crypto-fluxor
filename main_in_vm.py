# 모든 경고 무시
import argparse
import logging
import os
import time
import warnings
from datetime import datetime, timedelta

import pandas as pd
import pytz
from dotenv import load_dotenv

from src.config.helper import log_method_call
from src.connection.slack import SlackClient
from src.ctrend_model_v2 import CTRENDAllocator
from src.logger import get_logger
from src.trader import execute_buy_logic, execute_sell_logic, sell_expired_crypto
from src.upbit import get_accounts, post_market_buy_order

logger = get_logger(__name__)

warnings.filterwarnings("ignore")

# KST 기준 로깅 설정
kst = pytz.timezone("Asia/Seoul")

sleep_sec = 30
today = datetime.combine(datetime.now(tz=kst).date(), datetime.min.time())

load_dotenv()
# BTC_TRADE_UNIT .env에서 가져오기
BTC_TRADE_UNIT = int(os.getenv("BTC_TRADE_UNIT"))


@log_method_call
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

    # 매수/매도 종목 개수 및 종목명 슬랙 메시지 전송
    title = "🟠[BITHUMB-ML기반 자동 투자: 완료]🟠"
    contents = f"*매수 종목 개수*: `{len(long)}`\n*매도 종목 개수*: `{len(short)}`\n"
    SlackClient().chat_postMessage(title, contents)

    return {"result": "test"}


@log_method_call
def accumulate_btc():
    # 업비트 계좌(잔고) 조회 및 적립식 비트코인 매수
    accounts = get_accounts()
    accounts = pd.DataFrame(accounts)
    krw_account = accounts[accounts["currency"] == "KRW"].to_dict(orient="records")[0]
    krw_balance = float(krw_account["balance"])

    logger.info(f"현재 KRW 잔고: {krw_balance}원")
    if krw_balance <= BTC_TRADE_UNIT:
        title = "🚨[UPBIT-BTC 전용 계좌: 잔고 경고]🚨"
        contents = f"*KRW 잔고*: `{krw_balance:,.0f}원`\n*설정 거래 단위*: `{BTC_TRADE_UNIT:,.0f}원`\n거래소에 입금해 주세요."
        SlackClient().chat_postMessage(title, contents)
    else:
        market = "KRW-BTC"
        logger.info(f"{market} 적립식 시장가 매수: {BTC_TRADE_UNIT}원")
        before_balance = krw_balance
        result = post_market_buy_order(market, BTC_TRADE_UNIT)
        logger.info(result)
        title = "🔵[UPBIT-BTC 전용 계좌: 적립식 매수 성공]🔵"
        contents = (
            f"*마켓*: `{market}`\n"
            f"*매수 금액*: `{BTC_TRADE_UNIT:,.0f}원`\n"
            f"*거래 직전 KRW 잔고*: `{before_balance:,.0f}원`\n"
            f"*API 응답*: ```{result}```"
        )
        SlackClient().chat_postMessage(title, contents)


@log_method_call
def run():
    # 현재 날짜 및 시간 로깅(KST)
    current_time = datetime.now(tz=kst).strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"현재 시점을 로깅합니다.: {current_time}")

    # run_strategy() 실행
    try:
        run_strategy()
        logger.info("run_strategy() 성공")
    except Exception as e:
        logger.error(f"run_strategy() 실패: {e}")
        title = "🚨[BITHUMB-ML기반 자동 투자: 실패]🚨"
        contents = f"*에러 메시지*: ```{str(e)}```\n*시간*: `{current_time}`"
        SlackClient().chat_postMessage(title, contents)

    # accumulate_btc() 실행
    try:
        accumulate_btc()
        logger.info("accumulate_btc() 성공")
    except Exception as e:
        logger.error(f"accumulate_btc() 실패: {e}")
        title = "🚨[UPBIT-BTC 적립식 매수: 실패]🚨"
        contents = f"*에러 메시지*: ```{str(e)}```\n*시간*: `{current_time}`"
        SlackClient().chat_postMessage(title, contents)

    logger.info("전체 실행 완료")


@log_method_call
def send_test_message():
    """서버 테스트 메시지를 슬랙으로 전송"""
    current_time = datetime.now(tz=kst).strftime("%Y-%m-%d %H:%M:%S")
    title = "🧪[서버 테스트 중]🧪"
    contents = (
        f"*시간*: `{current_time}`\n*메시지*: `모든 투자 로직이 비활성화되어 있습니다.`"
    )
    SlackClient().chat_postMessage(title, contents)
    logger.info(f"서버 테스트 메시지 전송 완료: {current_time}")
    return {"status": "test_message_sent", "time": current_time}


@log_method_call
def main(is_test: bool = False):
    """
    메인 실행 함수

    Args:
        is_test (bool): 테스트 모드 여부. True이면 테스트 메시지만 전송, False이면 실제 로직 실행
    """
    if is_test:
        logger.info("테스트 모드로 실행합니다.")
        send_test_message()
    else:
        logger.info("실제 투자 로직을 실행합니다.")
        run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="암호화폐 자동 투자 시스템")
    parser.add_argument(
        "--test",
        action="store_true",
        help="테스트 모드로 실행 (실제 투자 로직 대신 테스트 메시지만 전송)",
        default=False,
    )

    args = parser.parse_args()
    main(is_test=args.test)
