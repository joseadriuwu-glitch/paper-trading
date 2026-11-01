"""Módulo de noticias: sentimiento (-1..1) + ventanas de bloqueo.

Versión base: léxico de palabras sobre titulares RSS, con decaimiento por antigüedad.
Mejora recomendada: reemplazar `score_text` por una llamada a un LLM que clasifique
sentimiento e impacto por activo.
"""
import math
import time
from datetime import datetime, timezone

POS = {"surge", "rally", "approval", "approved", "adoption", "record", "gain",
       "bullish", "upgrade", "inflow", "partnership", "beats"}
NEG = {"hack", "ban", "lawsuit", "crash", "plunge", "bearish", "outflow", "fraud",
       "liquidation", "downgrade", "sec sues", "bankruptcy", "misses", "exploit"}

FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
]


def score_text(text: str) -> float:
    t = text.lower()
    p = sum(w in t for w in POS)
    n = sum(w in t for w in NEG)
    return 0.0 if p + n == 0 else (p - n) / (p + n)


def get_news_score(half_life_hours: float = 6.0) -> float:
    """Promedio ponderado por antigüedad de los titulares recientes."""
    try:
        import feedparser
    except ImportError:
        return 0.0
    now, num, den = time.time(), 0.0, 0.0
    for url in FEEDS:
        try:
            for e in feedparser.parse(url).entries[:30]:
                ts = time.mktime(e.published_parsed) if getattr(e, "published_parsed", None) else now
                age_h = max(0.0, (now - ts) / 3600)
                w = 0.5 ** (age_h / half_life_hours)
                num += w * score_text(e.title)
                den += w
        except Exception:
            continue
    return max(-1.0, min(1.0, num / den)) if den else 0.0


def in_blackout(now: datetime, windows: list) -> bool:
    for a, b in windows:
        s = datetime.fromisoformat(a).replace(tzinfo=timezone.utc)
        e = datetime.fromisoformat(b).replace(tzinfo=timezone.utc)
        if s <= now <= e:
            return True
    return False
