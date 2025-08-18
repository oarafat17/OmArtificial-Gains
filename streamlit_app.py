import os
import pandas as pd
import numpy as np
import streamlit as st
import altair as alt

from src.data.quotes import (
    get_quote_summary,
    simple_dcf_intrinsic_value,
    rsi,  # for RSI series chart
    get_profitability_flags,
)
from src.data.ownership import fetch_institutional_snapshot
from src.nlp.sentiment import compute_weighted_sentiment
from src.score.scoring import normalize_mos, technical_score, ownership_score, overall_score

st.set_page_config(page_title="OmArtificial Gains — Scorecard", page_icon="📈", layout="wide")

# ---------------- Sidebar Controls ----------------
st.sidebar.title("OmArtificial Gains")
ticker = st.sidebar.text_input("Ticker", value="CLOV").strip().upper()

st.sidebar.markdown("---")
st.sidebar.subheader("DCF Assumptions")
years = st.sidebar.slider("Projection years", 3, 10, 5, 1)
growth_rate = st.sidebar.slider("FCF growth rate", 0.00, 0.30, 0.10, 0.01)
discount_rate = st.sidebar.slider("Discount rate (WACC)", 0.05, 0.20, 0.11, 0.005)
terminal_growth = st.sidebar.slider("Terminal growth", 0.00, 0.04, 0.02, 0.005)

st.sidebar.markdown("---")
st.sidebar.subheader("Buy Signal Filters")
mos_threshold = st.sidebar.slider("Margin of Safety threshold", 0.05, 0.50, 0.25, 0.05)
rsi_buy_max = st.sidebar.slider("Max RSI for fresh entry", 40, 80, 65, 1)

st.sidebar.markdown("---")
user_text = st.sidebar.text_area("(Optional) Paste latest earnings transcript or summary for NLP sentiment", height=140)

st.sidebar.markdown("---")
if st.sidebar.button("Refresh Data", use_container_width=True):
    st.rerun()

if not ticker:
    st.stop()

# ---------------- Data Fetch ----------------
quote = get_quote_summary(ticker)
price = quote.get("price")
sma200 = quote.get("sma200")
rsi14 = quote.get("rsi14")

dcf = simple_dcf_intrinsic_value(
    ticker=ticker,
    fcf0=None,
    shares_outstanding=quote.get("shares_outstanding"),
    years=years,
    growth_rate=growth_rate,
    discount_rate=discount_rate,
    terminal_growth=terminal_growth,
)

own = fetch_institutional_snapshot(ticker)

# ---------------- NLP Sentiment ----------------
if user_text and user_text.strip():
    sent = compute_weighted_sentiment(user_text)
else:
    sent = {"score": 0.0, "label": "neutral", "hits": []}

# ---------------- Profitability Flags ----------------
prof = get_profitability_flags(ticker)

# ---------------- Scorecard Metrics ----------------
iv_ps = dcf.get("iv_per_share") if dcf.get("ok") else None
mos = None
if iv_ps and price and iv_ps > 0:
    mos = (iv_ps - price) / iv_ps

mos_norm = normalize_mos(mos if mos is not None else 0.0)
tech_norm = technical_score(price, sma200, rsi14)
own_norm = ownership_score(own.get("qoq_change"), own.get("top10_pct"))
sent_norm = float(sent.get("score", 0.0))

score = overall_score(mos_norm, sent_norm, tech_norm, own_norm)

# ---------------- Layout ----------------
st.title("📊 OmArtificial Gains — Company Scorecard")
st.caption("DCF + Technicals + NLP Sentiment + Institutional Ownership")

# KPIs
kpi_cols = st.columns(5)
kpi_cols[0].metric("Price", f"{price:.2f}" if price is not None else "—")
kpi_cols[1].metric("Intrinsic Value (DCF)", f"{iv_ps:.2f}" if iv_ps is not None else "—", help=dcf.get("message", ""))
kpi_cols[2].metric("Margin of Safety", f"{mos*100:.1f}%" if mos is not None else "—")
kpi_cols[3].metric("RSI(14)", f"{rsi14:.1f}" if rsi14 is not None else "—")
kpi_cols[4].metric("Overall Score", f"{score:.0f}/100")

# Core Profitability Check (your 3 favorites)
st.markdown("### ✅ Core Profitability Check")
pc1, pc2, pc3, pc4 = st.columns([1.2, 1.2, 1.2, 3.4])
pc1.metric("Net Profitability", "Yes" if prof["net_profit"] else "No")
pc2.metric("Free Cash Flow +", "Yes" if prof["fcf_positive"] else "No")
pc3.metric("Operating Cash Flow +", "Yes" if prof["ocf_positive"] else "No")
with pc4:
    vals = prof.get("values", {})
    st.caption(
        f"Net Income (TTM/Annual): {vals.get('net_income_ttm_or_annual'):,}" if vals.get("net_income_ttm_or_annual") is not None else "Net Income: —"
    )
    st.caption(
        f"OCF (TTM): {vals.get('ocf_ttm'):,}" if vals.get("ocf_ttm") is not None else "OCF (TTM): —"
    )
    st.caption(
        f"FCF (TTM): {vals.get('fcf_ttm'):,}" if vals.get('fcf_ttm') is not None else "FCF (TTM): —"
    )

# Buy signal
buy_signal = False
buy_reasons = []
if iv_ps and price and mos is not None and mos >= mos_threshold:
    buy_signal = True
    buy_reasons.append(f"MOS ≥ {int(mos_threshold*100)}%")
if price and sma200 and price >= sma200:
    buy_reasons.append("Price ≥ SMA200")
else:
    buy_signal = False
if rsi14 and rsi14 <= rsi_buy_max:
    buy_reasons.append(f"RSI ≤ {rsi_buy_max}")
else:
    buy_signal = False
if sent_norm >= 0.0:
    buy_reasons.append("Sentiment ≥ Neutral")
else:
    buy_signal = False

st.markdown("---")
sig_col1, sig_col2 = st.columns([1,3])
with sig_col1:
    st.subheader("Signal")
    st.success("✅ BUY CONDITIONS MET" if buy_signal else "⚠️ Conditions not met")
with sig_col2:
    st.write(", ".join(buy_reasons) if buy_reasons else "No positive conditions detected yet.")

# ---------------- Tabs ----------------
tab1, tab2, tab3, tab4 = st.tabs(["Score Breakdown", "DCF", "Sentiment (NLP)", "Institutional Ownership"])

with tab1:
    st.subheader("Score Breakdown")
    bcols = st.columns(4)
    bcols[0].metric("MOS (normalized)", f"{mos_norm:+.2f}")
    bcols[1].metric("Sentiment (normalized)", f"{sent_norm:+.2f}", help="Weighted keywords from transcript/news")
    bcols[2].metric("Technicals (normalized)", f"{tech_norm:+.2f}", help="SMA200 / RSI blend")
    bcols[3].metric("Ownership (normalized)", f"{own_norm:+.2f}", help="QoQ institutional % change + concentration")

    st.markdown("#### Quick Technicals — Price vs SMA200")
    if quote.get("price_hist") is not None and not quote["price_hist"].empty:
        hist = quote["price_hist"].reset_index()
        sma200_series = hist["Close"].rolling(window=200, min_periods=100).mean()
        chart = alt.Chart(hist).mark_line().encode(
            x="Date:T",
            y=alt.Y("Close:Q", title="Price")
        ).properties(height=260)
        chart_sma = alt.Chart(pd.DataFrame({"Date": hist["Date"], "SMA200": sma200_series})).mark_line().encode(
            x="Date:T",
            y=alt.Y("SMA200:Q", title="SMA200")
        )
        st.altair_chart(chart + chart_sma, use_container_width=True)

        # RSI mini-chart
        st.markdown("#### RSI(14)")
        rsi_series = rsi(hist["Close"])
        rsi_df = pd.DataFrame({"Date": hist["Date"], "RSI14": rsi_series})
        line = alt.Chart(rsi_df).mark_line().encode(
            x="Date:T",
            y=alt.Y("RSI14:Q", title="RSI (0–100)", scale=alt.Scale(domain=[0, 100]))
        ).properties(height=160)
        st.altair_chart(line, use_container_width=True)
        st.caption("Common levels: 30 (oversold), 70 (overbought).")
    else:
        st.info("No price history available.")

with tab2:
    st.subheader("Discounted Cash Flow (simplified)")
    if dcf.get("ok"):
        st.write(f"**Intrinsic Value per Share:** `{iv_ps:.2f}`")
        st.caption("This simplified DCF uses trailing FCF (OCF - CapEx), projected growth for N years, a discount rate, and a terminal growth model.")
    else:
        st.warning(dcf.get("message", "DCF not available."))

with tab3:
    st.subheader("NLP Sentiment on Latest Earnings")
    st.write(f"**Label:** `{sent.get('label', 'neutral')}` — **Score:** `{sent_norm:+.2f}` (−1 to +1)")
    if sent.get("hits"):
        st.markdown("**Top Keyword Hits**")
        st.dataframe(pd.DataFrame(sent["hits"]))
    else:
        st.info("Paste an earnings transcript or summary in the sidebar to analyze.")
    st.caption("Tip: Paste the most recent call transcript or summary text in the sidebar to get a sharper reading.")

with tab4:
    st.subheader("Institutional Ownership")
    if own.get("inst_pct") is not None:
        met_cols = st.columns(4)
        met_cols[0].metric("Institutional Ownership", f"{own['inst_pct']:.2f}%")
        if own.get("qoq_change") is not None:
            met_cols[1].metric("QoQ Change (approx.)", f"{own['qoq_change']:+.2f}pp")
        else:
            met_cols[1].metric("QoQ Change (approx.)", "—")
        met_cols[2].metric("Top 5 Concentration", f"{own['top5_pct']:.1f}%" if own.get("top5_pct") is not None else "—")
        met_cols[3].metric("Top 10 Concentration", f"{own['top10_pct']:.1f}%" if own.get("top10_pct") is not None else "—")

        # Trend sparkline
        trend_df = own.get("trend_df")
        if trend_df is not None and not trend_df.empty:
            st.markdown("**Institutional % Trend (cached snapshots)**")
            tdf = trend_df.copy()
            tdf = tdf.dropna(subset=["inst_pct"])
            line = alt.Chart(tdf).mark_line().encode(
                x=alt.X("date:T", title="Date"),
                y=alt.Y("inst_pct:Q", title="Institutional %")
            ).properties(height=220)
            st.altair_chart(line, use_container_width=True)
        else:
            st.info("No trend history yet. Each refresh writes a new snapshot for trend building.")

        # Top holders table
        holders = own.get("holders")
        if holders is not None and not holders.empty:
            st.markdown("**Top Institutional Holders (by shares)**")
            st.dataframe(holders.head(20))
        else:
            st.info("Holder breakdown unavailable.")

        # Change commentary
        if own.get("top10_changes"):
            st.caption(own.get("top10_changes"))
    else:
        st.warning(own.get("message", "Institutional data not available."))

st.markdown("---")
st.caption("OmArtificial Gains: composite score = 40% MOS, 25% Sentiment, 20% Technicals, 15% Ownership.")
