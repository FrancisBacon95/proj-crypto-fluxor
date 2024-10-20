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
# 문자열을 datetime으로 변환 & UTC에서 KST로 변환
data['last_updated'] = pd.to_datetime(data['last_updated'], utc=True).dt.tz_convert('Asia/Seoul')

for _c in ['tags', 'platform', 'quote']:
    data[_c] = data[_c].astype(str)

data["total_supply"] = pd.to_numeric(data['total_supply'])

conn.upsert(data, table_id='crypto_market_cap_1d', data_set='crypto_fluxor', target_dict={'reg_date': reg_date})