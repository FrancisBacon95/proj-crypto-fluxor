import pytz
import pandas as pd
from datetime import datetime
from src.coinmarketcap import CoinMarketCapClient
from src.connection.bigquery import BigQueryConn

cur = datetime.now(pytz.timezone('Asia/Seoul'))
reg_date = pd.to_datetime(cur.date())

conn = BigQueryConn()
client = CoinMarketCapClient()
data = client.listing_latest()
data['reg_date'] = reg_date

conn.upsert(data, table_id='coin_marketcap', data_set='crypto_fluxor', target_dict={'reg_date': reg_date})