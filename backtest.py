# backtest.py

from __future__ import annotations
import pandas as pd
from typing import List, Dict, Tuple, Callable
from strategy import basic_intraday_signal


def backtest_basic_strategy(
    df: pd.DataFrame,
    strategy_fn: Callable[[pd.DataFrame], dict] = basic_intraday_signal,
    min_history: int = 20,
) -> Tuple[pd.DataFrame, dict, pd.DataFrame]:
    """
    Backtest the current basic_intraday_signal on a single symbol.

    - df: OHLCV + indicators (ema_20, ema_50, rsi_14, vwap)
    - Uses:
        signal  -> LONG / SHORT / NO_SIGNAL
        entry   -> suggested entry price
        stop_loss
        target_1 (used as main TP)

    Returns:
        trades_df: each completed trade
        stats: summary dict
        equity_df: time vs equity (for plotting equity curve)
    """

    trades: List[Dict] = []
    equity_points: List[Dict] = []

    position = None      # "LONG" or "SHORT"
    entry_price = None
    sl = None
    tp = None
    entry_time = None

    equity = 0.0

    # walk forward candle by candle
    for i in range(min_history, len(df)):
        window = df.iloc[: i + 1]
        row = df.iloc[i]

        # if no open position → check for new signal
        if position is None:
            sig = strategy_fn(window)
            side = sig.get("signal")  # LONG / SHORT / NO_SIGNAL

            if side in ("LONG", "SHORT") and sig.get("entry") is not None:
                position = side
                entry_price = float(sig["entry"])
                sl = sig.get("stop_loss")
                tp = sig.get("target_1")  # use T1 as main TP
                entry_time = sig.get("timestamp") or str(row["date"])

                # if SL/TP missing, ignore this signal
                if sl is None or tp is None:
                    position = None
                    entry_price = sl = tp = entry_time = None
                    continue

                sl = float(sl)
                tp = float(tp)

        else:
            # we have an open position → check SL/TP on this candle
            high = float(row["high"])
            low = float(row["low"])
            time_now = row["date"]
            exit_price = None
            exit_reason = None

            if position == "LONG":
                if low <= sl:
                    exit_price = sl
                    exit_reason = "SL"
                elif high >= tp:
                    exit_price = tp
                    exit_reason = "TP"
            else:  # SHORT
                if high >= sl:
                    exit_price = sl
                    exit_reason = "SL"
                elif low <= tp:
                    exit_price = tp
                    exit_reason = "TP"

            if exit_price is not None:
                # 1-unit position
                if position == "LONG":
                    pnl = exit_price - entry_price
                else:
                    pnl = entry_price - exit_price

                equity += pnl
                equity_points.append(
                    {"time": time_now, "equity": equity}
                )

                trades.append(
                    {
                        "entry_time": entry_time,
                        "exit_time": time_now,
                        "side": position,
                        "entry": entry_price,
                        "stop_loss": sl,
                        "target": tp,
                        "exit": exit_price,
                        "exit_reason": exit_reason,
                        "pnl": pnl,
                    }
                )

                # reset
                position = None
                entry_price = sl = tp = entry_time = None

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_points)

    if trades_df.empty:
        stats = {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate_pct": 0.0,
            "total_pnl": 0.0,
            "avg_pnl": 0.0,
            "max_drawdown": 0.0,
        }
        return trades_df, stats, equity_df

    wins = (trades_df["pnl"] > 0).sum()
    losses = (trades_df["pnl"] < 0).sum()
    total_trades = len(trades_df)
    total_pnl = float(trades_df["pnl"].sum())
    avg_pnl = float(trades_df["pnl"].mean())
    win_rate = 100.0 * wins / total_trades

    # max drawdown based on equity points
    if not equity_df.empty:
        eq_series = equity_df["equity"]
        roll_max = eq_series.cummax()
        drawdown = eq_series - roll_max
        max_dd = float(drawdown.min())  # <= 0
    else:
        max_dd = 0.0

    stats = {
        "total_trades": int(total_trades),
        "wins": int(wins),
        "losses": int(losses),
        "win_rate_pct": round(win_rate, 2),
        "total_pnl": round(total_pnl, 2),
        "avg_pnl": round(avg_pnl, 2),
        "max_drawdown": round(max_dd, 2),
    }

    return trades_df, stats, equity_df
