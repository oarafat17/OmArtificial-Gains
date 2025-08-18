
from __future__ import annotations
import re

POSITIVE_WEIGHTS = {
    r"\b(beat|beats|beating)\b": 2.0,
    r"\b(raise[d]?|increas(e|ed|es)|above guidance)\b": 1.8,
    r"\b(profit(able)?|positive EBITDA|free cash flow positive)\b": 2.2,
    r"\b(margin(s)? (expand(ed|ing)?|improv(ed|ing)?))\b": 1.8,
    r"\b(revenue growth|top[- ]?line growth|record revenue)\b": 1.6,
    r"\b(guidance (raised|maintained)|strong outlook|upgraded)\b": 1.8,
    r"\b(loss(es)? narrowing|reduced losses)\b": 1.4,
    r"\b(cost discipline|efficien(cy|cies)|operating leverage)\b": 1.4,
    r"\b(buyback|share repurchase|dividend increase)\b": 1.2,
}

NEGATIVE_WEIGHTS = {
    r"\b(miss|missed|below expectations)\b": -2.2,
    r"\b(lower(ed)? guidance|cut guidance|downside)\b": -2.0,
    r"\b(loss widened|widening losses)\b": -1.8,
    r"\b(margin(s)? (compress(ed|ion)|decline|down))\b": -1.6,
    r"\b(revenue decline|top[- ]?line decline|falling sales)\b": -1.6,
    r"\b(headwind(s)?|macro headwinds|foreign exchange headwinds)\b": -1.2,
    r"\b(one[- ]?time charge|impairment|restructuring)\b": -1.2,
    r"\b(cash burn|liquidity risk|going concern)\b": -2.0,
    r"\b(dilution|secondary offering)\b": -1.2,
}

def compute_weighted_sentiment(text: str) -> dict:
    if not text or not text.strip():
        return {"score": 0.0, "label": "neutral", "hits": []}

    text_low = text.lower()

    def apply_patterns(pattern_dict, sign_label):
        score = 0.0
        loc_hits = []
        for pattern, weight in pattern_dict.items():
            matches = re.findall(pattern, text_low, flags=re.IGNORECASE)
            if matches:
                cnt = len(matches)
                sc = weight * cnt
                score += sc
                loc_hits.append((pattern, cnt, weight, sc, sign_label))
        return score, loc_hits

    pos_score, pos_hits = apply_patterns(POSITIVE_WEIGHTS, "+")
    neg_score, neg_hits = apply_patterns(NEGATIVE_WEIGHTS, "-")

    raw = pos_score + neg_score
    norm = max(min(raw / 10.0, 1.0), -1.0)

    label = "bullish" if norm > 0.2 else ("bearish" if norm < -0.2 else "neutral")
    hits = pos_hits + neg_hits
    hits_sorted = sorted(hits, key=lambda x: abs(x[3]), reverse=True)[:20]

    return {
        "score": float(norm),
        "label": label,
        "hits": [{"pattern": h[0], "count": h[1], "weight": h[2], "contrib": h[3], "sign": h[4]} for h in hits_sorted]
    }
