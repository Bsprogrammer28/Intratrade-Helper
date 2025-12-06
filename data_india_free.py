# data_india_free.py

import pandas as pd
import yfinance as yf

INTERVAL_MAP = {
    "1minute": "1m",
    "2minute": "2m",
    "5minute": "5m",
    "15minute": "15m",
    "30minute": "30m",
    "60minute": "60m",
}


def _format_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    return symbol if symbol.endswith(".NS") else symbol + ".NS"


def get_intraday_data_india_free(
    symbol: str = "RELIANCE",
    interval: str = "5minute",
    days: int = 5,
) -> pd.DataFrame:
    yf_symbol = _format_symbol(symbol)
    yf_interval = INTERVAL_MAP.get(interval, "5m")

    # map days -> yfinance "period"
    if days <= 1:
        period = "1d"
    elif days <= 5:
        period = "5d"
    elif days <= 30:
        period = "1mo"
    else:
        period = "3mo"

    df = yf.download(
        yf_symbol,
        period=period,
        interval=yf_interval,
        auto_adjust=False,
        progress=False,
    )

    if df.empty:
        raise ValueError(f"No data returned for symbol {symbol} (as {yf_symbol})")

    # ---- 1) flatten MultiIndex columns if any ----
    if isinstance(df.columns, pd.MultiIndex):
        # take first level name for each column
        df.columns = [str(col[0]) for col in df.columns.to_list()]

    # ---- 2) move index (datetime) to a column ----
    df = df.reset_index()

    # ---- 3) normalize column names to lowercase strings ----
    df.columns = [str(c).lower() for c in df.columns]

    # ---- 4) find the datetime column ----
    datetime_col = None
    for cand in ["datetime", "date", "index"]:
        if cand in df.columns:
            datetime_col = cand
            break

    if datetime_col is None:
        raise ValueError(f"Could not find datetime column in: {df.columns.tolist()}")

    # ---- 5) ensure required OHLCV columns exist ----
    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(
            f"Missing columns {missing} in downloaded data. "
            f"Available columns: {df.columns.tolist()}"
        )

    # ---- 6) build clean output DataFrame ----
    out = pd.DataFrame()
    out["date"] = pd.to_datetime(df[datetime_col], errors="coerce")

    for c in required:
        out[c] = pd.to_numeric(df[c], errors="coerce")

    out.dropna(inplace=True)

    return out
