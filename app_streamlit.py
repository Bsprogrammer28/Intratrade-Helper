import math
from backtest import backtest_basic_strategy
import plotly.graph_objects as go
import streamlit as st
import pandas as pd

from streamlit_autorefresh import st_autorefresh

from data_india import get_intraday_data_india
from data_us import get_intraday_data_us
from indicators import add_basic_indicators
from strategy import (
    basic_intraday_signal,
    supertrend_signal,
    macd_bollinger_vwap_signal,
    STRATEGIES,
)
STRATEGY_DESCRIPTIONS = {
    "Basic EMA + RSI": (
        "Uses EMA20 & EMA50 to define trend and RSI14 to check momentum. "
        "Bullish when price is above EMAs and RSI is not overbought; "
        "bearish when price is below EMAs and RSI is not oversold."
    ),
    "SuperTrend": (
        "Uses SuperTrend (10,3) as main trend filter. "
        "Long when SuperTrend is below price and in up mode; "
        "short when SuperTrend is above price and in down mode."
    ),
    "MACD + Bollinger + VWAP": (
        "Combines VWAP, Bollinger Bands and MACD. "
        "Looks for pullbacks/bounces near VWAP & Bollinger bands "
        "with MACD crossing in the direction of the move."
    ),
}

from paper_trading import (
    init_paper_state,
    open_paper_trade_from_signal,
    update_paper_position_for_symbol,
    get_paper_equity,
)
from charts import price_chart_with_ema, rsi_chart

# -------------------------------------------------------------------
# App setup
# -------------------------------------------------------------------
st.set_page_config(page_title="Intraday Analyzer", layout="wide")
init_paper_state(st.session_state)
st.title("📊 Intraday Stock Analyzer – India (NSE) + US (Alpaca)")

# ---------- Sidebar: Auto-refresh controls ----------
st.sidebar.header("⚙️ Settings")

auto_refresh = st.sidebar.checkbox("Auto-refresh", value=False)
refresh_every_sec = st.sidebar.slider(
    "Refresh interval (seconds)", 10, 300, 60, step=10
)

if auto_refresh:
    # auto-rerun the script every N milliseconds
    st_autorefresh(interval=refresh_every_sec * 1000, key="autorefresh_key")

# ---------- Sidebar: Risk Management ----------
st.sidebar.markdown("---")
st.sidebar.header("💰 Risk Management")

account_capital = st.sidebar.number_input(
    "Account capital",
    min_value=0.0,
    value=100000.0,  # adjust default to your typical capital
    step=1000.0,
)

risk_percent = st.sidebar.slider(
    "Risk per trade (%)",
    0.1,
    5.0,
    1.0,
    step=0.1,
)

# ---------- Sidebar: Strategy ----------
st.sidebar.markdown("---")
st.sidebar.header("📐 Strategy")

strategy_name = st.sidebar.selectbox(
    "Select strategy",
    list(STRATEGIES.keys()),
    index=0,
)
strategy_fn = STRATEGIES[strategy_name]

st.sidebar.markdown("**Strategy info:**")
st.sidebar.write(STRATEGY_DESCRIPTIONS.get(strategy_name, ""))

# ---------- Sidebar: Paper Trading ----------
st.sidebar.markdown("---")
st.sidebar.header("💵 Paper Trading")

enable_paper = st.sidebar.checkbox("Enable paper trading", value=True)

if st.sidebar.button("Reset paper trades"):
    st.session_state["paper_open_positions"] = {}
    st.session_state["paper_closed_trades"] = []

# ---------- Market selection ----------
market = st.selectbox("Market", ["India (NSE)", "US (Alpaca)"])

# Tabs: single, scanner, backtest, paper, help
tab_single, tab_scan, tab_backtest, tab_paper, tab_help = st.tabs(
    ["🎯 Single Symbol", "📚 Watchlist Scanner", "📈 Backtest", "💵 Paper Trading", "❓ Help / Docs"]
)

# ===================================================================
# 🎯 SINGLE SYMBOL TAB
# ===================================================================
with tab_single:
    col1, col2, col3 = st.columns(3)

    with col1:
        if market.startswith("India"):
            symbol_single = st.text_input("NSE Symbol", value="RELIANCE")
        else:
            symbol_single = st.text_input("US Symbol", value="AAPL")
        symbol_key = symbol_single.strip().upper()  # for paper trading / state keys

    with col2:
        interval_single = st.selectbox(
            "Interval",
            ["1minute", "2minute", "5minute", "15minute", "30minute", "60minute"],
            index=2,
            key="interval_single",
        )

    with col3:
        days_single = st.slider("Lookback days", 1, 20, 5, key="days_single")

    run_single = st.button("Analyze Single") or auto_refresh

    if run_single:
        try:
            # 1) Fetch data
            if market.startswith("India"):
                raw_df = get_intraday_data_india(
                    symbol_single, interval=interval_single, days=days_single
                )
            else:
                raw_df = get_intraday_data_us(
                    symbol_single, interval=interval_single, days=days_single
                )

            # 2) Indicators
            df = add_basic_indicators(raw_df)

            # --- Paper trading: update any open position for this symbol ---
            if enable_paper and len(df) > 0:
                last_row = df.iloc[-1]
                update_paper_position_for_symbol(st.session_state, symbol_key, last_row)

            # 3) Show recent data
            st.subheader("Last 10 candles (with indicators)")
            st.dataframe(df.tail(10))

            # 4) Charts (PRICE + EMA/VWAP + RSI)
            st.subheader("Price Action")
            price_fig = price_chart_with_ema(
                df, title=f"{symbol_key} – Price / EMA / VWAP"
            )
            st.plotly_chart(price_fig, use_container_width=True)

            st.subheader("RSI (14)")
            rsi_fig = rsi_chart(df, title=f"{symbol_key} – RSI 14")
            st.plotly_chart(rsi_fig, use_container_width=True)

            # 5) Trading plan / signal
            sig = strategy_fn(df)

            st.subheader("Trading Plan")

            st.markdown(f"**Action:** `{sig.get('action', 'WAIT')}`")
            st.markdown(
                f"**Bias / Direction:** `{sig.get('signal', 'NO_SIGNAL')}`"
            )

            st.markdown(f"**Summary:** {sig.get('summary', '')}")
            st.markdown(f"**Trend view:** {sig.get('trend', 'N/A')}")
            st.markdown(f"**RSI view:** {sig.get('rsi_state', 'N/A')}")

            entry = sig.get("entry")
            sl = sig.get("stop_loss")
            t1 = sig.get("target_1")
            t2 = sig.get("target_2")
            rps = sig.get("risk_per_share")
            rr1 = sig.get("rr_1")
            rr2 = sig.get("rr_2")

            qty = None  # default, in case we can't compute position size

            if (
                entry is not None
                and sl is not None
                and t1 is not None
                and rps is not None
                and rps > 0
            ):
                # position sizing
                max_risk_money = account_capital * (risk_percent / 100.0)
                qty = math.floor(max_risk_money / rps)

                if qty <= 0:
                    st.warning(
                        "Risk per share is too large for the chosen risk % and capital. "
                        "Consider increasing capital, lowering risk %, or waiting for a tighter setup."
                    )
                else:
                    risk_money = qty * rps
                    reward1 = qty * (t1 - entry)
                    reward2 = qty * (t2 - entry)

                    st.markdown(
                        f"""
                        **Entry price:** `{entry}`
                        **Stop-loss:** `{sl}`
                        **Target 1:** `{t1}`
                        **Target 2:** `{t2}`

                        **Risk per share:** `{rps}`
                        **Max risk (at {risk_percent:.1f}%):** `{max_risk_money:.2f}`

                        **Suggested quantity:** `{qty}` units
                        **Actual loss at SL:** `≈ {risk_money:.2f}`
                        **Potential P/L:**
                        - To Target 1: `≈ {reward1:.2f}` (≈ {rr1:.1f}R)
                        - To Target 2: `≈ {reward2:.2f}` (≈ {rr2:.1f}R)
                        """
                    )
            else:
                st.info("No concrete trade setup right now – system suggests to WAIT.")

            # --- Paper trading: open position button ---
            if (
                enable_paper
                and entry is not None
                and sl is not None
                and qty is not None
                and qty > 0
            ):
                st.markdown("### Paper Trade")

                already_open = symbol_key in st.session_state["paper_open_positions"]

                if already_open:
                    st.info("Paper position already open for this symbol.")
                else:
                    if st.button("Open paper trade on this signal"):
                        ok = open_paper_trade_from_signal(
                            st.session_state,
                            symbol_key,
                            sig,
                            qty,
                            strategy_name,  # from sidebar
                        )
                        if ok:
                            st.success("Paper trade opened.")
                        else:
                            st.warning(
                                "Paper trade NOT opened (maybe invalid signal or already open)."
                            )

            with st.expander("Detailed reasoning"):
                st.write(sig.get("explanation", ""))
                st.json(sig)  # optional

        except Exception as e:
            st.error(f"Error (single symbol): {e}")

# ===================================================================
# 📚 WATCHLIST SCANNER TAB
# ===================================================================
with tab_scan:
    st.write("Scan multiple symbols and see which ones generate signals.")

    # Default watchlists
    if market.startswith("India"):
        default_watchlist = "RELIANCE, TCS, INFY, SBIN, HDFCBANK, ICICIBANK"
    else:
        default_watchlist = "AAPL, MSFT, TSLA, NVDA, META, AMZN"

    watchlist_str = st.text_area(
        "Symbols (comma-separated)",
        value=default_watchlist,
        height=80,
    )

    interval_scan = st.selectbox(
        "Interval (scanner)",
        ["1minute", "2minute", "5minute", "15minute", "30minute", "60minute"],
        index=2,
        key="interval_scan",
    )
    days_scan = st.slider("Lookback days (scanner)", 1, 10, 3, key="days_scan")

    run_scan = st.button("Run Scan") or auto_refresh

    if run_scan:
        symbols = [s.strip().upper() for s in watchlist_str.split(",") if s.strip()]
        results = []

        with st.spinner("Scanning symbols..."):
            for sym in symbols:
                try:
                    # 1) Fetch data
                    if market.startswith("India"):
                        raw_df = get_intraday_data_india(
                            sym, interval=interval_scan, days=days_scan
                        )
                    else:
                        raw_df = get_intraday_data_us(
                            sym, interval=interval_scan, days=days_scan
                        )

                    # 2) Indicators + strategy
                    df_sym = add_basic_indicators(raw_df)
                    sig = strategy_fn(df_sym)   # uses selected strategy
                    last = df_sym.iloc[-1]

                    # Position sizing (optional)
                    entry = sig.get("entry")
                    sl = sig.get("stop_loss")
                    rps = None
                    qty = None
                    risk_money = None

                    if entry is not None and sl is not None:
                        rps = abs(entry - sl)
                        if rps > 0 and account_capital > 0:
                            max_risk_money = account_capital * (risk_percent / 100.0)
                            qty = math.floor(max_risk_money / rps)
                            if qty > 0:
                                risk_money = qty * rps

                    results.append(
                        {
                            "symbol": sym,
                            "action": sig.get("action"),
                            "direction": sig.get("signal"),   # LONG / SHORT / NO_SIGNAL
                            "summary": sig.get("summary"),
                            "trend": sig.get("trend"),
                            "rsi_state": sig.get("rsi_state"),
                            "entry": entry,
                            "stop_loss": sl,
                            "target_1": sig.get("target_1"),
                            "position_size": qty,
                            "risk_at_sl": risk_money,
                            "last_price": float(last["close"]),
                            "rsi_14": float(last["rsi_14"]),
                            "timestamp": sig.get("timestamp"),
                        }
                    )

                except Exception as e:
                    # If any symbol fails, record the error
                    results.append(
                        {
                            "symbol": sym,
                            "action": "ERROR",
                            "direction": "NO_SIGNAL",
                            "summary": f"Error: {e}",
                            "trend": None,
                            "rsi_state": None,
                            "entry": None,
                            "stop_loss": None,
                            "target_1": None,
                            "position_size": None,
                            "risk_at_sl": None,
                            "last_price": None,
                            "rsi_14": None,
                            "timestamp": None,
                        }
                    )

        if results:
            df_res = pd.DataFrame(results)

            # ----- sort by direction: LONG → SHORT → NO_SIGNAL -----
            df_res["direction"] = df_res["direction"].fillna("NO_SIGNAL")
            cat = pd.CategoricalDtype(["LONG", "SHORT", "NO_SIGNAL"], ordered=True)
            df_res["direction"] = df_res["direction"].astype(cat)
            df_res = df_res.sort_values(["direction", "symbol"])

            st.subheader("Scanner Results (color coded)")

            # ----- color function for each row -----
            def color_row(row):
                if row["direction"] == "LONG":
                    return ["background-color: rgba(0, 128, 0, 0.25)"] * len(row)
                elif row["direction"] == "SHORT":
                    return ["background-color: rgba(178, 34, 34, 0.25)"] * len(row)
                else:
                    return ["background-color: rgba(90, 90, 90, 0.15)"] * len(row)

            styled = df_res.style.apply(color_row, axis=1)
            st.dataframe(styled, use_container_width=True)

            # ----- show only active LONG/SHORT signals -----
            active = df_res[df_res["direction"].isin(["LONG", "SHORT"])]
            st.subheader("Active Signals Only (LONG / SHORT)")
            st.dataframe(active, use_container_width=True)

        else:
            st.warning("No symbols to scan or no results produced.")

# ===================================================================
# 📈 BACKTEST TAB
# ===================================================================
with tab_backtest:
    st.write("Run a simple backtest of the current strategy on one symbol.")

    colb1, colb2, colb3 = st.columns(3)

    with colb1:
        if market.startswith("India"):
            symbol_bt = st.text_input("NSE Symbol (backtest)", value="RELIANCE")
        else:
            symbol_bt = st.text_input("US Symbol (backtest)", value="AAPL")

    with colb2:
        interval_bt = st.selectbox(
            "Interval (backtest)",
            ["1minute", "2minute", "5minute", "15minute", "30minute", "60minute"],
            index=2,
            key="interval_bt",
        )

    with colb3:
        days_bt = st.slider("Lookback days (backtest)", 1, 60, 20, key="days_bt")

    if st.button("Run Backtest"):
        try:
            # 1) fetch data
            if market.startswith("India"):
                raw_df = get_intraday_data_india(
                    symbol_bt, interval=interval_bt, days=days_bt
                )
            else:
                raw_df = get_intraday_data_us(
                    symbol_bt, interval=interval_bt, days=days_bt
                )

            # 2) add indicators
            df_bt = add_basic_indicators(raw_df)

            # 3) run backtest (uses selected strategy)
            trades_df, stats, equity_df = backtest_basic_strategy(
                df_bt, strategy_fn=strategy_fn
            )

            if trades_df.empty:
                st.warning("No trades generated by this strategy on the given data.")
            else:
                st.subheader("Backtest Summary")
                st.json(stats)

                st.subheader("Trades")
                st.dataframe(trades_df)

                # 4) equity curve
                if not equity_df.empty:
                    st.subheader("Equity Curve")
                    fig_eq = go.Figure()
                    fig_eq.add_trace(
                        go.Scatter(
                            x=equity_df["time"],
                            y=equity_df["equity"],
                            mode="lines",
                            name="Equity",
                        )
                    )
                    fig_eq.update_layout(
                        template="plotly_dark",
                        xaxis_title="Time",
                        yaxis_title="Cum. PnL (1 unit per trade)",
                        hovermode="x unified",
                        margin=dict(l=40, r=20, t=40, b=40),
                    )
                    st.plotly_chart(fig_eq, use_container_width=True)

        except Exception as e:
            st.error(f"Backtest error: {e}")

# ===================================================================
# 💵 PAPER TRADING TAB
# ===================================================================
with tab_paper:
    st.header("Paper Trading – Open & Closed Positions")

    equity = get_paper_equity(st.session_state)
    st.markdown(f"**Total realized PnL (paper):** `{equity:.2f}`")

    open_pos = st.session_state.get("paper_open_positions", {})
    closed_trades = st.session_state.get("paper_closed_trades", [])

    st.subheader("Open Positions")
    if open_pos:
        df_open = pd.DataFrame(open_pos).T  # dict-of-dicts → rows
        st.dataframe(df_open, use_container_width=True)
    else:
        st.info("No open paper positions.")

    st.subheader("Closed Trades")
    if closed_trades:
        df_closed = pd.DataFrame(closed_trades)
        st.dataframe(df_closed, use_container_width=True)
    else:
        st.info("No closed paper trades yet.")

# ===================================================================
# ❓ HELP / DOCS TAB
# ===================================================================
with tab_help:
    st.header("How to use this app")

    st.markdown(
        """
### 1. Markets & Data

- **India (NSE)**: Data comes from Yahoo Finance (via `yfinance`) using symbols like `RELIANCE`, `TCS`, `SBIN`.
- **US (Alpaca)**: Data comes from Alpaca's free IEX feed using symbols like `AAPL`, `MSFT`, `TSLA`.

Data is intraday (1m/5m/15m etc.), used for **analysis and backtesting**, not guaranteed tick-perfect for scalping.

---

### 2. Indicators used

- **EMA 20 & EMA 50**  
  Exponential moving averages of the last 20 and 50 candles.  
  - Price above EMAs → uptrend bias  
  - Price below EMAs → downtrend bias  

- **RSI 14**  
  Momentum / overbought–oversold indicator.  
  - Below 30 → oversold  
  - 30–40 → weak / recovering  
  - 40–60 → neutral / healthy  
  - 60–70 → strong  
  - Above 70 → overbought  

- **VWAP**  
  Volume-weighted average price. Often acts like an intraday “fair value” / mean.

- **SuperTrend (10, 3)**  
  Trend-following indicator based on ATR.  
  - Price above SuperTrend → bullish mode  
  - Price below SuperTrend → bearish mode  

- **MACD (12, 26, 9)**  
  Uses fast and slow EMAs to measure trend momentum.  
  - MACD crossing above signal → bullish shift  
  - MACD crossing below signal → bearish shift  

- **Bollinger Bands (20, 2)**  
  Volatility bands around a 20-period moving average.  
  - Price near lower band → potential “cheap” / oversold zone  
  - Price near upper band → potential “expensive” / overbought zone  

---

### 3. Strategy meanings

Each strategy returns:
- **Action**: `BUY`, `SELL`, or `WAIT`  
- **Direction**: `LONG`, `SHORT`, or `NO_SIGNAL`  
- **Entry / Stop-loss / Targets**: Suggested prices based on last candle and indicators  
- **Risk per share**: Difference between entry and stop-loss  

**Basic EMA + RSI**  
- Trades in direction of EMA20 vs EMA50 trend.  
- Filters with RSI so it avoids chasing extreme overbought/oversold moves.

**SuperTrend**  
- Trades in direction of SuperTrend (up/down).  
- As long as price stays above SuperTrend line → bias is long; below → bias is short.

**MACD + Bollinger + VWAP**  
- Looks for pullbacks to VWAP / inside Bollinger band with MACD crossing in favour of the trade.  
- Idea: buy dips in an up move or fade pops in a down move with confirmation from MACD.

---

### 4. How to interpret a signal

On the **Single Symbol** tab you see a “Trading Plan”:

- If **Action = BUY** and **Direction = LONG**:  
  System sees a bullish setup.  
  - You *consider* going long near the **entry** price.  
  - Use **stop-loss** to control risk.  
  - Use **Target 1 / Target 2** as booking levels.  

- If **Action = SELL** and **Direction = SHORT**:  
  System sees a bearish setup.  
  - You *consider* going short or exiting longs.  

- If **Action = WAIT**:  
  No clean edge right now. Best is usually to do nothing.

The **Risk section** shows:
- Suggested **quantity** based on your `Account capital` and `Risk per trade (%)` (from the sidebar)
- Approximate **maximum loss at SL** and potential **profit at targets**.

---

### 5. Scanner & Backtest

- **Scanner**:  
  - Lets you input a watchlist (comma-separated symbols).  
  - For each symbol, the selected strategy is applied.  
  - Color coding:  
    - Green → LONG bias  
    - Red → SHORT bias  
    - Grey → no clear signal  
  - Shows suggested position size and risk for each symbol.

- **Backtest**:  
  - Runs the currently selected strategy over past data for a single symbol.  
  - Simulates 1-unit trades from signal entry to SL/Target.  
  - Shows:
    - Total trades, wins, losses, win rate  
    - Total & average PnL  
    - Max drawdown  
    - Equity curve chart

---

### 6. Paper Trading

- Enable **Paper Trading** in the sidebar.  
- On the **Single Symbol** tab:
  - When a valid setup appears and a quantity is computed, you can click  
    **“Open paper trade on this signal”**.  
  - On each refresh, the app checks if SL / Target 1 / Target 2 were hit and closes the trade accordingly.
- In the **💵 Paper Trading** tab:
  - See all open paper positions.  
  - See all closed trades with PnL.  
  - See total realized PnL.

---

### 7. Important notes

- This tool is for **analysis and learning**, not guaranteed profit.  
- Always consider:
  - News / events  
  - Liquidity / spreads  
  - Your own risk tolerance  

Use it as an assistant to help you structure trades, not as a blind auto-trader.
        """
    )
