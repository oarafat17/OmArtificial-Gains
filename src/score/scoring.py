
from __future__ import annotations

def clamp(v: float, lo: float, hi: float) -> float:
    return max(min(v, hi), lo)

def normalize_mos(mos: float) -> float:
    return clamp(mos, -1.0, 1.0)

def technical_score(price: float | None, sma200: float | None, rsi14: float | None) -> float:
    if price is None or sma200 is None or rsi14 is None:
        return 0.0
    sc = 0.0
    if price >= sma200:
        sc += 0.4
    else:
        sc -= 0.2
    if 40 <= rsi14 <= 60:
        sc += 0.3
    elif rsi14 < 30:
        sc += 0.15
    elif rsi14 > 70:
        sc -= 0.2
    return clamp(sc, -1.0, 1.0)

def ownership_score(inst_pct_change: float | None, top_conc: float | None = None) -> float:
    sc = 0.0
    if inst_pct_change is not None:
        if inst_pct_change > 0.5:
            sc += 0.5
        elif inst_pct_change > 0.0:
            sc += 0.25
        elif inst_pct_change < -0.5:
            sc -= 0.5
        else:
            sc -= 0.15
    if top_conc is not None:
        if 30 <= top_conc <= 60:
            sc += 0.15
        elif top_conc > 80:
            sc -= 0.15
    return clamp(sc, -1.0, 1.0)

def overall_score(mos_norm: float, sentiment_norm: float, technical_norm: float, ownership_norm: float) -> float:
    w_m, w_s, w_t, w_o = 0.40, 0.25, 0.20, 0.15
    composite = (w_m * mos_norm) + (w_s * sentiment_norm) + (w_t * technical_norm) + (w_o * ownership_norm)
    score_0_100 = (composite + 1.0) * 50.0
    return max(min(score_0_100, 100.0), 0.0)
