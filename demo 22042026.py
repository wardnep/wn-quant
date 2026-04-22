import ccxt
import os

from dotenv import load_dotenv
from orders import (
    open_long,
    open_short,
    place_long_sl,
    place_long_tp
)

load_dotenv()

API_KEY = os.getenv('BINANCE_DEMO_API_KEY')
API_SECRET = os.getenv('BINANCE_DEMO_API_SECRET')

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',
        'adjustForTimeDifference': True
    }
})

exchange.enable_demo_trading(True)

balance = exchange.fetch_balance()
usdt_balance = balance['USDT']['free']

symbol = 'BTC/USDT'
risk_percent = 0.01

entry_price = 75000
sl_price = 70000
tp_price = 90000

risk_amount = usdt_balance * risk_percent
stop_distance = abs(entry_price - sl_price)

amount = risk_amount / stop_distance

loss_if_sl = stop_distance * amount
profit_if_tp = abs(tp_price - entry_price) * amount
rr = profit_if_tp / loss_if_sl

# open_long(exchange, symbol, amount)
# place_long_sl(exchange, symbol, amount, sl_price)
# place_long_tp(exchange, symbol, amount, tp_price)

print(f'Balance: ${usdt_balance}')
print(f'Risk Amount: ${risk_amount:.2f}')
print(f'Entry: {entry_price}')
print(f'SL: {sl_price}')
print(f'TP: {tp_price}')
print(f'Amount: {amount:.6f} BTC')
print(f'Loss if SL: ${loss_if_sl:.2f}')
print(f'Profit if TP: ${profit_if_tp:.2f}')
print(f'RR: 1:{rr:.2f}')
