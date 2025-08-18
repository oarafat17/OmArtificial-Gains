from __future__ import annotations
import math
import pandas as pd
import numpy as np
import yfinance as yf

# ----------------------------
# Price & History Helpers
# ----------------------------

def _safe_float(x):
    try:
        v = float(x)
        if math.isfinite(v):
            return v
    except Exception:
        pass
    return None

def get_price_history(ticker: str, period: str = "3y", interval: str = "1d") -> pd.DataFrame:
    """
    Fetches price history with a fallback if Yahoo returns an empty frame.
    """
    t = yf.Ticker(ticker)
    hist = t.history(period=period, interval=interval, auto_adjust=True)
    if hist is None or hist.empty:
        # Fallback: shorter window to improve odds if Yahoo throttled long lookbacks
        hist = t.history(period="1y", interval=interval, auto_adjust=True)
    if hist is None or hist.empty:
        return pd.DataFrame()
    hist = hist.rename(columns=str.capitalize)  # Close, Open, etc.
    return hist

def sma(series: pd.Series, window: int = 200) -> pd.Series:
    if series is None or series.empty:
        return pd.Series(dtype=float)
    return series.rolling(window=window, min_periods=max(1, window // 2)).mean()

def rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    if prices is None or prices.empty:
        return pd.Series(dtype=float)
    delta = prices.diff()
    up = delta.clip(lower=0.0)
    down = -1 * delta.clip(upper=0.0)
    roll_up = up.ewm(alpha=1/period, adjust=False).mean()
    roll_down = down.ewm(alpha=1/period, adjust=False).mean()
    rs = roll_up / (roll_down + 1e-9)
    rsi_vals = 100.0 - (100.0 / (1.0 + rs))
    return rsi_vals

def _try_fast_info_price(t: yf.Ticker):
    """
    Try multiple fast_info keys that sometimes vary by yfinance version.
    """
    price = None
    fi = getattr(t, "fast_info", None)
    if isinstance(fi, dict):
        for key in ("last_price", "lastPrice", "regularMarketPrice", "previous_close", "previousClose"):
            if key in fi:
                price = _safe_float(fi.get(key))
                if price is not None:
                    return price
    # Some versions return a SimpleNamespace-like object
    if fi is not None and not isinstance(fi, dict):
        for key in ("last_price", "lastPrice", "regularMarketPrice", "previous_close", "previousClose"):
            if hasattr(fi, key):
                price = _safe_float(getattr(fi, key))
                if price is not None:
                    return price
    return None

def _try_history_price(t: yf.Ticker):
    """
    Use intraday and daily history to get the latest price.
    """
    # 1m interval, same day
    try:
        h1 = t.history(period="1d", interval="1m", auto_adjust=True)
        if h1 is not None and not h1.empty and "Close" in h1.columns:
            p = _safe_float(h1["Close"].iloc[-1])
            if p is not None:
                return p
    except Exception:
        pass

    # 1d close from 5d history
    try:
        h2 = t.history(period="5d", interval="1d", auto_adjust=True)
        if h2 is not None and not h2.empty and "Close" in h2.columns:
            p = _safe_float(h2["Close"].iloc[-1])
            if p is not None:
                return p
    except Exception:
        pass

    # 1d close
    try:
        h3 = t.history(period="1d", interval="1d", auto_adjust=True)
        if h3 is not None and not h3.empty and "Close" in h3.columns:
            p = _safe_float(h3["Close"].iloc[-1])
            if p is not None:
                return p
    except Exception:
        pass

    return None

def _try_info_price(t: yf.Ticker):
    """
    Deprecated .info can still work as a fallback on some installs.
    """
    try:
        gi = t.get_info()
        for key in ("currentPrice", "regularMarketPrice", "previousClose"):
            if key in gi:
                p = _safe_float(gi.get(key))
                if p is not None:
                    return p
    except Exception:
        pass
    return None

def get_current_price(ticker: str) -> float | None:
    """
    Resilient current price across yfinance versions and Yahoo quirks.
    """
    t = yf.Ticker(ticker)
    # 1) fast_info
    p = _try_fast_info_price(t)
    if p is not None:
        return p
    # 2) history-based approaches
    p = _try_history_price(t)
    if p is not None:
        return p
    # 3) legacy info fallback
    p = _try_info_price(t)
    if p is not None:
        return p
    return None

# ----------------------------
# Public API for the app
# ----------------------------

def get_quote_summary(ticker: str) -> dict:
    t = yf.Ticker(ticker)

    price = get_current_price(ticker)
    prev_close = None
    market_cap = None
    shares_out = None

    # Try to fetch some fast_info facts if present
    fi = getattr(t, "fast_info", None)
    if isinstance(fi, dict):
        prev_close = _safe_float(fi.get("previous_close") or fi.get("previousClose"))
        market_cap = _safe_float(fi.get("market_cap") or fi.get("marketCap"))
    elif fi is not None and not isinstance(fi, dict):
        prev_close = _safe_float(getattr(fi, "previous_close", None) or getattr(fi, "previousClose", None))
        market_cap = _safe_float(getattr(fi, "market_cap", None) or getattr(fi, "marketCap", None))

    # Fallback to get_info if needed
    if market_cap is None or prev_close is None:
        try:
            gi = t.get_info()
            if market_cap is None:
                market_cap = _safe_float(gi.get("marketCap"))
            if prev_close is None:
                prev_close = _safe_float(gi.get("previousClose"))
        except Exception:
            pass

    # Shares outstanding
    try:
        gi = t.get_info()
        shares_out = gi.get("sharesOutstanding")
        if (shares_out is None) and market_cap and price and price > 0:
            shares_out = int(market_cap / price)
    except Exception:
        if market_cap and price and price > 0:
            shares_out = int(market_cap / price)

    # History + indicators
    hist = get_price_history(ticker, period="3y", interval="1d")
    sma200_val = float(sma(hist["Close"], 200).iloc[-1]) if not hist.empty and len(hist) >= 100 else None
    rsi14_val = float(rsi(hist["Close"], 14).iloc[-1]) if not hist.empty and len(hist) >= 20 else None

    return {
        "price": price,
        "prev_close": prev_close,
        "market_cap": market_cap,
        "shares_outstanding": shares_out,
        "sma200": sma200_val,
        "rsi14": rsi14_val,
        "price_hist": hist
    }

# ----------------------------
# DCF & Profitability Utilities
# ----------------------------

def recent_fcf_annual(ticker: str) -> float | None:
    """
    Approximate trailing 12-month FCF using yfinance statements:
    FCF = Operating Cash Flow - CapEx.
    Try TTM (quarterly sum) first, else last annual.
    """
    t = yf.Ticker(ticker)
    fcf_ttm = None

    try:
        cf_q = t.quarterly_cashflow
        if cf_q is not None and not cf_q.empty:
            ocf = cf_q.loc["Operating Cash Flow"].dropna().head(4).sum()
            capex = cf_q.loc["Capital Expenditures"].dropna().head(4).sum()
            fcf_ttm = float(ocf - capex)
    except Exception:
        pass

    if fcf_ttm is not None and np.isfinite(fcf_ttm):
        return fcf_ttm

    try:
        cf_a = t.cashflow
        if cf_a is not None and not cf_a.empty:
            ocf = cf_a.loc["Operating Cash Flow"].dropna().iloc[0]
            capex = cf_a.loc["Capital Expenditures"].dropna().iloc[0]
            return float(ocf - capex)
    except Exception:
        pass

    return None

def simple_dcf_intrinsic_value(
    ticker: str,
    fcf0: float | None = None,
    shares_outstanding: int | None = None,
    years: int = 5,
    growth_rate: float = 0.08,
    discount_rate: float = 0.11,
    terminal_growth: float = 0.025,
) -> dict:
    """
    Basic DCF using a single-stage growth then terminal value (Gordon).
    Returns per-share intrinsic value and status message.
    """
    t = yf.Ticker(ticker)
    if fcf0 is None:
        fcf0 = recent_fcf_annual(ticker)

    if shares_outstanding is None:
        try:
            gi = t.get_info()
            shares_outstanding = gi.get("sharesOutstanding")
        except Exception:
            pass

    if not fcf0 or not shares_outstanding or discount_rate <= terminal_growth:
        return {
            "ok": False,
            "message": "Insufficient data for DCF (FCF, shares, or rates).",
            "iv_per_share": None
        }

    # Project FCF for N years
    fcf_list = []
    fcf = float(fcf0)
    for _ in range(years):
        fcf *= (1.0 + growth_rate)
        fcf_list.append(fcf)

    # Discount each year
    disc = [(fcf_list[i] / ((1.0 + discount_rate) ** (i+1))) for i in range(years)]
    pv_sum = sum(disc)

    # Terminal value at year N
    tv = fcf_list[-1] * (1.0 + terminal_growth) / (discount_rate - terminal_growth)
    pv_tv = tv / ((1.0 + discount_rate) ** years)

    enterprise = pv_sum + pv_tv
    iv_per_share = enterprise / float(shares_outstanding)

    return {
        "ok": True,
        "message": "DCF calculated",
        "iv_per_share": float(iv_per_share)
    }

def get_profitability_flags(ticker: str) -> dict:
    """
    Returns booleans and latest values for:
      - net_profit: whether Net Income (TTM approx or last annual) > 0
      - ocf_positive: Operating Cash Flow TTM > 0
      - fcf_positive: Free Cash Flow TTM > 0 (OCF - CapEx)
    """
    t = yf.Ticker(ticker)
    net_income_val = None
    ocf_ttm = None
    capex_ttm = None
    fcf_ttm = None

    # Net income (try TTM via 4 recent quarterlies; else last annual)
    try:
        inc_q = t.quarterly_income_stmt
        if inc_q is not None and not inc_q.empty and "Net Income" in inc_q.index:
            net_income_val = float(inc_q.loc["Net Income"].dropna().head(4).sum())
    except Exception:
        pass
    if net_income_val is None:
        try:
            inc_a = t.income_stmt
            if inc_a is not None and not inc_a.empty and "Net Income" in inc_a.index:
                net_income_val = float(inc_a.loc["Net Income"].dropna().iloc[0])
        except Exception:
            pass

    # OCF / CapEx TTM
    try:
        cf_q = t.quarterly_cashflow
        if cf_q is not None and not cf_q.empty:
            ocf_ttm = float(cf_q.loc["Operating Cash Flow"].dropna().head(4).sum())
            capex_ttm = float(cf_q.loc["Capital Expenditures"].dropna().head(4).sum())
            fcf_ttm = ocf_ttm - capex_ttm
    except Exception:
        pass

    return {
        "net_profit": (net_income_val is not None and net_income_val > 0),
        "ocf_positive": (ocf_ttm is not None and ocf_ttm > 0),
        "fcf_positive": (fcf_ttm is not None and fcf_ttm > 0),
        "values": {
            "net_income_ttm_or_annual": net_income_val,
            "ocf_ttm": ocf_ttm,
            "capex_ttm": capex_ttm,
            "fcf_ttm": fcf_ttm,
        }
    }
