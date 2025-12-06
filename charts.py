# charts.py
import pandas as pd
import plotly.graph_objects as go


def price_chart_with_ema(df: pd.DataFrame, title: str = "Price", limit: int = 200):
    """
    Candlestick chart with EMA20, EMA50, VWAP.
    Shows only the last `limit` candles for better readability.
    """
    if len(df) > limit:
        df = df.iloc[-limit:].copy()

    fig = go.Figure()

    # Candlesticks
    fig.add_trace(
        go.Candlestick(
            x=df["date"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Price",
            increasing_line_width=1,
            decreasing_line_width=1,
            showlegend=True,
        )
    )

    # EMA 20
    if "ema_20" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["ema_20"],
                mode="lines",
                name="EMA 20",
                line=dict(width=2),
            )
        )

    # EMA 50
    if "ema_50" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["ema_50"],
                mode="lines",
                name="EMA 50",
                line=dict(width=2),
            )
        )

    # VWAP
    if "vwap" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["vwap"],
                mode="lines",
                name="VWAP",
                line=dict(width=2, dash="dot"),
            )
        )

    fig.update_layout(
        title=title,
        template="plotly_dark",
        xaxis_title="Time",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        margin=dict(l=40, r=20, t=40, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
    )

    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridwidth=0.5)

    return fig


def rsi_chart(df: pd.DataFrame, title: str = "RSI (14)", limit: int = 200):
    """
    RSI line with overbought/oversold bands.
    Shows only the last `limit` candles.
    """
    if len(df) > limit:
        df = df.iloc[-limit:].copy()

    fig = go.Figure()

    # RSI line
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["rsi_14"],
            mode="lines",
            name="RSI 14",
            line=dict(width=2),
        )
    )

    # Overbought / oversold zones (shaded)
    fig.add_hrect(
        y0=70, y1=100,
        line_width=0,
        fillcolor="red",
        opacity=0.05,
    )
    fig.add_hrect(
        y0=0, y1=30,
        line_width=0,
        fillcolor="green",
        opacity=0.05,
    )

    # Reference lines
    fig.add_hline(y=70, line_dash="dash", annotation_text="70")
    fig.add_hline(y=30, line_dash="dash", annotation_text="30")

    fig.update_layout(
        title=title,
        template="plotly_dark",
        xaxis_title="Time",
        yaxis_title="RSI",
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        margin=dict(l=40, r=20, t=40, b=40),
        yaxis=dict(range=[0, 100]),
        showlegend=False,
    )

    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridwidth=0.5)

    return fig
