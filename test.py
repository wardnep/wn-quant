import ccxt
import pandas as pd

exchange = ccxt.binance()

ohlcv = exchange.fetch_ohlcv('PAXG/USDT', timeframe='1m', limit=100)

df = pd.DataFrame(ohlcv, columns=[
    'time', 'open', 'high', 'low', 'close', 'volume'
])

df['ma'] = df['close'].rolling(20).mean()

print(ohlcv)
print(df)
