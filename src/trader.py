import pytz
import time
from collections import defaultdict
import logging
from datetime import date, datetime, timedelta
import pandas as pd
from src.bithumb import get_bithumb_client
from src.connection.bigquery import get_bq_conn
logger = logging.getLogger(__name__)
RANDOM_STATE = 950223
kst = pytz.timezone('Asia/Seoul')
bq_conn = get_bq_conn()
bithumb_client = get_bithumb_client()

def execute_sell_logic(cand_short: pd.DataFrame, except_cryptos: tuple):
    # 1) SHORT TARGETs 매도
    # account_df의 shape, columns 프린트
    if cand_short.empty:
        logger.info('No SHORT targets to sell.')
        exit(0)
    
    account_df = bithumb_client.get_account_info().rename(columns={'currency': 'symbol'})

    sell_targets = account_df.merge(cand_short, on='symbol', how='inner')[['market', 'balance']].reset_index(drop=True)
    for i in sell_targets.index:
        _market, _balance =  sell_targets.at[i, 'market'], sell_targets.at[i, 'balance']
        if _market in except_cryptos:
            continue
        logger.info(f'SELL(ask) market(시장가) - {_market}:{ _balance}')
        bithumb_client.exceute_order(type='sell', market=_market, volume=_balance, ord_type='market')


def execute_buy_logic(cand_long: pd.DataFrame, except_cryptos: tuple):
    # 2) SHORT TARGETs 매도 후, 정산 결과를 포함하여 예산 측정
    account_df = bithumb_client.get_account_info().rename(columns={'currency': 'symbol'})
    budget = int(account_df.loc[account_df['symbol'] == 'KRW', 'balance'].to_list()[0])
    
    each_budget = budget / len(cand_long) 
    each_budget = int(each_budget / 1000) * 1000
    logger.info(f'BUTGET: {each_budget} (total={budget})')
    # 3) LONG TARGETs 매수
    for _market in cand_long['market']:
        if _market in except_cryptos:
            continue
        logger.info(f'BUY(bid) price(시장가) - {_market}:{each_budget}')
        bithumb_client.exceute_order(type='buy', market=_market, price=each_budget, ord_type='price')

    return 1

def sell_expired_crypto(target_date: datetime, expire_range: int):
    target_date_str = target_date.strftime('%Y-%m-%d')
    # 기준일자 (40일 이전) 계산
    cutoff_date = target_date - timedelta(days=expire_range)
    
    # BigQuery에서 거래 내역 조회 (매수/매도 포함), created_at은 타임존 고려해 변환
    trade_log = bq_conn.query(f"""
    DECLARE target_date DATETIME DEFAULT '{target_date_str}';
    SELECT 
        uuid,
        type,
        market,
        SAFE_CAST(JSON_VALUE(data, '$.executed_volume') AS FLOAT64) AS executed_volume,
        DATETIME(PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%S%Ez', JSON_VALUE(data, '$.created_at')), 'Asia/Seoul') AS created_at,
        update_dt
    FROM `proj-asset-allocation.crypto_fluxor.trade_history`
    ORDER BY created_at ASC
    """)

    # datetime 타입으로 변환
    trade_log['created_at'] = pd.to_datetime(trade_log['created_at'])
    trade_log['update_dt'] = pd.to_datetime(trade_log['update_dt'])

    # market별로 남은 매수 잔량을 기록할 dict (FIFO 기준)
    holdings = defaultdict(dict)

    # 거래 내역을 순회하며 holdings 계산
    for _, row in trade_log.iterrows():
        market = row['market']
        created_at = row['created_at']
        volume = row['executed_volume']

        if row['type'] == 'buy':
            # 매수 건은 그대로 보유량에 추가
            holdings[market][created_at] = holdings[market].get(created_at, 0) + volume

        elif row['type'] == 'sell':
            # 매도일 경우, 이전 매수 건에서 FIFO 방식으로 차감
            remaining = volume
            for buy_time in sorted(holdings[market].keys()):
                if buy_time >= created_at:
                    continue  # 미래 매수는 건너뜀

                available = holdings[market][buy_time]
                deduct = min(remaining, available)  # 차감할 수 있는 양 계산
                holdings[market][buy_time] -= deduct
                remaining -= deduct

                if holdings[market][buy_time] == 0:
                    # 0이 된 매수는 제거
                    del holdings[market][buy_time]

                if remaining <= 0:
                    break  # 더 이상 차감할 필요 없음

            # 해당 market에 남은 매수가 없으면 market 자체 삭제
            if len(holdings[market]) == 0:
                del holdings[market]

    # 40일 이상 보유된 매수 내역만 티커별로 합산
    filtered_holdings = defaultdict(float)
    for market, buys in holdings.items():
        for created_at, volume in buys.items():
            if created_at < cutoff_date:
                filtered_holdings[market] += volume

    filtered_holdings_df = pd.DataFrame([
        {'market': market, 'volume': volume}
        for market, volume in filtered_holdings.items()
    ])

    account = bithumb_client.get_account_info()
    account['market'] = account['unit_currency'] + '-' + account['currency']

    # sell_volume 기준으로 account와 병합
    merged = account.merge(
        filtered_holdings_df.rename(columns={'volume': 'sell_volume'}),
        how='inner',
        on='market'
    )

    # 잔여 수량 계산
    merged['sell_volume'] = merged['sell_volume'].astype(float)
    merged['balance'] = merged['balance'].astype(float)
    merged['remain_volume'] = merged['balance'] - merged['sell_volume']

    for _, row in merged.loc[merged['remain_volume'] > 0].iterrows():
            market = row['market']
            rebalance_vol = row['remain_volume']
            try:
                bithumb_client.exceute_order(type='sell', market=market, ord_type='market', volume=rebalance_vol)
            except Exception as e:
                logging.error(f"Error executing sell order for {market}: {e}")