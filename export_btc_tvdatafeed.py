"""
Export BTC OHLCV from TradingView (via tvDatafeed) to a CSV for
btc_trend_backtest.py.

Run this on the same machine/venv where tvDatafeed is already installed
and working (same auth setup as xauusd-alert.py).

Usage:
    python export_btc_tvdatafeed.py --symbol BTCUSDT --exchange BINANCE \
        --interval 4h --n_bars 5000 --out btc_4h.csv

If your TradingView account needs login (like in xauusd-alert.py), set
TV_USERNAME / TV_PASSWORD as environment variables, or edit the
TvDatafeed(...) call below directly.
"""

import argparse
import os
import sys

try:
    from tvDatafeed import TvDatafeed, Interval
except ImportError:
    print("tvDatafeed is not installed in this environment.")
    print("Install it with: pip install --upgrade --no-cache-dir "
          "git+https://github.com/rongardF/tvdatafeed.git")
    sys.exit(1)

INTERVAL_MAP = {
    "1m": Interval.in_1_minute,
    "5m": Interval.in_5_minute,
    "15m": Interval.in_15_minute,
    "30m": Interval.in_30_minute,
    "1h": Interval.in_1_hour,
    "2h": Interval.in_2_hour,
    "4h": Interval.in_4_hour,
    "1d": Interval.in_daily,
    "1w": Interval.in_weekly,
}


def main():
    p = argparse.ArgumentParser(description="Export OHLCV from TradingView via tvDatafeed")
    p.add_argument("--symbol", default="BTCUSDT", help="e.g. BTCUSDT")
    p.add_argument("--exchange", default="BINANCE", help="e.g. BINANCE, COINBASE, BITSTAMP")
    p.add_argument("--interval", default="4h", choices=list(INTERVAL_MAP.keys()))
    p.add_argument("--n_bars", type=int, default=5000,
                   help="Number of bars to pull (tvDatafeed caps this per call, "
                        "usually ~5000 for intraday TFs on the free tier)")
    p.add_argument("--out", default="btc_4h.csv")
    args = p.parse_args()

    username = os.environ.get("TV_USERNAME")
    password = os.environ.get("TV_PASSWORD")

    print("Connecting to TradingView via tvDatafeed...")
    if username and password:
        tv = TvDatafeed(username=username, password=password)
    else:
        tv = TvDatafeed()  # anonymous session -- works for most symbols, may rate-limit sooner

    print(f"Fetching {args.n_bars} bars of {args.symbol} on {args.exchange} "
          f"({args.interval}) ...")
    df = tv.get_hist(
        symbol=args.symbol,
        exchange=args.exchange,
        interval=INTERVAL_MAP[args.interval],
        n_bars=args.n_bars,
    )

    if df is None or df.empty:
        print("No data returned. Check symbol/exchange spelling, or that this "
              "market exists on TradingView under that exchange code.")
        sys.exit(1)

    df = df.reset_index()  # brings the datetime index back as a column
    # tvDatafeed's default column name is 'datetime' already; keep only what we need
    keep_cols = [c for c in ["datetime", "open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[keep_cols]

    df.to_csv(args.out, index=False)
    print(f"Saved {len(df)} bars to {args.out}")
    print(f"Range: {df['datetime'].min()} -> {df['datetime'].max()}")

    if args.n_bars >= 5000:
        print("\nNote: tvDatafeed usually caps a single call around ~5000 bars.")
        print("For a longer history, run this multiple times shifting the end "
              "date, or stitch together several CSV exports before backtesting.")


if __name__ == "__main__":
    main()
