# EMA9 ตัดกับ EMA200
# SL ที่ swing low/high + ATR
# RR 1:2

import pandas as pd
import numpy as np

# === LOAD DATA ===
df = pd.read_csv("./csv/BTCUSDT_5m.csv")
df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
df = df.sort_values('timestamp')

# === EMA ===
df['ema9'] = df['close'].ewm(span=9).mean()
df['ema200'] = df['close'].ewm(span=200).mean()

# === SIGNAL ===
df['signal'] = 0
df.loc[(df['ema9'] > df['ema200']) & (df['ema9'].shift(1) <= df['ema200'].shift(1)), 'signal'] = 1
df.loc[(df['ema9'] < df['ema200']) & (df['ema9'].shift(1) >= df['ema200'].shift(1)), 'signal'] = -1

# === ATR ===
df['high_low'] = df['high'] - df['low']
df['high_close'] = np.abs(df['high'] - df['close'].shift(1))
df['low_close'] = np.abs(df['low'] - df['close'].shift(1))
df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
df['atr'] = df['tr'].rolling(14).mean()

# === SWING ===
lookback = 10
df['swing_low'] = df['low'].rolling(lookback).min()
df['swing_high'] = df['high'].rolling(lookback).max()

print(df[['ema9', 'ema200', 'signal', 'high_low', 'high_close', 'low_close', 'tr', 'atr']].tail())

# === BACKTEST ===
balance = 1000
risk_per_trade = 0.01

position = 0
entry = sl = tp = 0

trades = []

total_rows = len(df)

for i in range(total_rows):
    row = df.iloc[i]

    # === PROGRESS ทุก 10,000 แท่ง ===
    if i % 10000 == 0:
        percent = (i / total_rows) * 100
        print(f"⏳ {percent:.2f}% | index {i}/{total_rows} | balance {balance:.2f}")

    # === CHECK EXIT FIRST ===
    if position == 1:
        if row['low'] <= sl:
            pnl = -risk_per_trade
            balance *= (1 + pnl)
            trades.append(pnl)
            position = 0
            print(f"❌ SL LONG @ {row['datetime']} | balance {balance:.2f}")

        elif row['high'] >= tp:
            pnl = risk_per_trade * 2
            balance *= (1 + pnl)
            trades.append(pnl)
            position = 0
            print(f"✅ TP LONG @ {row['datetime']} | balance {balance:.2f}")

    elif position == -1:
        if row['high'] >= sl:
            pnl = -risk_per_trade
            balance *= (1 + pnl)
            trades.append(pnl)
            position = 0
            print(f"❌ SL SHORT @ {row['datetime']} | balance {balance:.2f}")

        elif row['low'] <= tp:
            pnl = risk_per_trade * 2
            balance *= (1 + pnl)
            trades.append(pnl)
            position = 0
            print(f"✅ TP SHORT @ {row['datetime']} | balance {balance:.2f}")

    # === ENTRY ===
    if position == 0:
        if row['signal'] == 1:
            entry = row['close']
            sl = row['swing_low'] - row['atr']
            tp = entry + (entry - sl) * 2
            position = 1
            print(f"🟢 BUY @ {row['datetime']} | entry {entry:.2f}")

        elif row['signal'] == -1:
            entry = row['close']
            sl = row['swing_high'] + row['atr']
            tp = entry - (sl - entry) * 2
            position = -1
            print(f"🔴 SELL @ {row['datetime']} | entry {entry:.2f}")

# === RESULT ===
total_trades = len(trades)
winrate = len([t for t in trades if t > 0]) / total_trades * 100 if total_trades else 0

print("\n==== RESULT ====")
print(f"Balance: {balance:.2f}")
print(f"Trades: {total_trades}")
print(f"Winrate: {winrate:.2f}%")
