"""
analyze_session_performance.py
================================
โหลด xauusd_m15_raw.csv (จาก export_xauusd_tvdatafeed.py) แล้ว:
  1) แปลง timezone -> Bangkok time
  2) แท็ก session (Asia / London / NY / Overlap)
  3) สร้าง Heikin Ashi + EMA9/EMA200 signal (ตามที่จำโครงจาก xauusd-alert.py)
  4) รัน backtest แบบง่าย (fixed RR) แล้วสรุปสถิติแยกตาม session

*** สำคัญ ***
signal_generation() ด้านล่างเป็นการ "จำลอง" logic EMA9/EMA200 cross + slope
ตามที่เคยคุยกันไว้ (Signal 1/2/3) แต่ผมไม่มี source code ตัวจริงของ
xauusd-alert.py อยู่ตรงหน้า ดังนั้นก่อนเชื่อผลลัพธ์ 100%
ให้เทียบ logic ในฟังก์ชันนี้กับของจริงในบอทคุณก่อน แล้วแก้ให้ตรงกัน
ไม่งั้นตัวเลข win rate/expectancy ที่ได้จะไม่ reflect ระบบจริงของคุณ
"""

import pandas as pd
import numpy as np

# ----------------------------
# 0) โหลดข้อมูล
# ----------------------------
df = pd.read_csv("xauusd_m15_raw.csv", parse_dates=["datetime"])
df = df.sort_values("datetime").reset_index(drop=True)

# ปรับ timezone ตรงนี้ให้ตรงกับที่ tvDatafeed คืนมาจริง
# สมมติว่า raw เป็น UTC -> แปลงเป็น Asia/Bangkok (UTC+7)
if df["datetime"].dt.tz is None:
    df["datetime"] = df["datetime"].dt.tz_localize("UTC")
df["datetime_bkk"] = df["datetime"].dt.tz_convert("Asia/Bangkok")
df["hour_bkk"] = df["datetime_bkk"].dt.hour

# ----------------------------
# 1) แท็ก session ตามเวลา Bangkok (UTC+7)
# ----------------------------
# กรอบเวลาอ้างอิง (คร่าวๆ, ปรับได้ตามที่คุณยึดถือ):
#   Asia       : 06:00 - 14:00 BKK  (Tokyo/Sydney overlap ส่วนใหญ่)
#   London     : 14:00 - 20:00 BKK
#   NY         : 19:30 - 04:00 BKK (ข้ามเที่ยงคืน)
#   Overlap LN/NY : 19:30 - 23:00 BKK (ใช้เป็นช่วงที่ volume หนาสุด)
def tag_session(hour: int) -> str:
    if 6 <= hour < 14:
        return "Asia"
    elif 14 <= hour < 19:
        return "London"
    elif 19 <= hour < 23:
        return "London_NY_Overlap"
    else:
        return "NY"

df["session"] = df["hour_bkk"].apply(tag_session)

# ----------------------------
# 2) Heikin Ashi
# ----------------------------
ha_close = (df["open"] + df["high"] + df["low"] + df["close"]) / 4
ha_open = [(df["open"].iloc[0] + df["close"].iloc[0]) / 2]
for i in range(1, len(df)):
    ha_open.append((ha_open[i - 1] + ha_close.iloc[i - 1]) / 2)
ha_open = pd.Series(ha_open, index=df.index)

df["ha_close"] = ha_close
df["ha_open"] = ha_open
df["ha_high"] = df[["high", "ha_open", "ha_close"]].max(axis=1)
df["ha_low"] = df[["low", "ha_open", "ha_close"]].min(axis=1)

# ----------------------------
# 3) EMA9 / EMA200 บน HA close + slope ของ EMA200
# ----------------------------
df["ema9"] = df["ha_close"].ewm(span=9, adjust=False).mean()
df["ema200"] = df["ha_close"].ewm(span=200, adjust=False).mean()

# slope แบบ atan-normalized (มุมเป็น radian ของการเปลี่ยนแปลง ema200 เทียบ pip)
df["ema200_slope"] = np.arctan(df["ema200"].diff())

# ----------------------------
# 4) สร้าง signal แบบง่าย: EMA9 cross EMA200 + slope confirm
#    ใช้แท่งที่ปิดแล้ว (iloc[-2] logic) -> ในบริบท backtest คือ shift(1)
# ----------------------------
df["ema9_prev"] = df["ema9"].shift(1)
df["ema200_prev"] = df["ema200"].shift(1)

cross_up = (df["ema9_prev"] < df["ema200_prev"]) & (df["ema9"] > df["ema200"])
cross_down = (df["ema9_prev"] > df["ema200_prev"]) & (df["ema9"] < df["ema200"])

slope_up = df["ema200_slope"] > 0
slope_down = df["ema200_slope"] < 0

df["long_signal"] = cross_up & slope_up
df["short_signal"] = cross_down & slope_down

# ----------------------------
# 5) Backtest แบบง่าย: fixed RR 1:1.5, SL = ATR-based
# ----------------------------
atr_period = 14
tr = pd.concat([
    df["high"] - df["low"],
    (df["high"] - df["close"].shift(1)).abs(),
    (df["low"] - df["close"].shift(1)).abs(),
], axis=1).max(axis=1)
df["atr"] = tr.rolling(atr_period).mean()

RR = 1.5
SL_ATR_MULT = 1.5

trades = []
for i in range(len(df)):
    row = df.iloc[i]
    if pd.isna(row["atr"]):
        continue

    if row["long_signal"]:
        entry = row["close"]
        sl = entry - SL_ATR_MULT * row["atr"]
        tp = entry + SL_ATR_MULT * row["atr"] * RR
        direction = "long"
    elif row["short_signal"]:
        entry = row["close"]
        sl = entry + SL_ATR_MULT * row["atr"]
        tp = entry - SL_ATR_MULT * row["atr"] * RR
        direction = "short"
    else:
        continue

    # เดิน forward หา TP/SL โดนก่อน (แบบง่าย ไม่คิด spread/slippage)
    result = None
    for j in range(i + 1, min(i + 200, len(df))):  # จำกัด lookahead 200 แท่ง
        future = df.iloc[j]
        if direction == "long":
            if future["low"] <= sl:
                result = -1.0
                break
            if future["high"] >= tp:
                result = RR
                break
        else:
            if future["high"] >= sl:
                result = -1.0
                break
            if future["low"] <= tp:
                result = RR
                break

    if result is not None:
        trades.append({
            "datetime": row["datetime_bkk"],
            "session": row["session"],
            "direction": direction,
            "r_multiple": result,
        })

trades_df = pd.DataFrame(trades)

if trades_df.empty:
    print("ไม่มี trade เกิดขึ้นเลย เช็ค signal logic หรือช่วงข้อมูลอีกที")
else:
    # ----------------------------
    # 6) สรุปสถิติแยกตาม session
    # ----------------------------
    def summarize(group: pd.DataFrame) -> pd.Series:
        n = len(group)
        wins = (group["r_multiple"] > 0).sum()
        losses = (group["r_multiple"] < 0).sum()
        win_rate = wins / n if n > 0 else np.nan
        expectancy = group["r_multiple"].mean()
        gross_win = group.loc[group["r_multiple"] > 0, "r_multiple"].sum()
        gross_loss = -group.loc[group["r_multiple"] < 0, "r_multiple"].sum()
        profit_factor = gross_win / gross_loss if gross_loss > 0 else np.nan
        return pd.Series({
            "n_trades": n,
            "win_rate_%": round(win_rate * 100, 1),
            "expectancy_R": round(expectancy, 3),
            "profit_factor": round(profit_factor, 2),
        })

    summary = trades_df.groupby("session").apply(summarize)
    overall = summarize(trades_df)
    overall.name = "ALL"

    print("\n=== สรุปผลแยกตาม Session ===")
    print(summary)
    print("\n=== ภาพรวมทั้งหมด ===")
    print(overall)

    trades_df.to_csv("session_trades_detail.csv", index=False)
    summary.to_csv("session_summary.csv")
    print("\nเซฟรายละเอียด trade -> session_trades_detail.csv")
    print("เซฟสรุปตาม session -> session_summary.csv")
