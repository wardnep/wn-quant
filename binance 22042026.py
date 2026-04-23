import ccxt
import numpy as np
import os
import pandas as pd
import time
from flask import Flask, jsonify
import threading
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
from utils.orders import (
    open_long,
    open_short,
    place_sl,
    place_tp
)
from utils.log import (
    create_log
)

load_dotenv()

symbol = 'BTC/USDT'
timeframe = '15m'
risk = 0.01
position = 0

def heikin_ashi(df):
    ha = df.copy()

    ha['ha_close'] = (
        df['open'] +
        df['high'] +
        df['low'] +
        df['close']
    ) / 4

    ha_open = [
        (df['open'].iloc[0] + df['close'].iloc[0]) / 2
    ]

    for i in range(1, len(df)):
        ha_open.append(
            (ha_open[i - 1] + ha['ha_close'].iloc[i - 1]) / 2
        )

    ha['ha_open'] = ha_open
    ha['ha_high'] = ha[['high', 'ha_open', 'ha_close']].max(axis=1)
    ha['ha_low'] = ha[['low', 'ha_open', 'ha_close']].min(axis=1)

    return ha

def load_data():
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=300)

    df = pd.DataFrame(ohlcv, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume'
    ])

    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

    return df

def prepare_dataframe(df):
    df = heikin_ashi(df)

    df['ema9'] = df['ha_close'].ewm(span=9).mean()
    df['ema200'] = df['ha_close'].ewm(span=200).mean()

    df['tr'] = np.maximum.reduce([
        df['high'] - df['low'],
        abs(df['high'] - df['close'].shift(1)),
        abs(df['low'] - df['close'].shift(1))
    ])

    df['atr'] = df['tr'].rolling(14).mean()
    df['atr_mean'] = df['atr'].rolling(50).mean()

    lookback = 10
    df['swing_low'] = df['low'].rolling(lookback).min()
    df['swing_high'] = df['high'].rolling(lookback).max()

    return df

###########################################################################
# Health Check
###########################################################################

app = Flask(__name__)

bot_status = {
    "running": True,
    "last_heartbeat": time.time(),
    "position": 0
}

@app.route("/status")
def status():
    return jsonify(bot_status)

def run_api():
    app.run(host="0.0.0.0", port=5000)

threading.Thread(target=run_api, daemon=True).start()

###########################################################################
# Binance Connect
###########################################################################

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

###########################################################################
# Position Sizing
###########################################################################

balances = exchange.fetch_balance()
balance = balances['USDT']['free']

def position_size(balance, entry, sl, risk):
    risk_amount = balance * risk
    stop_distance = abs(entry - sl)

    if stop_distance == 0:
        return 0

    size = risk_amount / stop_distance
    return round(size, 3)

###########################################################################
# Running
###########################################################################

last_candle_time = None

while True:
    try:
        ts = time.time()
        bot_status["last_heartbeat"] = datetime.fromtimestamp(
            ts, tz=timezone(timedelta(hours=7))
        ).strftime("%Y-%m-%d %H:%M:%S")
        bot_status["position"] = position

        df = load_data()
        df = prepare_dataframe(df)

        row = df.iloc[-2]
        current_candle_time = row['datetime']

        if last_candle_time == current_candle_time:
            time.sleep(5)
            continue

        last_candle_time = current_candle_time

        if pd.isna(row['atr']) or pd.isna(row['atr_mean']):
            time.sleep(10)
            continue

        trend_up = row['ema9'] > row['ema200']
        trend_down = row['ema9'] < row['ema200']

        bullish = row['ha_close'] > row['ha_open']
        bearish = row['ha_close'] < row['ha_open']

        vol_ok = row['atr'] > row['atr_mean']

        positions = exchange.fetch_positions(['BTC/USDT'])

        pos = positions[0]

        contracts = float(pos['contracts'])

        if contracts == 0:
            position = 0
        elif pos['side'] == 'long':
            position = 1
        elif pos['side'] == 'short':
            position = -1

        if position == 0:

            if trend_up and bullish and vol_ok:
                entry = row['close']
                sl = row['swing_low'] - row['atr']
                tp = entry + (entry - sl) * 1.5

                amount = position_size(balance, entry, sl, risk)

                if amount > 0:
                    open_long(exchange, symbol, amount)
                    place_sl(exchange, symbol, amount, sl, 'sell')
                    place_tp(exchange, symbol, amount, tp, 'sell')
                    position = 1

                    # create_log(print(f'LONG | entry={entry:.2f} sl={sl:.2f} tp={tp:.2f}'))
                    print(f'LONG | entry={entry:.2f} sl={sl:.2f} tp={tp:.2f}')

            elif trend_down and bearish and vol_ok:
                entry = row['close']
                sl = row['swing_high'] + row['atr']
                tp = entry - (sl - entry) * 1.5

                amount = position_size(balance, entry, sl, risk)

                if amount > 0:
                    open_short(exchange, symbol, amount)
                    place_sl(exchange, symbol, amount, sl, 'buy')
                    place_tp(exchange, symbol, amount, sl, 'buy')
                    position = -1

                    # create_log(print(f'SHORT | entry={entry:.2f} sl={sl:.2f} tp={tp:.2f}'))
                    print(f'SHORT | entry={entry:.2f} sl={sl:.2f} tp={tp:.2f}')

        time.sleep(60)

    except Exception as e:
        create_log(print('ERROR:', e))
        time.sleep(10)
