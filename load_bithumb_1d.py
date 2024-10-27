import pytz
from datetime import datetime, date, timedelta
import pandas as pd
from src.bithumb import BithumbClient
cur = datetime.now(pytz.timezone('Asia/Seoul'))
reg_date = pd.to_datetime(cur.date())

client = BithumbClient()

enable_cryptos = client.enable_cryptos_by_date(target_date=reg_date, threshold=570)
raw = client.get_raw_data_1d(target_cryptos=enable_cryptos['market'], target_date=reg_date)
client.bq_conn.upsert(
    df=raw,
    table_id='bithumb_crypto_1d',
    data_set='crypto_fluxor',
    target_dict={'reg_date': reg_date}
)
