"""Perfiles de riesgo y ajustes generales. Edita aquí, no en el resto del código."""
from dataclasses import dataclass


@dataclass(frozen=True)
class RiskProfile:
    risk_per_trade: float    # fracción del capital arriesgada por operación (0.01 = 1%)
    atr_sl_mult: float       # distancia del stop loss en múltiplos de ATR
    rr: float                # ratio beneficio/riesgo del take profit
    max_daily_loss: float    # pérdida diaria máxima -> deja de operar ese día
    max_drawdown: float      # caída máxima desde el pico -> APAGADO del bot
    score_threshold: float   # confluencia mínima de señales para entrar (0 a 1)
    max_leverage: float      # tope del tamaño de posición (nocional / capital)


PROFILES = {
    "conservador": RiskProfile(0.005, 2.0, 2.0, 0.015, 0.08, 0.60, 1.0),
    "moderado":    RiskProfile(0.010, 1.8, 1.8, 0.030, 0.15, 0.50, 2.0),
    "agresivo":    RiskProfile(0.020, 1.5, 1.5, 0.050, 0.25, 0.40, 3.0),
}

SETTINGS = {
    "profile": "moderado",
    "exchange": "binance",
    "symbol": "BTC/USDT",
    "timeframe": "1h",
    "fee": 0.001,            # 0.1% por lado
    "slippage": 0.0005,      # 0.05%
    "news_weight": 0.25,
    "trend_filter": True,    # v2: solo largos sobre la EMA larga, solo cortos debajo
    "trend_ema": 200,     # cuánto pesan las noticias en el puntaje final
    "paper_equity": 10_000,
    # Ventanas sin operar (UTC), p. ej. datos de inflación / decisiones de tasas:
    "blackouts": [
        # ("2026-11-12 13:00", "2026-11-12 15:00"),
    ],
}

# Activos del universo v3 (velas diarias)
UNIVERSO = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT", "DOGE/USDT",
            "SOL/USDT", "LTC/USDT", "LINK/USDT", "AVAX/USDT", "DOT/USDT", "TRX/USDT"]
