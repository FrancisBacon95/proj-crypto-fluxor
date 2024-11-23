import pytz
import requests
from datetime import datetime, timedelta
import pandas as pd
from src.connection.slack import SlackClient
from src.connection.bigquery import BigQueryConn
kst = pytz.timezone('Asia/Seoul')
cur = datetime.now(tz=kst)
reg_date = cur.date()
reg_hour = cur.hour

target_slug = 'bitcoin'
response = requests.get(f"https://api.coinmarketcap.com/data-api/v3/cryptocurrency/market-pairs/latest?slug={target_slug}&start=1&limit=100&category=spot&centerType=all&sort=cmc_rank_advanced&direction=desc&spotUntracked=true")
response.raise_for_status()

data = pd.DataFrame(response.json()['data']['marketPairs'])
binance = data.loc[data['exchangeName'].str.lower().isin(['binance']) & data['marketPair'].isin(['BTC/USDT']), 'price'].to_list()[0]
upbit = data.loc[data['exchangeName'].str.lower().isin(['upbit']) & data['marketPair'].isin(['BTC/KRW']), 'price'].to_list()[0]
diff_per = (upbit - binance)/binance * 100

result_df = pd.DataFrame([{
    'diff_per': diff_per,
    'binance': binance,
    'upbit': upbit,
    'reg_date': reg_date,
    'reg_hour': reg_hour
}])
result_df['reg_date'] = pd.to_datetime(result_df['reg_date'])
if diff_per >= 2:
    title = f"🚨[FLUXOR-김프: {diff_per:.2f}%]🚨"
    contents = f'*CRYPTO*: `{target_slug.upper()}`'
    SlackClient().chat_postMessage(title, contents)

BigQueryConn().upsert(result_df, table_id='btc_diff_per', data_set='crypto_fluxor', target_dict={'reg_date': reg_date, 'reg_hour': reg_hour})