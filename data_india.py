import pandas as pd
import yfinance as yf

# Map our interval names to yfinance intervals
INTERVAL_MAP = {
    "1minute": "1m",
    "2minute": "2m",
    "5minute": "5m",
    "15minute": "15m",
    "30minute": "30m",
    "60minute": "60m",
}


def _format_symbol(symbol: str) -> str:
    """
    Convert 'RELIANCE' -> 'RELIANCE.NS' (Yahoo format).
    If user already passes '.NS', keep as is.
    """
    symbol = symbol.strip().upper()
    return symbol if symbol.endswith(".NS") else symbol + ".NS"


def get_intraday_data_india(
    symbol: str = "RELIANCE",
    interval: str = "5minute",
    days: int = 5,
) -> pd.DataFrame:
    """
    Fetch intraday OHLCV data for an NSE stock using yfinance.

    Parameters
    ----------
    symbol : str
        NSE symbol, e.g. 'RELIANCE', 'TCS', 'SBIN' (with or without .NS).
    interval : str
        One of: '1minute','2minute','5minute','15minute','30minute','60minute'
    days : int
        Approx number of past days of data to fetch.

    Returns
    -------
    DataFrame with columns: ['date','open','high','low','close','volume']
    """

    yf_symbol = _format_symbol(symbol)
    yf_interval = INTERVAL_MAP.get(interval, "5m")

    # Map days → yfinance period string
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

    # ---- 1) Handle possible MultiIndex columns ----
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [str(col[0]) for col in df.columns.to_list()]

    # ---- 2) Move index (datetime) to a column ----
    df = df.reset_index()

    # ---- 3) Normalize column names ----
    df.columns = [str(c).lower() for c in df.columns]

    # ---- 4) Find datetime column ----
    datetime_col = None
    for cand in ["datetime", "date", "index"]:
        if cand in df.columns:
            datetime_col = cand
            break

    if datetime_col is None:
        raise ValueError(f"Could not find datetime column in: {df.columns.tolist()}")

    # ---- 5) Make sure OHLCV exist ----
    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(
            f"Missing columns {missing} in downloaded data. "
            f"Available columns: {df.columns.tolist()}"
        )

    # ---- 6) Build clean output ----
    out = pd.DataFrame()
    out["date"] = pd.to_datetime(df[datetime_col], errors="coerce")
    for c in required:
        out[c] = pd.to_numeric(df[c], errors="coerce")

    out.dropna(inplace=True)

    return out
