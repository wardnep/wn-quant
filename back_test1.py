# EMA9 ตัด EMA200
# SL ที่ swing long/high
# RR 1:1.5

import pandas as pd
import numpy as np

# === LOAD DATA ===
df = pd.read_csv("./csv/BTCUSDT_15m.csv")
df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
df = df.sort_values('timestamp').reset_index(drop=True)

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
lookback = 20
df['swing_low'] = df['low'].rolling(lookback).min()
df['swing_high'] = df['high'].rolling(lookback).max()

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

    # === PROGRESS ===
    if i % 10000 == 0:
        percent = (i / total_rows) * 100
        print(f"⏳ {percent:.2f}% | index {i}/{total_rows} | balance {balance:.2f}")

    # === EXIT ===
    if position == 1:
        if row['low'] <= sl:
            pnl = -risk_per_trade
            balance *= (1 + pnl)
            trades.append(pnl)
            position = 0
            print(f"❌ SL LONG @ {row['datetime']} | balance {balance:.2f}")

        elif row['high'] >= tp:
            pnl = risk_per_trade * 1.5
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
            pnl = risk_per_trade * 1.5
            balance *= (1 + pnl)
            trades.append(pnl)
            position = 0
            print(f"✅ TP SHORT @ {row['datetime']} | balance {balance:.2f}")

    # === ENTRY ===
    if position == 0:
        if row['signal'] == 1:
            entry = row['close']
            sl = row['swing_low'] - row['atr']

            if pd.isna(sl):
                continue

            tp = entry + (entry - sl) * 1.5
            position = 1

            print(f"🟢 BUY @ {row['datetime']} | entry {entry:.2f} | sl {sl:.2f} | tp {tp:.2f}")

        elif row['signal'] == -1:
            entry = row['close']
            sl = row['swing_high'] + row['atr']

            if pd.isna(sl):
                continue

            tp = entry - (sl - entry) * 1.5
            position = -1

            print(f"🔴 SELL @ {row['datetime']} | entry {entry:.2f} | sl {sl:.2f} | tp {tp:.2f}")

# === FORCE CLOSE ===
if position != 0:
    print("⚠️ Force close at end")
    position = 0

# === RESULT ===
total_trades = len(trades)
winrate = len([t for t in trades if t > 0]) / total_trades * 100 if total_trades else 0

print("\n==== RESULT ====")
print(f"Balance: {balance:.2f}")
print(f"Trades: {total_trades}")
print(f"Winrate: {winrate:.2f}%")
