# 모든 경고 무시
import argparse
import os
import time
import warnings
from datetime import datetime, timedelta
from typing import Tuple

import pandas as pd
import pytz
from dotenv import load_dotenv

from src.config.helper import log_method_call
from src.connection.slack import SlackClient
from src.ctrend_model_v2 import CTRENDAllocator
from src.logger import get_logger
from src.trader import execute_buy_logic, execute_sell_logic, sell_expired_crypto
from src.upbit import get_accounts, post_market_buy_order

# -----------------------------------------------------------------------------
# Globals & Constants
# -----------------------------------------------------------------------------
logger = get_logger(__name__)
warnings.filterwarnings("ignore")

# KST 기준 로깅 설정
KST = pytz.timezone("Asia/Seoul")

SLEEP_SEC: int = 30
LONG_Q: float = 0.8  # 상위 20%
SHORT_Q: float = 0.2  # 하위 20%

# "오늘 00:00 KST" 기준일
TODAY = datetime.combine(datetime.now(tz=KST).date(), datetime.min.time())

load_dotenv()

# BTC_TRADE_UNIT .env에서 가져오기
BTC_TRADE_UNIT = int(os.getenv("BTC_TRADE_UNIT"))


def _quantile_long_short(
    df: pd.DataFrame,
    col: str = "pred",
    long_q: float = LONG_Q,
    short_q: float = SHORT_Q,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """예측 점수 기준으로 롱/숏 후보를 분리한다.
    - long: 상위 (1 - short_q) 이상
    - short: 하위 short_q 이하
    빈 DF에 대해서는 빈 DF를 반환.
    """
    if df is None or df.empty:
        return df, df

    # 경계값 계산
    long_thr = df[col].quantile(long_q)
    short_thr = df[col].quantile(short_q)

    long = df.loc[df[col] >= long_thr]
    short = df.loc[df[col] <= short_thr]
    return long, short


def _slack_notify(title: str, contents: str) -> None:
    """슬랙 메시지 전송 래퍼."""
    try:
        SlackClient().chat_postMessage(title, contents)
    except Exception as e:
        logger.error(f"Slack notify failed: {e}")


def _strategy_common_args() -> dict:
    """전략 공통 파라미터."""
    return {
        "train_size": 365 * 2,
        "inference_date": TODAY - timedelta(days=1),
        # 주의: 단일 원소 튜플은 쉼표 필수
        "except_cryptos": ("KRW-BTC",),
    }


@log_method_call
def run_strategy() -> dict:
    """전략 실행의 공통 코어 함수.

    Args:
        test: 실제 매수/매도/만기청산 수행 여부
    Returns:
        dict: 간단 실행 결과
    """
    args = _strategy_common_args()
    obj = CTRENDAllocator(**args)

    # 실거래 모드에서만 만기 청산
    sell_expired_crypto(target_date=TODAY, expire_range=40)

    # 예측 수행
    pred_result = obj.run()

    # 롱/숏 후보 분리
    long, short = _quantile_long_short(
        pred_result, col="pred", long_q=LONG_Q, short_q=SHORT_Q
    )

    # 실거래 모드에서는 매도 → 대기 → 매수
    execute_sell_logic(cand_short=short, except_cryptos=args["except_cryptos"])
    logger.info(f"WAIT {SLEEP_SEC} sec FOR SELLING SETTLEMENT")
    time.sleep(SLEEP_SEC)
    execute_buy_logic(cand_long=long, except_cryptos=args["except_cryptos"])

    # 결과 요약 슬랙 전송
    title = "🟠[BITHUMB-ML기반 자동 투자: 완료]🟠"

    contents = f"*매수 종목 개수*: `{len(long)}`\n*매도 종목 개수*: `{len(short)}`\n"
    _slack_notify(title, contents)

    return {"result": "ok", "n_long": int(len(long)), "n_short": int(len(short))}


@log_method_call
def accumulate_btc() -> None:
    """업비트 KRW 잔고 확인 후, BTC 적립식 시장가 매수 수행."""
    # 업비트 계좌(잔고) 조회
    accounts = pd.DataFrame(get_accounts())
    if accounts.empty or "currency" not in accounts.columns:
        _slack_notify(
            "🚨[UPBIT-BTC 전용 계좌: 조회 실패]🚨",
            "*계좌 조회 실패:* 응답이 비어있습니다.",
        )
        return

    krw_rows = accounts.loc[accounts["currency"] == "KRW"]
    if krw_rows.empty:
        _slack_notify(
            "🚨[UPBIT-BTC 전용 계좌: 잔고 경고]🚨", "*KRW 잔고를 찾을 수 없습니다.*"
        )
        return

    krw_account = krw_rows.to_dict(orient="records")[0]
    try:
        krw_balance = float(krw_account.get("balance", 0))
    except (TypeError, ValueError):
        krw_balance = 0.0

    logger.info(f"현재 KRW 잔고: {krw_balance}원")

    if krw_balance <= BTC_TRADE_UNIT:
        title = "🚨[UPBIT-BTC 전용 계좌: 잔고 경고]🚨"
        contents = (
            f"*KRW 잔고*: `{krw_balance:,.0f}원`\n"
            f"*설정 거래 단위*: `{BTC_TRADE_UNIT:,.0f}원`\n"
            "거래소에 입금해 주세요."
        )
        _slack_notify(title, contents)
        return

    market = "KRW-BTC"
    logger.info(f"{market} 적립식 시장가 매수: {BTC_TRADE_UNIT}원")

    before_balance = krw_balance
    try:
        result = post_market_buy_order(market, BTC_TRADE_UNIT)
        logger.info(result)
    except Exception as e:
        _slack_notify("🚨[UPBIT-BTC 전용 계좌: 매수 실패]🚨", f"*에러*: ```{str(e)}```")
        return

    title = "🔵[UPBIT-BTC 전용 계좌: 적립식 매수 성공]🔵"
    contents = (
        f"*마켓*: `{market}`\n"
        f"*매수 금액*: `{BTC_TRADE_UNIT:,.0f}원`\n"
        f"*거래 직전 KRW 잔고*: `{before_balance:,.0f}원`\n"
        f"*API 응답*: ```{result}```"
    )
    _slack_notify(title, contents)


@log_method_call
def run() -> None:
    """메인 런북: 전략 실행 → BTC 적립식."""
    current_time = datetime.now(tz=KST).strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"현재 시점을 로깅합니다.: {current_time}")

    # 1) 전략 실행
    try:
        run_strategy(test=args.test)
        logger.info("run_strategy() 성공")
    except Exception as e:
        logger.error(f"run_strategy() 실패: {e}")
        _slack_notify(
            "🚨[BITHUMB-ML기반 자동 투자: 실패]🚨",
            f"*에러 메시지*: ```{str(e)}```\n*시간*: `{current_time}`",
        )

    # 2) BTC 적립식
    try:
        accumulate_btc()
        logger.info("accumulate_btc() 성공")
    except Exception as e:
        logger.error(f"accumulate_btc() 실패: {e}")
        _slack_notify(
            "🚨[UPBIT-BTC 적립식 매수: 실패]🚨",
            f"*에러 메시지*: ```{str(e)}```\n*시간*: `{current_time}`",
        )
    logger.info("전체 실행 완료")


def test():
    args = _strategy_common_args()
    _slack_notify(
        "🟡[BITHUMB-ML기반 자동 투자: 테스트]🟡", "테스트 시작 계정 연결 이전"
    )
    obj = CTRENDAllocator(**args)

    title = "🟡[BITHUMB-ML기반 자동 투자: 테스트]🟡"
    pred_result = obj.run()
    # 롱/숏 후보 분리
    long, short = _quantile_long_short(
        pred_result, col="pred", long_q=LONG_Q, short_q=SHORT_Q
    )

    contents = f"*매수 종목 개수*: `{len(long)}`\n*매도 종목 개수*: `{len(short)}`\n"
    _slack_notify(title, contents)

    return {"result": "ok", "n_long": int(len(long)), "n_short": int(len(short))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="암호화폐 자동 투자 시스템")
    parser.add_argument(
        "--test",
        action="store_true",
        help="실제 투자 로직을 실행 (기본: True)",
        default=False,
    )

    args = parser.parse_args()
    if args.test:
        run()
    else:
        test()
