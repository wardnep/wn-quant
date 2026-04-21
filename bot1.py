import pandas as pd
import numpy as np
import sqlite3

# ==============================
# === DATABASE SETUP ===========
# ==============================
conn = sqlite3.connect("trading.db")
cursor = conn.cursor()

cursor.execute("""
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
""")
conn.commit()

# ==============================
# === LOAD DATA ================
# ==============================
df = pd.read_csv("./csv/BTCUSDT_5m.csv")
df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
df = df.sort_values('timestamp').reset_index(drop=True)

# ==============================
# === HEIKIN ASHI ==============
# ==============================
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

# ==============================
# === INDICATORS ===============
# ==============================
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

# ==============================
# === BACKTEST =================
# ==============================
balance = 1000
risk = 0.01

position = 0
entry = sl = tp = None
entry_time = None

trades = []

total_rows = len(df)

for i in range(total_rows):
    row = df.iloc[i]

    # skip NaN
    if pd.isna(row['atr']) or pd.isna(row['swing_low']):
        continue

    # === PROGRESS ===
    if i % 1000 == 0 or i == total_rows - 1:
        percent = (i / total_rows) * 100
        status = "LONG" if position == 1 else "SHORT" if position == -1 else "FLAT"

        print(
            f"⏳ {percent:6.2f}% | bal={balance:8.2f} | pos={status} | trades={len(trades)}",
            end="\r",
            flush=True
        )

    # ==================
    # === EXIT =========
    # ==================
    exit_price = None

    if position == 1:
        if row['low'] <= sl:
            pnl = -risk
            exit_price = sl

        elif row['high'] >= tp:
            pnl = risk * 1.5
            exit_price = tp

        else:
            pnl = None

        if pnl is not None:
            balance *= (1 + pnl)
            trades.append(pnl)

            # === LOG DB ===
            cursor.execute("""
            INSERT INTO trades (datetime, symbol, side, entry, sl, tp, exit, pnl)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(row['datetime']),
                "BTCUSDT",
                "LONG",
                entry,
                sl,
                tp,
                exit_price,
                pnl
            ))

            position = 0

    elif position == -1:
        if row['high'] >= sl:
            pnl = -risk
            exit_price = sl

        elif row['low'] <= tp:
            pnl = risk * 1.5
            exit_price = tp

        else:
            pnl = None

        if pnl is not None:
            balance *= (1 + pnl)
            trades.append(pnl)

            cursor.execute("""
            INSERT INTO trades (datetime, symbol, side, entry, sl, tp, exit, pnl)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(row['datetime']),
                "BTCUSDT",
                "SHORT",
                entry,
                sl,
                tp,
                exit_price,
                pnl
            ))

            position = 0

    # ==================
    # === ENTRY ========
    # ==================
    if position == 0:

        trend_up = row['ema9'] > row['ema200']
        trend_down = row['ema9'] < row['ema200']

        vol_ok = row['atr'] > row['atr_mean']

        bullish = row['ha_close'] > row['ha_open']
        bearish = row['ha_close'] < row['ha_open']

        if trend_up and bullish and vol_ok:
            entry = row['close']
            sl = row['swing_low'] - row['atr']
            tp = entry + (entry - sl) * 1.5
            entry_time = row['datetime']
            position = 1

        elif trend_down and bearish and vol_ok:
            entry = row['close']
            sl = row['swing_high'] + row['atr']
            tp = entry - (sl - entry) * 1.5
            entry_time = row['datetime']
            position = -1

# commit ครั้งเดียว
conn.commit()

# ==============================
# === RESULT ===================
# ==============================
total = len(trades)
winrate = len([t for t in trades if t > 0]) / total * 100 if total else 0

print("\n==== RESULT ====")
print(f"Balance: {balance:.2f}")
print(f"Trades: {total}")
print(f"Winrate: {winrate:.2f}%")

# ==============================
# === LOAD FROM DB ============
# ==============================
df_trades = pd.read_sql("SELECT * FROM trades", conn)

print("\n==== DB SUMMARY ====")
print("Total trades:", len(df_trades))
print("Winrate:", (df_trades['pnl'] > 0).mean() * 100)

conn.close()
