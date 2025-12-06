# indicators.py
import pandas as pd
import pandas_ta as ta


def add_basic_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds EMA, RSI, VWAP, SuperTrend, MACD and Bollinger Bands
    to OHLCV DataFrame.
    Expects columns: date, open, high, low, close, volume
    """
    df = df.copy()
    df.set_index("date", inplace=True)

    close = df["close"]
    high = df["high"]
    low = df["low"]
    vol = df["volume"]

    # EMAs
    df["ema_20"] = ta.ema(close, length=20)
    df["ema_50"] = ta.ema(close, length=50)

    # RSI
    df["rsi_14"] = ta.rsi(close, length=14)

    # VWAP
    df["vwap"] = ta.vwap(high, low, close, vol)

    # SuperTrend (10 period, 3x ATR – common default)
    st = ta.supertrend(high, low, close, length=10, multiplier=3.0)
    # st gives columns like: SUPERT_10_3.0, SUPERTd_10_3.0
    if st is not None and not st.empty:
        df["supertrend"] = st.iloc[:, 0]
        df["supertrend_dir"] = st.iloc[:, 1]  # 1 = uptrend, -1 = downtrend

    # MACD (12,26,9 default)
    macd = ta.macd(close)
    if macd is not None and not macd.empty:
        df["macd"] = macd.iloc[:, 0]
        df["macd_signal"] = macd.iloc[:, 1]
        df["macd_hist"] = macd.iloc[:, 2]

    # Bollinger Bands (20, 2)
    bb = ta.bbands(close, length=20, std=2.0)
    if bb is not None and not bb.empty:
        df["bb_lower"] = bb.iloc[:, 0]
        df["bb_mid"] = bb.iloc[:, 1]
        df["bb_upper"] = bb.iloc[:, 2]

    df.reset_index(inplace=True)
    return df
