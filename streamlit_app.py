# streamlit_app.py
# OmArtificial Gains – Fair-Use Friendly Build
# - Manual refresh button (no background polling)
# - Cached data fetches via src/data/quotes.py@get_quotes
# - Optional gentle auto-refresh (OFF by default)
# - Lite mode to keep Community Cloud usage low

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import List, Sequence, Optional

import pandas as pd
import streamlit as st

# ----------------------------
# App Config & Header
# ----------------------------
st.set_page_config(
    page_title="OmArtificial Gains",
    page_icon="📈",
    layout="wide",
)

st.title("OmArtificial Gains 📈")
st.caption(
    "Fair-use friendly build. Data is cached and refreshed on demand to avoid Streamlit Cloud 403 blocks."
)

# ----------------------------
# Sidebar: Core Inputs
# ----------------------------
st.sidebar.header("Configuration")

tickers_input = st.sidebar.text_input(
    "Tickers (comma-separated)",
    value="AAPL, MSFT, NVDA",
    help="Example: AAPL, MSFT, NVDA",
)

lite_mode = st.sidebar.toggle(
    "Lite mode (recommended on Streamlit Cloud)",
    value=True,
    help="Skips non-essential network work."
)

# ----------------------------
# Sidebar: Refresh Controls
# ----------------------------
st.sidebar.subheader("Data refresh")

refresh_now = st.sidebar.button("Fetch latest data")
st.sidebar.caption("Tip: Data is cached ~15 minutes in Community Cloud friendly mode.")

auto_refresh = st.sidebar.toggle("Auto-refresh (advanced)", value=False)
interval_min = st.sidebar.slider(
    "Auto-refresh interval (minutes)",
    min_value=10, max_value=60, value=15,
    disabled=not auto_refresh
)

# ----------------------------
# Utilities / Session State
# ----------------------------
if "quotes_df" not in st.session_state:
    st.session_state.quotes_df = None
    st.session_state.last_fetch_utc = None

def parse_tickers(raw: str) -> List[str]:
    if not raw:
        return []
    return [t.strip().upper() for t in raw.split(",") if t.strip()]

def last_update_badge():
    ts = st.session_state.last_fetch_utc
    if ts:
        st.caption(f"Last updated (UTC): **{ts.strftime('%Y-%m-%d %H:%M:%S')}**")
    else:
        st.caption("No data loaded yet. Click **Fetch latest data** in the sidebar.")

# ----------------------------
# Cached Quotes Helper (import)
# Ensure src/data/quotes.py defines:
#   @st.cache_data(ttl=900)
#   def get_quotes(tickers: Sequence[str], period="1d", interval="1m"): ...
# ----------------------------
from src.data.quotes import get_quotes  # noqa: E402

def fetch_and_store(tickers: Sequence[str]):
    """Fetch quotes once (cached), store in session state."""
    if not tickers:
        st.warning("Please enter at least one ticker.")
        return
    try:
        df = get_quotes(tickers, period="1d", interval="1m")
        if df is None or (hasattr(df, "empty") and df.empty):
            st.warning("No data returned for the selected tickers. Try again in a minute.")
            return
        st.session_state.quotes_df = df
        st.session_state.last_fetch_utc = datetime.utcnow()
    except Exception as e:
        st.error(f"Failed to fetch data: {e}")

# ----------------------------
# Trigger fetches
# ----------------------------
tickers = parse_tickers(tickers_input)

if refresh_now or st.session_state.quotes_df is None:
    fetch_and_store(tickers)

if auto_refresh and st.session_state.last_fetch_utc:
    due = st.session_state.last_fetch_utc + timedelta(minutes=interval_min)
    if datetime.utcnow() >= due:
        fetch_and_store(tickers)
        # Only re-run at most once per interval
        st.rerun()

quotes_df: Optional[pd.DataFrame] = st.session_state.quotes_df

# ----------------------------
# Tabs
# ----------------------------
tab_overview, tab_dcf, tab_ownership = st.tabs(["Overview", "DCF", "Ownership"])

# ----------------------------
# Overview Tab
# ----------------------------
with tab_overview:
    st.subheader("Price Overview")
    last_update_badge()

    if quotes_df is None or (hasattr(quotes_df, "empty") and quotes_df.empty):
        st.info("No data yet. Click **Fetch latest data** in the sidebar.")
    else:
        # yfinance with group_by="ticker" often returns a MultiIndex for multiple tickers
        try:
            if isinstance(quotes_df.columns, pd.MultiIndex):
                latest = {}
                for t in tickers:
                    try:
                        close_series = quotes_df[(t, "Close")]
                        if close_series is not None and not close_series.empty:
                            latest[t] = float(close_series.dropna().iloc[-1])
                    except Exception:
                        continue
                if latest:
                    table = pd.DataFrame.from_dict(latest, orient="index", columns=["Last Close"])
                    table.index.name = "Ticker"
                    st.dataframe(table, use_container_width=True)
                else:
                    st.warning("Could not parse quote data. Try a manual refresh.")
            else:
                # Single-ticker shape
                last_close = float(quotes_df["Close"].dropna().iloc[-1])
                if tickers:
                    st.metric(label=f"{tickers[0]} Last Close", value=f"{last_close:,.2f}")
                else:
                    st.metric(label="Last Close", value=f"{last_close:,.2f}")
        except Exception as e:
            st.warning(f"Overview rendering issue: {e}")

        st.divider()
        if lite_mode:
            st.write(
                "Charts intentionally minimized in Lite mode to keep resource use low on Community Cloud."
            )
        else:
            st.write("Charts coming soon (ensure heavy plotting only runs after manual refresh).")

# ----------------------------
# DCF Tab (Illustrative placeholder)
# ----------------------------
with tab_dcf:
    st.subheader("DCF Snapshot (Illustrative)")
    last_update_badge()

    c1, c2, c3 = st.columns(3)
    with c1:
        selected = st.selectbox("Ticker", options=tickers or ["—"], index=0 if tickers else 0)
    with c2:
        wacc = st.number_input("WACC %", min_value=4.0, max_value=20.0, value=10.0, step=0.5)
    with c3:
        mos = st.slider("Margin of Safety %", 0, 50, 20)

    if quotes_df is None or (hasattr(quotes_df, "empty") and quotes_df.empty) or selected == "—":
        st.info("Load quotes and choose a ticker to see a simple, illustrative DCF anchor.")
    else:
        # Pull a rough price anchor from the latest close
        try:
            if isinstance(quotes_df.columns, pd.MultiIndex):
                px = float(quotes_df[(selected, "Close")].dropna().iloc[-1])
            else:
                px = float(quotes_df["Close"].dropna().iloc[-1])
        except Exception:
            px = math.nan

        if not math.isnan(px):
            # Illustrative intrinsic value (placeholder logic)
            base_iv = px * (1 + (12.0 - (wacc - 10.0)) / 100.0)
            iv = max(base_iv, 0.01)
            target_buy = iv * (1 - mos / 100)

            m1, m2, m3 = st.columns(3)
            m1.metric("Price (approx.)", f"${px:,.2f}")
            m2.metric("Intrinsic Value (toy)", f"${iv:,.2f}")
            m3.metric("Buy Below (MOS applied)", f"${target_buy:,.2f}")

            st.caption(
                "Placeholder DCF. Plug in your full fundamentals-based DCF here (cache those calls too)."
            )
        else:
            st.warning("Could not compute a price anchor from quotes.")

# ----------------------------
# Ownership Tab (Preview)
# ----------------------------
with tab_ownership:
    st.subheader("Institutional Ownership (Preview)")
    st.info(
        "Live ownership lookups are disabled to respect fair-use. "
        "When you add them, wrap network calls with `@st.cache_data(ttl=900)` and fetch only on button click."
    )
    st.write(
        "Planned fields: % held by institutions, QoQ change, net shares added/trimmed, top holder changes, "
        "concentration (% top 5/10), and a small trend sparkline."
    )

# ----------------------------
# Footer
# ----------------------------
st.divider()
st.caption(
    "Built for Community Cloud. If you hit a 403 again, wait for the limit to reset, "
    "then keep refresh manual and caching enabled."
)

