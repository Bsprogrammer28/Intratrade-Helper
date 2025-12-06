# paper_trading.py

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, List, Any
import math


@dataclass
class PaperPosition:
    symbol: str
    side: str          # "LONG" or "SHORT"
    qty: int
    entry: float
    stop_loss: float
    target_1: float
    target_2: float
    opened_at: str
    strategy: str


@dataclass
class PaperClosedTrade:
    symbol: str
    side: str
    qty: int
    entry: float
    stop_loss: float
    target_1: float
    target_2: float
    opened_at: str
    closed_at: str
    exit_price: float
    exit_reason: str    # "SL" / "TP1" / "TP2"
    pnl: float
    strategy: str


def init_paper_state(state: Any) -> None:
    """Ensure required keys exist in st.session_state."""
    if "paper_open_positions" not in state:
        state["paper_open_positions"] = {}   # symbol -> dict
    if "paper_closed_trades" not in state:
        state["paper_closed_trades"] = []    # list of dicts


def open_paper_trade_from_signal(
    state: Any,
    symbol: str,
    sig: Dict,
    qty: int,
    strategy_name: str,
) -> bool:
    """
    Open a new paper position from a signal dict.
    Returns True if opened, False otherwise.
    """

    init_paper_state(state)

    # already have an open position for this symbol? (1 position per symbol)
    if symbol in state["paper_open_positions"]:
        return False

    entry = sig.get("entry")
    sl = sig.get("stop_loss")
    t1 = sig.get("target_1")
    t2 = sig.get("target_2")
    side = sig.get("signal")   # LONG / SHORT
    ts = sig.get("timestamp")

    if side not in ("LONG", "SHORT") or entry is None or sl is None or t1 is None:
        return False
    if qty is None or qty <= 0:
        return False

    pos = PaperPosition(
        symbol=symbol,
        side=side,
        qty=int(qty),
        entry=float(entry),
        stop_loss=float(sl),
        target_1=float(t1),
        target_2=float(t2 if t2 is not None else t1),
        opened_at=str(ts),
        strategy=strategy_name,
    )

    state["paper_open_positions"][symbol] = asdict(pos)
    return True


def update_paper_position_for_symbol(
    state: Any,
    symbol: str,
    last_candle: Dict,
) -> None:
    """
    Check if symbol has an open position and whether SL/T1/T2 hit
    on the latest candle. If hit, close the trade and move to closed list.
    """
    init_paper_state(state)

    if symbol not in state["paper_open_positions"]:
        return

    pos = state["paper_open_positions"][symbol]

    side = pos["side"]
    qty = pos["qty"]
    entry = pos["entry"]
    sl = pos["stop_loss"]
    t1 = pos["target_1"]
    t2 = pos["target_2"]
    opened_at = pos["opened_at"]
    strategy = pos["strategy"]

    high = float(last_candle["high"])
    low = float(last_candle["low"])
    close_time = str(last_candle["date"])

    exit_price = None
    exit_reason = None

    # VERY simple fill logic:
    # For LONG: check SL, then TP2, then TP1
    # For SHORT: same idea but reversed
    if side == "LONG":
        if low <= sl:
            exit_price = sl
            exit_reason = "SL"
        elif high >= t2:
            exit_price = t2
            exit_reason = "TP2"
        elif high >= t1:
            exit_price = t1
            exit_reason = "TP1"
    else:  # SHORT
        if high >= sl:
            exit_price = sl
            exit_reason = "SL"
        elif low <= t2:
            exit_price = t2
            exit_reason = "TP2"
        elif low <= t1:
            exit_price = t1
            exit_reason = "TP1"

    if exit_price is None:
        # nothing hit this candle
        return

    # Calculate PnL (1 unit)
    if side == "LONG":
        pnl_per = exit_price - entry
    else:
        pnl_per = entry - exit_price

    pnl_total = pnl_per * qty

    closed = PaperClosedTrade(
        symbol=symbol,
        side=side,
        qty=qty,
        entry=entry,
        stop_loss=sl,
        target_1=t1,
        target_2=t2,
        opened_at=opened_at,
        closed_at=close_time,
        exit_price=exit_price,
        exit_reason=exit_reason,
        pnl=pnl_total,
        strategy=strategy,
    )

    # Move position to closed list
    state["paper_closed_trades"].append(asdict(closed))
    del state["paper_open_positions"][symbol]


def get_paper_equity(state: Any) -> float:
    """Sum of PnL of closed trades."""
    init_paper_state(state)
    total = 0.0
    for trade in state["paper_closed_trades"]:
        total += float(trade["pnl"])
    return total
