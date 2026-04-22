import ccxt
from orders import (
    open_long,
    open_short,
    place_long_sl,
    place_long_tp
)
from config import API_KEY, API_SECRET

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

symbol = 'BTC/USDT'
amount = 0.001
sl_price = 70000
tp_price = 90000

open_long(exchange, symbol, amount)
place_long_sl(exchange, symbol, amount, sl_price)
place_long_tp(exchange, symbol, amount, tp_price)
