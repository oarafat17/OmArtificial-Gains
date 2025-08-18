from __future__ import annotations
import os
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf

# Cache folder (next to your project root)
CACHE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "ownership_cache"
)
os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_path(ticker: str) -> str:
    safe = ticker.upper().replace("/", "_").replace("\\", "_")
    return os.path.join(CACHE_DIR, f"{safe}.csv")


def _normalize_date_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure the 'date' column is consistently pandas.Timestamp
    (avoids 'Cannot compare Timestamp with datetime.date' errors).
    """
    if "date" not in df.columns:
        return df

    # Convert in-place to tz-naive pandas Timestamps
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.tz_localize(None)
    return df


def _load_cache(ticker: str) -> pd.DataFrame:
    path = _cache_path(ticker)
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            df = _normalize_date_column(df)
            return df
        except Exception:
            pass
    return pd.DataFrame(columns=["date", "inst_pct", "top5_pct", "top10_pct"])


def _save_cache(ticker: str, row: dict):
    """
    Append a new row and keep only unique dates, sorted.
    Dates are enforced as pandas.Timestamp for safe sorting/comparison.
    """
    df = _load_cache(ticker)
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df = _normalize_date_column(df)
    df = df.drop_duplicates(subset=["date"], keep="last").sort_values("date")
    df.to_csv(_cache_path(ticker), index=False)


def fetch_institutional_snapshot(ticker: str) -> dict:
    """
    Pull a current institutional snapshot from yfinance and compute:
      - inst_pct: % of shares held by institutions
      - top5_pct / top10_pct: concentration among top holders (as % of institutional shares)
      - qoq_change: change vs. last cached snapshot (percentage points)
      - trend_df: cached snapshots for sparkline
      - holders: sorted table of holders by shares
    Notes:
      * yfinance institutional_holders can be None/empty for some tickers.
      * QoQ change is approximate (last snapshot vs. current).
    """
    t = yf.Ticker(ticker)

    # Shares outstanding
    shares_out = None
    try:
        gi = t.get_info()
        shares_out = gi.get("sharesOutstanding")
    except Exception:
        pass

    # Institutional table (may be None/empty)
    try:
        inst_df = t.institutional_holders
    except Exception:
        inst_df = None

    result = {
        "ok": True,
        "message": "",
        "inst_pct": None,
        "top5_pct": None,
        "top10_pct": None,
        "holders": None,
        "trend_df": None,
        "qoq_change": None,
        "top10_changes": None,  # placeholder text
    }

    if inst_df is None or inst_df.empty or shares_out is None or not np.isfinite(shares_out):
        result["ok"] = False
        result["message"] = "Institutional data not available from yfinance."
        return result

    # Normalize expected columns
    holders = inst_df.copy()
    if "Shares" not in holders.columns:
        result["ok"] = False
        result["message"] = "Institutional data missing 'Shares' column."
        return result

    holders["Shares"] = pd.to_numeric(holders["Shares"], errors="coerce").fillna(0.0)
    # Some tables have Holder in the index—standardize
    if "Holder" not in holders.columns:
        holders["Holder"] = holders.index.astype(str)

    # Aggregate institutional shares and compute overall % of shares outstanding
    total_inst_shares = holders["Shares"].sum()
    inst_pct = float(total_inst_shares / float(shares_out) * 100.0) if shares_out else None

    # Concentration among top holders (relative to institutional pool)
    holders_sorted = holders.sort_values("Shares", ascending=False).reset_index(drop=True)
    top5 = holders_sorted.head(5)["Shares"].sum()
    top10 = holders_sorted.head(10)["Shares"].sum()
    top5_pct = float(top5 / total_inst_shares * 100.0) if total_inst_shares > 0 else None
    top10_pct = float(top10 / total_inst_shares * 100.0) if total_inst_shares > 0 else None

    # Load previous snapshots for QoQ change and sparkline
    trend_df = _load_cache(ticker)
    prev_row = trend_df.iloc[-1] if not trend_df.empty else None
    qoq_change = None
    if prev_row is not None and pd.notna(prev_row.get("inst_pct")) and inst_pct is not None:
        try:
            qoq_change = float(inst_pct - float(prev_row["inst_pct"]))
        except Exception:
            qoq_change = None  # be safe

    # --- Save current snapshot (ensure date is a pandas.Timestamp) ---
    row = {
        "date": pd.Timestamp(datetime.utcnow()).tz_localize(None),
        "inst_pct": inst_pct,
        "top5_pct": top5_pct,
        "top10_pct": top10_pct,
    }
    _save_cache(ticker, row)

    # Reload to return normalized/updated trend
    trend_df = _load_cache(ticker)

    # Placeholder for richer holder-change diffs (requires storing raw holder lists per date)
    top10_changes = None
    if prev_row is not None:
        top10_changes = (
            "Enable raw holder snapshot archiving to compute detailed top-10 add/trim changes between periods."
        )

    result.update(
        {
            "inst_pct": inst_pct,
            "top5_pct": top5_pct,
            "top10_pct": top10_pct,
            "holders": holders_sorted,
            "trend_df": trend_df,
            "qoq_change": qoq_change,
            "top10_changes": top10_changes,
        }
    )
    return result
