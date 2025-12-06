import pandas as pd
from datetime import datetime, timedelta, timezone

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from config import ALPACA_API_KEY, ALPACA_API_SECRET, ALPACA_SANDBOX

# Init historical data client
stock_client = StockHistoricalDataClient(
    api_key=ALPACA_API_KEY,
    secret_key=ALPACA_API_SECRET,
    sandbox=ALPACA_SANDBOX,
)

# Map our interval strings to Alpaca TimeFrame
def _interval_to_timeframe(interval: str) -> TimeFrame:
    interval = interval.lower()
    if interval == "1minute":
        return TimeFrame.Minute  # built-in 1-min
    if interval == "2minute":
        return TimeFrame(2, TimeFrameUnit.Minute)
    if interval == "5minute":
        return TimeFrame(5, TimeFrameUnit.Minute)
    if interval == "15minute":
        return TimeFrame(15, TimeFrameUnit.Minute)
    if interval == "30minute":
        return TimeFrame(30, TimeFrameUnit.Minute)
    if interval == "60minute":
        return TimeFrame(60, TimeFrameUnit.Minute)
    # default 5-min
    return TimeFrame(5, TimeFrameUnit.Minute)


def get_intraday_data_us(
    symbol: str = "AAPL",
    interval: str = "5minute",
    days: int = 5,
) -> pd.DataFrame:
    """
    Fetch intraday OHLCV data for a US stock using Alpaca.

    Returns DataFrame with:
        ['date', 'open', 'high', 'low', 'close', 'volume']
    """
    symbol = symbol.strip().upper()

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    timeframe = _interval_to_timeframe(interval)

    request_params = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
        feed="iex"
    )

    bars = stock_client.get_stock_bars(request_params)

    # Convert to DataFrame
    df = bars.df

    if df.empty:
        raise ValueError(f"No data returned for US symbol {symbol}")

    # For single symbol, df index is MultiIndex (symbol, timestamp)
    if isinstance(df.index, pd.MultiIndex):
        # Slice by symbol level
        df = df.xs(symbol)

    df = df.reset_index().rename(columns={"timestamp": "date"})

    # Normalize column names
    df.columns = [str(c).lower() for c in df.columns]

    required = ["date", "open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(
            f"Missing columns {missing} in Alpaca data. "
            f"Available: {df.columns.tolist()}"
        )

    out = df[required].copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")

    for c in ["open", "high", "low", "close", "volume"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")

    out.dropna(inplace=True)

    return out
