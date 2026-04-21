# Trend: EMA (จาก Heikin-Ashi)
# Entry: pullback + confirmation
# SL: structure (swing + ATR)
# RR: 1:1.5 – 1:2
# Filter: volatility + session

import pandas as pd
import numpy as np

# === LOAD DATA ===
df = pd.read_csv("./csv/PAXGUSDT_15m.csv")
print(len(df))
df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
df = df.sort_values('timestamp').reset_index(drop=True)

# === HEIKIN ASHI ===
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

# === EMA ===
df['ema9'] = df['ha_close'].ewm(span=9).mean()
df['ema200'] = df['ha_close'].ewm(span=200).mean()

# === ATR ===
df['tr'] = np.maximum.reduce([
    df['high'] - df['low'],
    abs(df['high'] - df['close'].shift(1)),
    abs(df['low'] - df['close'].shift(1))
])
df['atr'] = df['tr'].rolling(14).mean()
df['atr_mean'] = df['atr'].rolling(50).mean()

# === SWING ===
lookback = 10
df['swing_low'] = df['low'].rolling(lookback).min()
df['swing_high'] = df['high'].rolling(lookback).max()

# === BACKTEST ===
balance = 1000
risk = 0.01

position = 0
entry = sl = tp = None

trades = []

total_rows = len(df)

for i in range(total_rows):
    row = df.iloc[i]

    # === PROGRESS (อัปเดตบรรทัดเดียว) ===
    if i % 1000 == 0 or i == total_rows - 1:
        percent = (i / total_rows) * 100

        status = "LONG" if position == 1 else "SHORT" if position == -1 else "FLAT"

        print(
            f"⏳ {percent:6.2f}% | i={i}/{total_rows} | bal={balance:8.2f} | pos={status} | trades={len(trades)}",
            end="\r",
            flush=True
        )

    # skip
    if pd.isna(row['atr']) or pd.isna(row['swing_low']):
        continue

    # === EXIT ===
    if position == 1:
        if row['low'] <= sl:
            pnl = -risk
            balance *= (1 + pnl)
            trades.append(pnl)
            position = 0

        elif row['high'] >= tp:
            pnl = risk * 1.5
            balance *= (1 + pnl)
            trades.append(pnl)
            position = 0

    elif position == -1:
        if row['high'] >= sl:
            pnl = -risk
            balance *= (1 + pnl)
            trades.append(pnl)
            position = 0

        elif row['low'] <= tp:
            pnl = risk * 1.5
            balance *= (1 + pnl)
            trades.append(pnl)
            position = 0

    # === ENTRY ===
    if position == 0:

        trend_up = row['ema9'] > row['ema200']
        trend_down = row['ema9'] < row['ema200']

        vol_ok = row['atr'] > row['atr_mean']

        # HA direction
        bullish = row['ha_close'] > row['ha_open']
        bearish = row['ha_close'] < row['ha_open']

        # === LONG ===
        if trend_up and bullish and vol_ok:
            entry = row['close']
            sl = row['swing_low'] - row['atr']

            if pd.isna(sl):
                continue

            tp = entry + (entry - sl) * 1.5
            position = 1

        # === SHORT ===
        elif trend_down and bearish and vol_ok:
            entry = row['close']
            sl = row['swing_high'] + row['atr']

            if pd.isna(sl):
                continue

            tp = entry - (sl - entry) * 1.5
            position = -1

# === RESULT ===
total = len(trades)
winrate = len([t for t in trades if t > 0]) / total * 100 if total else 0

print("==== RESULT ====")
print(f"Balance: {balance:.2f}")
print(f"Trades: {total}")
print(f"Winrate: {winrate:.2f}%")
