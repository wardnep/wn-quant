"""
BTC Trend-Following Backtest Engine (4H / Daily timeframe)
=============================================================
System logic:
  1. Trend filter : EMA_fast vs EMA_slow (default 50/200) on the same TF
  2. Entry trigger: Pullback to EMA_pullback (default 20) + RSI reversal
                     in the direction of the trend
  3. Risk/Reward  : ATR-based stop loss, fixed R:R take profit
  4. Exit         : SL / TP / optional time-based exit (max_bars_in_trade)

Input:  CSV with columns [datetime, open, high, low, close, volume]
        (TradingView export or Binance klines CSV both work — see
         `load_csv()` for column auto-detection)

Output: Trade log CSV, equity curve PNG, and a printed statistics summary
        (win rate, expectancy in R, profit factor, max drawdown in R,
         trades/month, breakdown by year for regime comparison)

Usage:
    python btc_trend_backtest.py --csv BTCUSDT_4h.csv \
        --ema_fast 50 --ema_slow 200 --ema_pullback 20 \
        --rsi_period 14 --atr_period 14 --atr_mult 1.5 --rr 2.0 \
        --max_bars 40 --risk_pct 1.0
"""

import argparse
import numpy as np
import pandas as pd
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


# ----------------------------------------------------------------------
# Data loading
# ----------------------------------------------------------------------
def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    dt_col = next((c for c in df.columns if c in
                   ("datetime", "date", "time", "timestamp", "open time")), None)
    if dt_col is None:
        raise ValueError("Could not find a datetime/timestamp column in CSV")

    if pd.api.types.is_numeric_dtype(df[dt_col]):
        unit = "ms" if df[dt_col].iloc[0] > 1e12 else "s"
        df["datetime"] = pd.to_datetime(df[dt_col], unit=unit)
    else:
        df["datetime"] = pd.to_datetime(df[dt_col])

    rename_map = {}
    for target, aliases in {
        "open": ["open"], "high": ["high"], "low": ["low"],
        "close": ["close"], "volume": ["volume", "vol"]
    }.items():
        for a in aliases:
            if a in df.columns:
                rename_map[a] = target
                break

    df = df.rename(columns=rename_map)
    keep = ["datetime", "open", "high", "low", "close"]
    if "volume" in df.columns:
        keep.append("volume")
    df = df[keep].sort_values("datetime").drop_duplicates("datetime").reset_index(drop=True)
    return df


# ----------------------------------------------------------------------
# Indicators
# ----------------------------------------------------------------------
def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def add_indicators(df: pd.DataFrame, ema_fast, ema_slow, ema_pullback,
                    rsi_period, atr_period) -> pd.DataFrame:
    df = df.copy()
    df["ema_fast"] = ema(df["close"], ema_fast)
    df["ema_slow"] = ema(df["close"], ema_slow)
    df["ema_pullback"] = ema(df["close"], ema_pullback)
    df["rsi"] = rsi(df["close"], rsi_period)
    df["atr"] = atr(df, atr_period)
    df["trend"] = np.where(df["ema_fast"] > df["ema_slow"], 1,
                    np.where(df["ema_fast"] < df["ema_slow"], -1, 0))
    return df


# ----------------------------------------------------------------------
# Signal generation
# Long setup:  trend == 1, price pulls back near ema_pullback,
#              RSI crosses up from <45 (reversal out of pullback zone)
# Short setup: mirror image
# ----------------------------------------------------------------------
def generate_signals(df: pd.DataFrame, rsi_long_th=45, rsi_short_th=55,
                      pullback_atr_dist=1.0) -> pd.DataFrame:
    df = df.copy()
    near_ema_long = (df["low"] <= df["ema_pullback"] + pullback_atr_dist * df["atr"])
    near_ema_short = (df["high"] >= df["ema_pullback"] - pullback_atr_dist * df["atr"])

    rsi_cross_up = (df["rsi"].shift(1) < rsi_long_th) & (df["rsi"] >= rsi_long_th)
    rsi_cross_down = (df["rsi"].shift(1) > rsi_short_th) & (df["rsi"] <= rsi_short_th)

    df["long_signal"] = (df["trend"] == 1) & near_ema_long & rsi_cross_up
    df["short_signal"] = (df["trend"] == -1) & near_ema_short & rsi_cross_down
    return df


# ----------------------------------------------------------------------
# Backtest engine (bar-by-bar, one position at a time)
# ----------------------------------------------------------------------
def run_backtest(df: pd.DataFrame, atr_mult=1.5, rr=2.0, max_bars=40,
                  risk_pct=1.0, starting_equity=10000.0):
    trades = []
    equity = starting_equity
    equity_curve = []
    position = None

    for i in range(len(df)):
        row = df.iloc[i]
        equity_curve.append({"datetime": row["datetime"], "equity": equity})

        if position is not None:
            bars_held = i - position["entry_idx"]
            exit_price, exit_reason = None, None

            if position["side"] == 1:
                if row["low"] <= position["sl"]:
                    exit_price, exit_reason = position["sl"], "SL"
                elif row["high"] >= position["tp"]:
                    exit_price, exit_reason = position["tp"], "TP"
            else:
                if row["high"] >= position["sl"]:
                    exit_price, exit_reason = position["sl"], "SL"
                elif row["low"] <= position["tp"]:
                    exit_price, exit_reason = position["tp"], "TP"

            if exit_price is None and bars_held >= max_bars:
                exit_price, exit_reason = row["close"], "TIME"

            if exit_price is not None:
                r_multiple = (exit_price - position["entry"]) / position["risk_per_unit"] \
                    if position["side"] == 1 else \
                    (position["entry"] - exit_price) / position["risk_per_unit"]
                pnl = r_multiple * (risk_pct / 100) * starting_equity
                equity += pnl
                trades.append({
                    "entry_time": position["entry_time"],
                    "exit_time": row["datetime"],
                    "side": "LONG" if position["side"] == 1 else "SHORT",
                    "entry": position["entry"],
                    "exit": exit_price,
                    "sl": position["sl"],
                    "tp": position["tp"],
                    "bars_held": bars_held,
                    "r_multiple": r_multiple,
                    "pnl": pnl,
                    "exit_reason": exit_reason,
                })
                position = None
            continue

        if row.get("long_signal", False):
            risk_per_unit = atr_mult * row["atr"]
            entry = row["close"]
            position = {
                "side": 1, "entry": entry, "entry_idx": i,
                "entry_time": row["datetime"],
                "sl": entry - risk_per_unit,
                "tp": entry + risk_per_unit * rr,
                "risk_per_unit": risk_per_unit,
            }
        elif row.get("short_signal", False):
            risk_per_unit = atr_mult * row["atr"]
            entry = row["close"]
            position = {
                "side": -1, "entry": entry, "entry_idx": i,
                "entry_time": row["datetime"],
                "sl": entry + risk_per_unit,
                "tp": entry - risk_per_unit * rr,
                "risk_per_unit": risk_per_unit,
            }

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_curve)
    return trades_df, equity_df


# ----------------------------------------------------------------------
# Statistics
# ----------------------------------------------------------------------
def compute_stats(trades_df: pd.DataFrame, equity_df: pd.DataFrame) -> dict:
    if trades_df.empty:
        return {"error": "No trades generated — loosen entry conditions or check data."}

    wins = trades_df[trades_df["r_multiple"] > 0]
    losses = trades_df[trades_df["r_multiple"] <= 0]

    win_rate = len(wins) / len(trades_df) * 100
    avg_win_r = wins["r_multiple"].mean() if len(wins) else 0
    avg_loss_r = losses["r_multiple"].mean() if len(losses) else 0
    expectancy_r = trades_df["r_multiple"].mean()
    gross_win = wins["r_multiple"].sum()
    gross_loss = abs(losses["r_multiple"].sum())
    profit_factor = gross_win / gross_loss if gross_loss > 0 else np.inf

    cum_r = trades_df["r_multiple"].cumsum()
    running_max = cum_r.cummax()
    drawdown_r = running_max - cum_r
    max_dd_r = drawdown_r.max()

    days_span = (trades_df["exit_time"].max() - trades_df["entry_time"].min()).days
    months_span = max(days_span / 30.44, 1)
    trades_per_month = len(trades_df) / months_span

    trades_df["year"] = pd.to_datetime(trades_df["entry_time"]).dt.year
    by_year = trades_df.groupby("year")["r_multiple"].agg(
        trades="count", total_r="sum", win_rate=lambda x: (x > 0).mean() * 100
    )

    return {
        "total_trades": len(trades_df),
        "win_rate_pct": round(win_rate, 2),
        "avg_win_R": round(avg_win_r, 3),
        "avg_loss_R": round(avg_loss_r, 3),
        "expectancy_R": round(expectancy_r, 3),
        "profit_factor": round(profit_factor, 3),
        "total_R": round(trades_df["r_multiple"].sum(), 2),
        "max_drawdown_R": round(max_dd_r, 2),
        "recovery_factor": round(trades_df["r_multiple"].sum() / max_dd_r, 2) if max_dd_r > 0 else np.inf,
        "trades_per_month": round(trades_per_month, 2),
        "final_equity": round(equity_df["equity"].iloc[-1], 2),
        "by_year": by_year,
    }


def plot_equity(equity_df: pd.DataFrame, trades_df: pd.DataFrame, out_path: str):
    if not HAS_MATPLOTLIB:
        print("(matplotlib not installed -- skipping chart. `pip install matplotlib` to enable.)")
        return

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [2, 1]})

    axes[0].plot(equity_df["datetime"], equity_df["equity"], color="#2563eb", linewidth=1.2)
    axes[0].set_title("Equity Curve")
    axes[0].set_ylabel("Equity")
    axes[0].grid(alpha=0.3)

    if not trades_df.empty:
        cum_r = trades_df["r_multiple"].cumsum()
        axes[1].plot(trades_df["exit_time"], cum_r, color="#16a34a", linewidth=1.2)
        axes[1].set_title("Cumulative R-multiple")
        axes[1].set_ylabel("R")
        axes[1].grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(out_path, dpi=130)
    plt.close(fig)


# ----------------------------------------------------------------------
# Parameter sweep
# ----------------------------------------------------------------------
def run_sweep(df: pd.DataFrame, ema_pullbacks=(21, 34), atr_mults=(1.0, 1.5, 2.0, 2.5, 3.0),
              rrs=(1.5, 2.0, 3.0), rsi_period=14, rsi_long_th=45, rsi_short_th=55,
              atr_period=14, pullback_atr_dist=1.0, ema_fast=50, ema_slow=200,
              max_bars=40, risk_pct=1.0, starting_equity=10000.0) -> pd.DataFrame:
    """
    Sweeps ema_pullback x atr_mult x rr and returns one row of stats per
    combination, sorted by expectancy_R descending. atr_mult range covers
    1.0-3.0 since BTC's wick/volatility profile on 4H tends to need a wider
    buffer than gold/forex before the tighter end (1.0) stops getting
    stopped out by noise.
    """
    rows = []
    for ema_pb in ema_pullbacks:
        d = add_indicators(df, ema_fast, ema_slow, ema_pb, rsi_period, atr_period)
        d = generate_signals(d, rsi_long_th, rsi_short_th, pullback_atr_dist)
        for atr_mult, rr in [(a, r) for a in atr_mults for r in rrs]:
            trades_df, equity_df = run_backtest(
                d, atr_mult=atr_mult, rr=rr, max_bars=max_bars,
                risk_pct=risk_pct, starting_equity=starting_equity
            )
            stats = compute_stats(trades_df, equity_df)
            stats.pop("by_year", None)
            stats.update({"ema_pullback": ema_pb, "atr_mult": atr_mult, "rr": rr})
            rows.append(stats)

    out = pd.DataFrame(rows)
    if "expectancy_R" in out.columns:
        out = out.sort_values("expectancy_R", ascending=False)
    return out


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description="BTC Trend-Following Backtest (4H+)")
    p.add_argument("--csv", required=True, help="Path to OHLCV CSV file")
    p.add_argument("--ema_fast", type=int, default=50)
    p.add_argument("--ema_slow", type=int, default=200)
    p.add_argument("--ema_pullback", type=int, default=20)
    p.add_argument("--rsi_period", type=int, default=14)
    p.add_argument("--rsi_long_th", type=float, default=45)
    p.add_argument("--rsi_short_th", type=float, default=55)
    p.add_argument("--atr_period", type=int, default=14)
    p.add_argument("--atr_mult", type=float, default=1.5)
    p.add_argument("--pullback_atr_dist", type=float, default=1.0)
    p.add_argument("--rr", type=float, default=2.0)
    p.add_argument("--max_bars", type=int, default=40)
    p.add_argument("--risk_pct", type=float, default=1.0)
    p.add_argument("--equity", type=float, default=10000.0)
    p.add_argument("--out_prefix", default="btc_backtest")
    p.add_argument("--sweep", action="store_true",
                   help="Run a parameter sweep over ema_pullback x atr_mult x rr "
                        "instead of a single backtest, and save results to CSV.")
    args = p.parse_args()

    print(f"Loading data from {args.csv} ...")
    df = load_csv(args.csv)
    print(f"Loaded {len(df)} bars from {df['datetime'].min()} to {df['datetime'].max()}")

    if args.sweep:
        sweep_df = run_sweep(
            df, rsi_period=args.rsi_period, rsi_long_th=args.rsi_long_th,
            rsi_short_th=args.rsi_short_th, atr_period=args.atr_period,
            pullback_atr_dist=args.pullback_atr_dist, ema_fast=args.ema_fast,
            ema_slow=args.ema_slow, max_bars=args.max_bars, risk_pct=args.risk_pct,
            starting_equity=args.equity,
        )
        out_csv = f"{args.out_prefix}_sweep.csv"
        sweep_df.to_csv(out_csv, index=False)
        print("\n===== PARAMETER SWEEP (top 15 by expectancy_R) =====")
        print(sweep_df.head(15).to_string(index=False))
        print(f"\nFull sweep saved to {out_csv}")
        return
    df = add_indicators(df, args.ema_fast, args.ema_slow, args.ema_pullback,
                         args.rsi_period, args.atr_period)
    df = generate_signals(df, args.rsi_long_th, args.rsi_short_th, args.pullback_atr_dist)

    trades_df, equity_df = run_backtest(
        df, atr_mult=args.atr_mult, rr=args.rr, max_bars=args.max_bars,
        risk_pct=args.risk_pct, starting_equity=args.equity
    )

    stats = compute_stats(trades_df, equity_df)

    print("\n===== BACKTEST STATISTICS =====")
    for k, v in stats.items():
        if k == "by_year":
            print("\nBreakdown by year:")
            print(v.to_string())
        else:
            print(f"{k}: {v}")

    if not trades_df.empty:
        trades_csv = f"{args.out_prefix}_trades.csv"
        trades_df.to_csv(trades_csv, index=False)
        print(f"\nTrade log saved to {trades_csv}")

        chart_path = f"{args.out_prefix}_equity.png"
        plot_equity(equity_df, trades_df, chart_path)
        if HAS_MATPLOTLIB:
            print(f"Equity chart saved to {chart_path}")


if __name__ == "__main__":
    main()
