"""Gestión de riesgo: tamaño de posición y apagado automático."""
from config import RiskProfile


def size_position(equity: float, risk_frac: float, sl_dist: float,
                  price: float, max_leverage: float) -> float:
    """Cantidad tal que, si salta el stop, se pierde `risk_frac` del capital."""
    if sl_dist <= 0 or price <= 0 or equity <= 0:
        return 0.0
    qty = (equity * risk_frac) / sl_dist
    max_qty = (equity * max_leverage) / price
    return max(0.0, min(qty, max_qty))


class RiskGuard:
    def __init__(self, profile: RiskProfile, equity: float):
        self.p = profile
        self.peak = equity
        self.day = None
        self.day_start = equity
        self.halted = False
        self.reason = ""

    def update(self, ts, equity: float):
        d = ts.date()
        if d != self.day:
            self.day, self.day_start = d, equity
        self.peak = max(self.peak, equity)
        if equity / self.peak - 1 <= -self.p.max_drawdown and not self.halted:
            self.halted = True
            self.reason = f"Drawdown máximo alcanzado ({self.p.max_drawdown:.0%})"

    def can_trade(self, equity: float) -> bool:
        if self.halted:
            return False
        return equity / self.day_start - 1 > -self.p.max_daily_loss
