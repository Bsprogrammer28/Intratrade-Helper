# strategy.py
import pandas as pd


def _classify_trend(price: float, ema20: float, ema50: float) -> str:
    if any(pd.isna(x) for x in [price, ema20, ema50]):
        return "Unknown"

    if ema20 > ema50 and price > ema20:
        return "Strong uptrend"
    if ema20 > ema50 and price <= ema20:
        return "Mild uptrend / pullback"
    if ema20 < ema50 and price < ema20:
        return "Strong downtrend"
    if ema20 < ema50 and price >= ema20:
        return "Mild downtrend / bounce"
    return "Sideways / choppy"


def _classify_rsi(rsi: float) -> str:
    if pd.isna(rsi):
        return "Unknown"
    if rsi < 30:
        return f"Oversold ({rsi:.1f})"
    if rsi < 40:
        return f"Weak / recovering ({rsi:.1f})"
    if rsi <= 60:
        return f"Neutral / healthy ({rsi:.1f})"
    if rsi <= 70:
        return f"Strong / getting hot ({rsi:.1f})"
    return f"Overbought ({rsi:.1f})"


def _build_trade_plan(direction: str, price: float, low: float, high: float,
                      ema20: float, ema50: float, rsi: float,
                      timestamp: str, base_summary: str, extra_expl: str = "") -> dict:
    """
    Shared logic that builds entry, SL, targets, RR, explanation.
    direction: 'LONG' or 'SHORT'
    """
    trend = _classify_trend(price, ema20, ema50)
    rsi_state = _classify_rsi(rsi)

    if direction is None:
        return {
            "signal": "NO_SIGNAL",
            "action": "WAIT",
            "summary": "No clear edge – stay on the sidelines.",
            "explanation": f"Trend: {trend}. RSI: {rsi_state}. {extra_expl}",
            "trend": trend,
            "rsi_state": rsi_state,
            "price": price,
            "timestamp": timestamp,
            "entry": None,
            "stop_loss": None,
            "target_1": None,
            "target_2": None,
            "risk_per_share": None,
            "rr_1": None,
            "rr_2": None,
        }

    if direction == "LONG":
        action = "BUY"
        entry = price
        stop_loss = low
        risk = entry - stop_loss
        if risk <= 0:
            stop_loss = entry * 0.99
            risk = entry - stop_loss
        target_1 = entry + risk
        target_2 = entry + 2 * risk
    else:
        action = "SELL"
        entry = price
        stop_loss = high
        risk = stop_loss - entry
        if risk <= 0:
            stop_loss = entry * 1.01
            risk = stop_loss - entry
        target_1 = entry - risk
        target_2 = entry - 2 * risk

    rr_1 = (target_1 - entry) / risk if risk != 0 else None
    rr_2 = (target_2 - entry) / risk if risk != 0 else None

    explanation = (
        f"{base_summary} "
        f"Trend: {trend}. RSI: {rsi_state}. {extra_expl}"
    )

    return {
        "signal": direction,
        "action": action,
        "summary": base_summary,
        "explanation": explanation,
        "trend": trend,
        "rsi_state": rsi_state,
        "price": round(entry, 4),
        "entry": round(entry, 4),
        "stop_loss": round(stop_loss, 4),
        "target_1": round(target_1, 4),
        "target_2": round(target_2, 4),
        "risk_per_share": round(risk, 4),
        "rr_1": rr_1,
        "rr_2": rr_2,
        "timestamp": timestamp,
    }


# 1) BASIC EMA + RSI STRATEGY
def basic_intraday_signal(df: pd.DataFrame) -> dict:
    if len(df) < 3:
        return {
            "signal": "NO_SIGNAL",
            "action": "WAIT",
            "summary": "Not enough candles to analyse.",
            "explanation": "Need at least 3–4 candles with indicators ready.",
        }

    last = df.iloc[-1]
    price = float(last["close"])
    low = float(last["low"])
    high = float(last["high"])
    ema20 = last.get("ema_20")
    ema50 = last.get("ema_50")
    rsi = last.get("rsi_14")
    ts = str(last.get("date"))

    if any(pd.isna(x) for x in [ema20, ema50, rsi]):
        return {
            "signal": "NO_SIGNAL",
            "action": "WAIT",
            "summary": "Indicators not ready yet.",
            "explanation": "EMA or RSI has NaN values – need more history.",
            "timestamp": ts,
        }

    direction = None
    base_summary = ""

    if ema20 > ema50 and price > ema50 and rsi <= 70:
        direction = "LONG"
        base_summary = "Bullish bias using EMA + RSI – look for long (buy) setups."
    elif ema20 < ema50 and price < ema50 and rsi >= 30:
        direction = "SHORT"
        base_summary = "Bearish bias using EMA + RSI – look for short (sell) setups."

    return _build_trade_plan(direction, price, low, high, ema20, ema50, rsi, ts, base_summary)


# 2) SUPERTREND STRATEGY
def supertrend_signal(df: pd.DataFrame) -> dict:
    if len(df) < 3:
        return {
            "signal": "NO_SIGNAL",
            "action": "WAIT",
            "summary": "Not enough candles for SuperTrend.",
        }

    last = df.iloc[-1]
    price = float(last["close"])
    low = float(last["low"])
    high = float(last["high"])
    ema20 = last.get("ema_20")
    ema50 = last.get("ema_50")
    rsi = last.get("rsi_14")
    st = last.get("supertrend")
    st_dir = last.get("supertrend_dir")
    ts = str(last.get("date"))

    if any(pd.isna(x) for x in [ema20, ema50, rsi, st, st_dir]):
        return {
            "signal": "NO_SIGNAL",
            "action": "WAIT",
            "summary": "SuperTrend / indicators not ready yet.",
            "timestamp": ts,
        }

    direction = None
    base_summary = ""
    extra = f"SuperTrend value {st:.2f}, direction {int(st_dir)}."

    if st_dir == 1 and price > st:
        direction = "LONG"
        base_summary = "SuperTrend uptrend – consider long as long as price holds above SuperTrend."
    elif st_dir == -1 and price < st:
        direction = "SHORT"
        base_summary = "SuperTrend downtrend – consider short as long as price stays below SuperTrend."

    return _build_trade_plan(direction, price, low, high, ema20, ema50, rsi, ts, base_summary, extra_expl=extra)


# 3) MACD + BOLLINGER + VWAP BOUNCE STRATEGY
def macd_bollinger_vwap_signal(df: pd.DataFrame) -> dict:
    if len(df) < 25:
        return {
            "signal": "NO_SIGNAL",
            "action": "WAIT",
            "summary": "Not enough candles for MACD/Bollinger/VWAP.",
        }

    last = df.iloc[-1]
    price = float(last["close"])
    low = float(last["low"])
    high = float(last["high"])
    ema20 = last.get("ema_20")
    ema50 = last.get("ema_50")
    rsi = last.get("rsi_14")
    macd = last.get("macd")
    macd_sig = last.get("macd_signal")
    bb_low = last.get("bb_lower")
    bb_up = last.get("bb_upper")
    vwap = last.get("vwap")
    ts = str(last.get("date"))

    if any(pd.isna(x) for x in [ema20, ema50, rsi, macd, macd_sig, bb_low, bb_up, vwap]):
        return {
            "signal": "NO_SIGNAL",
            "action": "WAIT",
            "summary": "MACD/Bollinger/VWAP indicators not ready yet.",
            "timestamp": ts,
        }

    direction = None
    base_summary = ""
    extra = f"MACD={macd:.2f}, Signal={macd_sig:.2f}, VWAP={vwap:.2f}."

    # Long idea: price near lower band / VWAP, MACD crossing up, RSI not overbought
    if (
        price <= vwap * 1.005
        and price >= bb_low
        and macd > macd_sig
        and rsi < 65
    ):
        direction = "LONG"
        base_summary = "VWAP/Bollinger pullback with bullish MACD – potential long bounce."

    # Short idea: price near upper band / VWAP, MACD crossing down, RSI not oversold
    elif (
        price >= vwap * 0.995
        and price <= bb_up
        and macd < macd_sig
        and rsi > 35
    ):
        direction = "SHORT"
        base_summary = "VWAP/Bollinger rejection with bearish MACD – potential short fade."

    return _build_trade_plan(direction, price, low, high, ema20, ema50, rsi, ts, base_summary, extra_expl=extra)
STRATEGIES = {
"Basic EMA + RSI": basic_intraday_signal,
"SuperTrend": supertrend_signal,
"MACD + Bollinger + VWAP": macd_bollinger_vwap_signal,
}
