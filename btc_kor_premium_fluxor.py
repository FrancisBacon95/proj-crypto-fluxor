import requests
import pandas as pd
from src.connection.slack import SlackClient
target_slug = 'bitcoin'
response = requests.get(f"https://api.coinmarketcap.com/data-api/v3/cryptocurrency/market-pairs/latest?slug={target_slug}&start=1&limit=100&category=spot&centerType=all&sort=cmc_rank_advanced&direction=desc&spotUntracked=true")
response.raise_for_status()

data = pd.DataFrame(response.json()['data']['marketPairs'])
binance = data.loc[data['exchangeName'].str.lower().isin(['binance']) & data['marketPair'].isin(['BTC/USDT']), 'price'].to_list()[0]
upbit = data.loc[data['exchangeName'].str.lower().isin(['upbit']) & data['marketPair'].isin(['BTC/KRW']), 'price'].to_list()[0]
result = (upbit - binance)/binance * 100

if result >= 2:
    title = f"🚨[FLUXOR-김프: {result:.2f}%]🚨"
    contents = f'*CRYPTO*: `{target_slug.upper()}`'
    SlackClient().chat_postMessage(title, contents)