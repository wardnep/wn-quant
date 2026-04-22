# เช็กว่ามี position ค้างอยู่หรือไม่
# ยิง stop loss / take profit อัตโนมัติ
# กันเปิด order ซ้ำ
# กัน bot restart แล้วลืม position เดิม
# จัดการ minimum order size
# ใช้ Binance Futures Testnet ก่อน
# เพิ่ม logging ลง database ทุก order
# เช็กเวลาปิดแท่งจริงก่อนเข้าออเดอร์
# เพิ่ม notification ผ่าน Line หรือ Telegram

import time
import sqlite3
import pandas as pd
import numpy as np
import ccxt

# ==============================
# === BINANCE CONFIG ===========
# ==============================
exchange = ccxt.binance({
    'apiKey': 'YOUR_API_KEY',
    'secret': 'YOUR_SECRET_KEY',
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future'
    }
})

exchange.set_sandbox_mode(True)

symbol = 'BTC/USDT'
timeframe = '5m'
risk = 0.01
balance = 1000
position = 0
entry = sl = tp = None

# ==============================
# === DATABASE SETUP ===========
# ==============================
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    datetime TEXT,
    symbol TEXT,
    side TEXT,
    entry REAL,
    sl REAL,
    tp REAL,
    exit REAL,
    pnl REAL
)
''')
conn.commit()

# ==============================
# === HEIKIN ASHI ==============
# ==============================
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

# ==============================
# === LOAD MARKET DATA =========
# ==============================
def load_data():
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=300)

    df = pd.DataFrame(ohlcv, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume'
    ])

    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

    return df

# ==============================
# === INDICATORS ===============
# ==============================
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

# ==============================
# === POSITION SIZE ============
# ==============================
def calculate_size(balance, entry, sl, risk_percent):
    risk_amount = balance * risk_percent
    stop_distance = abs(entry - sl)

    if stop_distance == 0:
        return 0

    size = risk_amount / stop_distance
    return round(size, 3)

# ==============================
# === PLACE ORDER ==============
# ==============================
def open_long(amount):
    return exchange.create_order(
        symbol=symbol,
        type='market',
        side='buy',
        amount=amount,
        params={
            'positionSide': 'LONG'
        }
    )


def open_short(amount):
    return exchange.create_order(
        symbol=symbol,
        type='market',
        side='sell',
        amount=amount,
        params={
            'positionSide': 'SHORT'
        }
    )

# ==============================
# === MAIN LOOP ================
# ==============================
while True:
    try:
        df = load_data()
        df = prepare_dataframe(df)

        row = df.iloc[-1]

        if pd.isna(row['atr']) or pd.isna(row['atr_mean']):
            time.sleep(10)
            continue

        trend_up = row['ema9'] > row['ema200']
        trend_down = row['ema9'] < row['ema200']

        bullish = row['ha_close'] > row['ha_open']
        bearish = row['ha_close'] < row['ha_open']

        vol_ok = row['atr'] > row['atr_mean']

        if position == 0:

            if trend_up and bullish and vol_ok:
                entry = row['close']
                sl = row['swing_low'] - row['atr']
                tp = entry + (entry - sl) * 1.5

                amount = calculate_size(balance, entry, sl, risk)

                if amount > 0:
                    open_long(amount)
                    position = 1

                    print(f'LONG | entry={entry:.2f} sl={sl:.2f} tp={tp:.2f}')

            elif trend_down and bearish and vol_ok:
                entry = row['close']
                sl = row['swing_high'] + row['atr']
                tp = entry - (sl - entry) * 1.5

                amount = calculate_size(balance, entry, sl, risk)

                if amount > 0:
                    open_short(amount)
                    position = -1

                    print(f'SHORT | entry={entry:.2f} sl={sl:.2f} tp={tp:.2f}')

        time.sleep(60)

    except Exception as e:
        print('ERROR:', e)
        time.sleep(10)
