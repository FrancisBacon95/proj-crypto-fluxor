import pytz
import requests
from datetime import datetime, timedelta
import pandas as pd
from src.connection.slack import SlackClient
from src.connection.bigquery import BigQueryConn
from src.coinmarketcap import CoinMarketCapClient
kst = pytz.timezone('Asia/Seoul')
cur = datetime.now(tz=kst)
reg_date = cur.date()
result = CoinMarketCapClient().get_fear_and_greed_latest()
BigQueryConn().upsert(result, table_id='fear_and_greed', data_set='crypto_fluxor', target_dict={'reg_date': reg_date})