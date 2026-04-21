# Heikin-Ashi
# EMA9 ตัด EMA200
# SL ที่ swing long/high
# RR 1:1.5

import pandas as pd
import numpy as np

# === LOAD DATA ===
df = pd.read_csv("./csv/BTCUSDT_1h.csv")
df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
df = df.sort_values('timestamp').reset_index(drop=True)

# === HEIKIN-ASHI ===
def heikin_ashi(df):
    ha = df.copy()

    ha['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4

    ha_open = [(df['open'][0] + df['close'][0]) / 2]
    for i in range(1, len(df)):
        ha_open.append((ha_open[i-1] + ha['ha_close'][i-1]) / 2)

    ha['ha_open'] = ha_open
    ha['ha_high'] = ha[['high', 'ha_open', 'ha_close']].max(axis=1)
    ha['ha_low'] = ha[['low', 'ha_open', 'ha_close']].min(axis=1)

    return ha

df = heikin_ashi(df)

# === EMA (ใช้ HA) ===
df['ema9'] = df['ha_close'].ewm(span=9).mean()
df['ema200'] = df['ha_close'].ewm(span=200).mean()

# === SIGNAL ===
df['signal'] = 0
df.loc[(df['ema9'] > df['ema200']) & (df['ema9'].shift(1) <= df['ema200'].shift(1)), 'signal'] = 1
df.loc[(df['ema9'] < df['ema200']) & (df['ema9'].shift(1) >= df['ema200'].shift(1)), 'signal'] = -1

# === ATR (ใช้ HA) ===
df['high_low'] = df['ha_high'] - df['ha_low']
df['high_close'] = abs(df['ha_high'] - df['ha_close'].shift(1))
df['low_close'] = abs(df['ha_low'] - df['ha_close'].shift(1))
df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
df['atr'] = df['tr'].rolling(14).mean()

# === SWING (ใช้ HA) ===
lookback = 10
df['swing_low'] = df['ha_low'].rolling(lookback).min()
df['swing_high'] = df['ha_high'].rolling(lookback).max()

# === BACKTEST ===
balance = 1000
risk_per_trade = 0.01

position = 0
entry = sl = tp = None

trades = []

total_rows = len(df)

for i in range(total_rows):
    row = df.iloc[i]

    # === SKIP ถ้า indicator ยังไม่พร้อม ===
    if pd.isna(row['atr']) or pd.isna(row['swing_low']) or pd.isna(row['swing_high']):
        continue

    # === PROGRESS (บรรทัดเดียว) ===
    if i % 1000 == 0:
        percent = (i / total_rows) * 100
        print(f"⏳ {percent:.2f}% | balance {balance:.2f}", end="\r", flush=True)

    # === EXIT (ใช้ราคาจริง) ===
    if position == 1:
        if row['low'] <= sl:
            pnl = -risk_per_trade
            balance *= (1 + pnl)
            trades.append(pnl)
            position = 0

        elif row['high'] >= tp:
            pnl = risk_per_trade * 2
            balance *= (1 + pnl)
            trades.append(pnl)
            position = 0

    elif position == -1:
        if row['high'] >= sl:
            pnl = -risk_per_trade
            balance *= (1 + pnl)
            trades.append(pnl)
            position = 0

        elif row['low'] <= tp:
            pnl = risk_per_trade * 2
            balance *= (1 + pnl)
            trades.append(pnl)
            position = 0

    # === ENTRY (ใช้ signal จาก HA) ===
    if position == 0:
        if row['signal'] == 1:
            entry = row['close']  # ใช้ราคาจริง
            sl = row['swing_low'] - row['atr']

            if pd.isna(sl):
                continue

            tp = entry + (entry - sl) * 2
            position = 1

        elif row['signal'] == -1:
            entry = row['close']
            sl = row['swing_high'] + row['atr']

            if pd.isna(sl):
                continue

            tp = entry - (sl - entry) * 2
            position = -1

# === FORCE CLOSE ===
if position != 0:
    position = 0

# === RESULT ===
total_trades = len(trades)
winrate = len([t for t in trades if t > 0]) / total_trades * 100 if total_trades else 0

print("\n==== RESULT ====")
print(f"Balance: {balance:.2f}")
print(f"Trades: {total_trades}")
print(f"Winrate: {winrate:.2f}%")
