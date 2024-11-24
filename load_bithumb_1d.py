import pytz
from datetime import datetime, date, timedelta
import pandas as pd
from src.bithumb import BithumbClient
cur = datetime.now(pytz.timezone('Asia/Seoul'))
reg_date = pd.to_datetime(cur.date())

client = BithumbClient()
except_markets = ['KRW-NFT']
enable_cryptos = client.enable_cryptos_by_date(target_date=reg_date, threshold=570)
enable_cryptos = enable_cryptos.loc[enable_cryptos['market'].isin(except_markets)]

raw = client.get_raw_data_1d(target_cryptos=enable_cryptos['market'], target_date=reg_date)
client.bq_conn.upsert(
    df=raw,
    table_id='bithumb_crypto_1d',
    data_set='crypto_fluxor',
    target_dict={'reg_date': reg_date}
)

backfill_market_list = client.bq_conn.query('''
SELECT market
FROM `proj-asset-allocation.crypto_fluxor.bithumb_crypto_1d`
GROUP BY 1
HAVING COUNT(*) < 570
''')['market'].to_list()

for _m in backfill_market_list:
    df = client.backfill_data_1d(_m, reg_date, threshold=600)
    client.bq_conn.upsert(
        df=df,
        table_id='bithumb_crypto_1d', 
        data_set='crypto_fluxor', 
        target_dict={'market': _m}
    )