"""
자산
• 전체 계좌 조회
    → get_accounts

⸻

주문
• 주문 가능 정보 조회
    → get_order_chance
• 개별 주문 조회
    → get_order
• id로 주문리스트 조회
    → get_orders_by_id
• 체결 대기 주문 조회
    → get_open_orders
• 종료된 주문 조회
    → get_closed_orders
• 주문 취소 접수
    → delete_order
• 주문 일괄 취소 접수
    → delete_all_orders
• id로 주문리스트 취소 접수
    → delete_orders_by_id
• 주문하기
    → post_order
• 취소 후 재주문
    → post_replace_order
"""

import hashlib
import logging
import os
import uuid
from urllib.parse import unquote, urlencode

import jwt
import requests
from dotenv import load_dotenv

from src.connection.bigquery import get_bq_conn

load_dotenv()

logger = logging.getLogger(__name__)
headers = {"accept": "application/json"}
bq_conn = get_bq_conn()

server_url = "https://api.upbit.com"
access_key = os.environ["UPBIT_KEY"]
secret_key = os.environ["UPBIT_SECRET"]


def _make_auth_headers(payload: dict) -> dict:
    jwt_token = jwt.encode(payload, secret_key)
    authorization = f"Bearer {jwt_token}"
    return {"Authorization": authorization}


def _make_query_hash(params: dict) -> str:
    query_string = unquote(urlencode(params, doseq=True)).encode("utf-8")
    m = hashlib.sha512()
    m.update(query_string)
    return m.hexdigest()


def get_accounts():
    payload = {
        "access_key": access_key,
        "nonce": str(uuid.uuid4()),
    }
    headers = _make_auth_headers(payload)
    res = requests.get(server_url + "/v1/accounts", headers=headers)
    return res.json()


def post_order(
    market: str, side: str, ord_type: str, price: float = None, volume: float = None
):
    params = {
        "market": market,
        "side": side,
        "ord_type": ord_type,
    }
    if price is not None:
        params["price"] = str(price)
    if volume is not None:
        params["volume"] = str(volume)

    query_hash = _make_query_hash(params)
    payload = {
        "access_key": access_key,
        "nonce": str(uuid.uuid4()),
        "query_hash": query_hash,
        "query_hash_alg": "SHA512",
    }
    headers = _make_auth_headers(payload)
    res = requests.post(server_url + "/v1/orders", json=params, headers=headers)
    return res.json()


def post_market_buy_order(market: str, price: float):
    """
    시장가 매수 (ord_type='price', side='bid', price만 필수)
    """
    return post_order(market=market, side="bid", ord_type="price", price=price)


def post_market_sell_order(market: str, volume: float):
    """
    시장가 매도 (ord_type='market', side='ask', volume만 필수)
    """
    return post_order(
        market=market, side="ask", ord_type="market", price=None, volume=volume
    )


def post_deposit_krw(amount: int, two_factor_type: str = "naver"):
    params = {
        "amount": str(amount),
        "two_factor_type": two_factor_type,
    }
    query_hash = _make_query_hash(params)
    payload = {
        "access_key": access_key,
        "nonce": str(uuid.uuid4()),
        "query_hash": query_hash,
        "query_hash_alg": "SHA512",
    }
    headers = _make_auth_headers(payload)
    res = requests.post(server_url + "/v1/deposits/krw", json=params, headers=headers)
    return res.json()
