import ccxt
import os
import pandas as pd
import time
from datetime import datetime
import traceback
from dotenv import load_dotenv

# =========================
# Utils (replace with your own logger)
# =========================
def create_log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

load_dotenv()

# =========================
# Config
# =========================
symbol = 'BTC/USDT:USDT'   # ❗ futures symbol
timeframe = '15m'
risk = 0.01                # 1% risk ต่อไม้ (ปรับตามจริง)
leverage = 10              # แนะนำ 5–10x

last_candle = None
last_trade_candle = None

# =========================
# Exchange
# =========================
exchange = ccxt.binance({
    'apiKey': os.getenv('BINANCE_REAL_API_KEY'),
    'secret': os.getenv('BINANCE_REAL_API_SECRET'),
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',
    }
})

exchange.load_markets()
exchange.set_leverage(leverage, symbol)
create_log(f"Leverage set {leverage}x")

# =========================
# Safe order
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
# Position
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

# =========================
# Position size (correct)
# =========================
def position_size(balance, entry, sl):
    stop_distance = abs(entry - sl)
    if stop_distance == 0:
        return None

    risk_amount = balance * risk

    # ✅ Futures formula
    size_crypto = risk_amount / stop_distance

    market = exchange.market(symbol)
    min_amount = market['limits']['amount']['min']

    # ❗ ถ้าเล็กเกิน → skip trade (รักษา risk)
    if size_crypto < min_amount:
        create_log(f"SKIP: size {size_crypto:.6f} < min {min_amount}")
        return None

    size = exchange.amount_to_precision(symbol, size_crypto)
    return float(size)

# =========================
# Orders
# =========================
def open_position(side, amount):
    order = safe_order(exchange.create_order,
        symbol=symbol,
        type='market',
        side=side,
        amount=amount
    )

    if not order:
        return None

    # ✅ เช็ค fill
    if order.get('status') != 'closed':
        create_log("Order not filled")
        return None

    return order

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
        'timestamp','open','high','low','close','volume'
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
# Main loop
# =========================
while True:
    try:
        balance = exchange.fetch_balance()['USDT']['free']

        df = prepare(load_data())
        row = df.iloc[-2]
        candle_time = row['datetime']

        if candle_time == last_candle:
            time.sleep(5)
            continue

        last_candle = candle_time

        position = fetch_position()

        trend_up = row['ema9'] > row['ema200']
        trend_down = row['ema9'] < row['ema200']
        vol_ok = row['atr'] > row['atr_mean']

        if position == 0:

            if last_trade_candle == candle_time:
                continue

            # ================= LONG =================
            if trend_up and vol_ok:
                entry = row['close']
                sl = row['swing_low'] - row['atr']
                tp = entry + (entry - sl) * 1.5

                sl = float(exchange.price_to_precision(symbol, sl))
                tp = float(exchange.price_to_precision(symbol, tp))

                amount = position_size(balance, entry, sl)
                if not amount:
                    continue

                order = open_position('buy', amount)
                if not order:
                    continue

                create_log(f"LONG @ {entry} | SL {sl} | TP {tp}")

                place_sl('sell', sl)
                place_tp('sell', tp)

                last_trade_candle = candle_time

            # ================= SHORT =================
            elif trend_down and vol_ok:
                entry = row['close']
                sl = row['swing_high'] + row['atr']
                tp = entry - (sl - entry) * 1.5

                sl = float(exchange.price_to_precision(symbol, sl))
                tp = float(exchange.price_to_precision(symbol, tp))

                amount = position_size(balance, entry, sl)
                if not amount:
                    continue

                order = open_position('sell', amount)
                if not order:
                    continue

                create_log(f"SHORT @ {entry} | SL {sl} | TP {tp}")

                place_sl('buy', sl)
                place_tp('buy', tp)

                last_trade_candle = candle_time

        time.sleep(60)

    except Exception as e:
        create_log(traceback.format_exc())
        time.sleep(10)