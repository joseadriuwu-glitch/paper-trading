"""Puntaje de señales en [-1, 1]. Positivo = compra, negativo = venta."""
import pandas as pd
from config import SETTINGS
from indicators import ema, rsi, atr


def tech_score(df: pd.DataFrame) -> pd.Series:
    c = df["close"]
    trend = (ema(c, 20) > ema(c, 50)).astype(float) * 2 - 1           # tendencia
    mom = ((rsi(c, 14) - 50) / 20).clip(-1, 1)                         # momentum
    hi = df["high"].rolling(20).max().shift(1)
    lo = df["low"].rolling(20).min().shift(1)
    brk = pd.Series(0.0, index=df.index)                               # ruptura
    brk[c > hi] = 1.0
    brk[c < lo] = -1.0
    return 0.4 * trend + 0.3 * mom + 0.3 * brk


def final_score(df: pd.DataFrame, news=0.0,
                news_weight: float = SETTINGS["news_weight"],
                trend_filter: bool = SETTINGS["trend_filter"]) -> pd.Series:
    """Técnica + noticias + filtro de tendencia mayor (v2)."""
    s = tech_score(df) + news_weight * news
    if trend_filter:
        c = df["close"]
        e = ema(c, SETTINGS["trend_ema"])
        s = s.where(~((c <= e) & (s > 0)), 0.0)   # sin largos bajo la EMA larga
        s = s.where(~((c >= e) & (s < 0)), 0.0)   # sin cortos sobre la EMA larga
    return s.clip(-1, 1)
