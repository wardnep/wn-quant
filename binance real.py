import ccxt
import os
import pandas as pd
import time
from datetime import datetime
import traceback
from dotenv import load_dotenv

from utils.log import create_log

load_dotenv()

symbol = 'BTC/USDT'
timeframe = '15m'
# risk = 0.005  # ✅ 0.5%
risk = 0.01  # ✅ 1%

last_candle = None
last_trade_candle = None

# =========================
# Binance Connect
# =========================
exchange = ccxt.binance({
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_API_SECRET'),
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',
    }
})

exchange.set_leverage(10, symbol)

# =========================
# Safe Order (Retry)
# =========================
def safe_order(func, *args, **kwargs):
    for _ in range(3):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            create_log(f"ORDER ERROR: {e}")
            time.sleep(1)
    return None

# =========================
# Position Sync
# =========================
def fetch_position():
    try:
        positions = exchange.fetch_positions([symbol])
        for p in positions:
            if p['symbol'] != symbol:
                continue

            contracts = float(p.get('contracts', 0))
            side = p.get('side')

            if contracts > 0:
                return 1 if side == 'long' else -1

        return 0
    except Exception as e:
        create_log(f"FETCH POSITION ERROR: {e}")
        return 0

def wait_for_position():
    for _ in range(5):
        if fetch_position() != 0:
            return True
        time.sleep(0.5)
    return False

# =========================
# Position Size
# =========================
def position_size(balance, entry, sl):
    stop_distance = abs(entry - sl)
    if stop_distance == 0:
        return 0

    risk_amount = balance * risk
    size_usd = risk_amount / stop_distance
    size_btc = size_usd / entry

    market = exchange.market(symbol)
    min_amount = market['limits']['amount']['min']

    if size_btc < min_amount:
        return 0

    size = exchange.amount_to_precision(symbol, size_btc)
    return float(size)

# =========================
# Orders
# =========================
def open_position(side, amount):
    return safe_order(exchange.create_order,
        symbol=symbol,
        type='market',
        side=side,
        amount=amount
    )

def place_sl(side, price):
    return safe_order(exchange.create_order,
        symbol=symbol,
        type='STOP_MARKET',
        side=side,
        amount=None,
        params={
            'stopPrice': price,
            'closePosition': True,
            'reduceOnly': True,
            'workingType': 'MARK_PRICE'
        }
    )

def place_tp(side, price):
    return safe_order(exchange.create_order,
        symbol=symbol,
        type='TAKE_PROFIT_MARKET',
        side=side,
        amount=None,
        params={
            'stopPrice': price,
            'closePosition': True,
            'reduceOnly': True,
            'workingType': 'MARK_PRICE'
        }
    )

# =========================
# Data
# =========================
def load_data():
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=300)
    df = pd.DataFrame(ohlcv, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume'
    ])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def prepare(df):
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema200'] = df['close'].ewm(span=200).mean()
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()
    df['atr_mean'] = df['atr'].rolling(50).mean()
    df['swing_low'] = df['low'].rolling(10).min()
    df['swing_high'] = df['high'].rolling(10).max()
    return df

# =========================
# Main Loop
# =========================
while True:
    try:
        balance = exchange.fetch_balance()['USDT']['free']

        df = load_data()
        df = prepare(df)

        row = df.iloc[-2]
        candle_time = row['datetime']

        if candle_time == last_candle:
            time.sleep(5)
            continue

        last_candle = candle_time

        position = fetch_position()

        if position != 0:
            create_log(f"Already in position: {position}")

        trend_up = row['ema9'] > row['ema200']
        trend_down = row['ema9'] < row['ema200']
        vol_ok = row['atr'] > row['atr_mean']

        if position == 0:

            if last_trade_candle == candle_time:
                continue

            # LONG
            if trend_up and vol_ok:
                entry = row['close']
                sl = row['swing_low'] - row['atr']
                tp = entry + (entry - sl) * 1.5

                amount = position_size(balance, entry, sl)

                if amount > 0:
                    order = open_position('buy', amount)
                    if not order:
                        continue

                    if not wait_for_position():
                        create_log("Position not opened")
                        continue

                    sl_order = place_sl('sell', sl)
                    tp_order = place_tp('sell', tp)

                    if not sl_order or not tp_order:
                        create_log("SL/TP failed")

                    create_log(f"LONG entry={entry} sl={sl} tp={tp}")
                    last_trade_candle = candle_time

            # SHORT
            elif trend_down and vol_ok:
                entry = row['close']
                sl = row['swing_high'] + row['atr']
                tp = entry - (sl - entry) * 1.5

                amount = position_size(balance, entry, sl)

                if amount > 0:
                    order = open_position('sell', amount)
                    if not order:
                        continue

                    if not wait_for_position():
                        create_log("Position not opened")
                        continue

                    sl_order = place_sl('buy', sl)
                    tp_order = place_tp('buy', tp)

                    if not sl_order or not tp_order:
                        create_log("SL/TP failed")

                    create_log(f"SHORT entry={entry} sl={sl} tp={tp}")
                    last_trade_candle = candle_time

        create_log(datetime.now())
        time.sleep(60)

    except Exception as e:
        create_log(traceback.format_exc())
        time.sleep(10)
