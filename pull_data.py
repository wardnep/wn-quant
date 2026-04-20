import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta

# === CONFIG ===
exchange = ccxt.binance({
    'enableRateLimit': True
})

symbol = 'PAXG/USDT'
days_back = 1000

start_date = datetime.now() - timedelta(days=days_back)
start_timestamp = int(start_date.timestamp() * 1000)


def fetch_all_ohlcv(tf, filename):
    print(f"\n📥 โหลดข้อมูล Timeframe: {tf} ย้อนหลัง {days_back} วัน จาก Binance ...")

    all_ohlcv = []
    since = start_timestamp

    while True:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, tf, since=since, limit=1000)

            if not ohlcv:
                break

            all_ohlcv.extend(ohlcv)

            since = ohlcv[-1][0] + 1

            current_date_str = datetime.fromtimestamp(
                ohlcv[-1][0] / 1000
            ).strftime('%Y-%m-%d')

            print(f"⏳ โหลดมาแล้ว {len(all_ohlcv):,} แท่ง ถึง {current_date_str}")

            time.sleep(0.2)

            # stop ถ้าถึงปัจจุบัน
            if ohlcv[-1][0] >= int(time.time() * 1000) - (60 * 1000):
                break

        except Exception as e:
            print(f"❌ Error: {e} → retry ใน 5 วิ")
            time.sleep(5)

    # === CREATE DATAFRAME ===
    df = pd.DataFrame(
        all_ohlcv,
        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
    )

    # convert time
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

    # remove duplicates
    df = df.drop_duplicates(subset='timestamp')

    # sort
    df = df.sort_values('timestamp')

    # save file
    df.to_csv(filename, index=False)

    print(f"\n✅ บันทึกไฟล์เรียบร้อย: {filename} ({len(df):,} rows)")


# === RUN ===
if __name__ == "__main__":
    fetch_all_ohlcv('5m', 'PAXGUSDT_5m.csv')
    fetch_all_ohlcv('15m', 'PAXGUSDT_15m.csv')
    fetch_all_ohlcv('1h', 'PAXGUSDT_1h.csv')
