"""Backtester v2.
- Entra en la apertura de la barra siguiente a la señal.
- Si SL y TP caen en la misma barra, asume el SL (conservador).
- Reporta: periodo completo, tramo 1 y tramo 2 (validación) y comprar-y-mantener.
Uso: python backtest.py datos.csv [perfil] [--sin-apagado]"""
import sys
from dataclasses import replace
import numpy as np
import pandas as pd
from config import PROFILES, SETTINGS
from indicators import atr
from signals import final_score
from risk import size_position, RiskGuard

WARM = 250  # velas de calentamiento (EMA 200)


def run_backtest(df, profile_name="moderado", news=0.0, equity0=10_000,
                 fee=SETTINGS["fee"], slip=SETTINGS["slippage"],
                 news_weight=SETTINGS["news_weight"], start=None, end=None, halt=True):
    p = PROFILES[profile_name]
    gp = p if halt else replace(p, max_drawdown=10.0, max_daily_loss=10.0)
    score = final_score(df, news, news_weight).values
    a = atr(df, 14).values
    o, h, l, c = (df[k].values for k in ("open", "high", "low", "close"))
    idx = df.index
    start = max(WARM, start or 0)
    end = end or len(df)
    equity, pos, pending = equity0, None, 0
    guard = RiskGuard(gp, equity0)
    guard.halt_time = None
    trades, curve = [], []

    for i in range(start, end):
        if pending and pos is None and not guard.halted:
            side, pending = pending, 0
            px = o[i] * (1 + slip * side)
            sl_d = a[i - 1] * p.atr_sl_mult
            qty = size_position(equity, p.risk_per_trade, sl_d, px, p.max_leverage)
            if qty > 0:
                equity -= qty * px * fee
                pos = dict(side=side, entry=px, qty=qty, sl=px - side * sl_d,
                           tp=px + side * sl_d * p.rr, t=idx[i])
        if pos:
            s, ex = pos["side"], None
            if s == 1:
                if l[i] <= pos["sl"]: ex = pos["sl"] * (1 - slip)
                elif h[i] >= pos["tp"]: ex = pos["tp"]
            else:
                if h[i] >= pos["sl"]: ex = pos["sl"] * (1 + slip)
                elif l[i] <= pos["tp"]: ex = pos["tp"]
            if ex is not None:
                pnl = s * (ex - pos["entry"]) * pos["qty"] - pos["qty"] * ex * fee
                equity += pnl
                trades.append(dict(entrada=pos["t"], salida=idx[i], lado=s, pnl=pnl))
                pos = None
        mtm = equity + (pos["side"] * (c[i] - pos["entry"]) * pos["qty"] if pos else 0)
        was = guard.halted
        guard.update(idx[i], mtm)
        if guard.halted and not was:
            guard.halt_time = idx[i]
        curve.append(mtm)
        if pos is None and not pending and guard.can_trade(mtm):
            if score[i] >= p.score_threshold: pending = 1
            elif score[i] <= -p.score_threshold: pending = -1

    return pd.DataFrame(trades), pd.Series(curve, index=idx[start:end]), guard


def periods_per_year(index) -> float:
    step = pd.Series(index).diff().median().total_seconds()
    return 365 * 24 * 3600 / step


def metrics(trades, curve, ppy, equity0=10_000):
    dd = float(((curve / curve.cummax()) - 1).min() * 100)
    ret = curve.pct_change().dropna()
    sharpe = float(ret.mean() / ret.std() * np.sqrt(ppy)) if ret.std() else 0.0
    out = {"ops": len(trades), "retorno_%": round(float(curve.iloc[-1] / equity0 - 1) * 100, 1),
           "maxDD_%": round(dd, 1), "sharpe": round(sharpe, 2)}
    if len(trades):
        w, lo = trades.pnl[trades.pnl > 0], trades.pnl[trades.pnl <= 0]
        out["aciertos_%"] = round(len(w) / len(trades) * 100, 1)
        out["PF"] = round(float(w.sum() / abs(lo.sum())), 2) if lo.sum() else float("inf")
    else:
        out["aciertos_%"], out["PF"] = 0.0, 0.0
    return out


def buy_hold(df, start, end, ppy, equity0=10_000):
    cl = df["close"].iloc[start:end]
    curve = cl / cl.iloc[0] * equity0
    return metrics(pd.DataFrame(), curve, ppy) | {"aciertos_%": "-", "PF": "-"}


def report(df, profiles, halt=True, plot=True):
    n, ppy = len(df), periods_per_year(df.index)
    mid = (WARM + n) // 2
    segs = {"completo": (WARM, n), "tramo1": (WARM, mid), "tramo2": (mid, n)}
    print(f"Datos: {df.index[0]} -> {df.index[-1]} ({n} velas)")
    for k, (s, e) in segs.items():
        print(f"  {k}: {df.index[s].date()} -> {df.index[e - 1].date()}")
    print("Apagado por drawdown:", "ACTIVADO" if halt else "DESACTIVADO (mide la señal pura)", "\n")
    rows, curves = [], {}
    for name in profiles:
        for k, (s, e) in segs.items():
            t, cv, g = run_backtest(df, name, start=s, end=e, halt=halt)
            m = metrics(t, cv, ppy)
            m = {"perfil": name, "tramo": k} | m | {"apagado": str(g.halt_time.date()) if g.halt_time else "-"}
            rows.append(m)
            if k == "completo":
                curves[name] = cv
    for k, (s, e) in segs.items():
        rows.append({"perfil": "COMPRAR-Y-MANTENER", "tramo": k} | buy_hold(df, s, e, ppy) | {"apagado": "-"})
    print(pd.DataFrame(rows).to_string(index=False))
    if plot:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            plt.figure(figsize=(10, 5))
            for name, cv in curves.items():
                plt.plot(cv.index, cv.values, label=name)
            bh = df["close"].iloc[WARM:] / df["close"].iloc[WARM] * 10_000
            plt.plot(bh.index, bh.values, "k--", label="comprar y mantener")
            plt.axvline(df.index[mid], color="gray", ls=":")
            plt.yscale("log"); plt.legend(); plt.title("Capital (escala log). Línea punteada = inicio tramo 2")
            plt.tight_layout(); plt.savefig("curvas.png", dpi=110)
            print("\nGráfico guardado en curvas.png")
        except Exception as ex:
            print("(sin gráfico:", ex, ")")


def synthetic(n=24 * 365 * 2, seed=1):
    """Datos sintéticos SOLO para probar que el código corre."""
    r = np.random.default_rng(seed)
    drift = np.repeat(r.normal(0, 0.0004, n // 500 + 1), 500)[:n]
    close = 30000 * np.exp(np.cumsum(drift + r.normal(0, 0.006, n)))
    op = np.r_[close[0], close[:-1]]
    hi = np.maximum(op, close) * (1 + np.abs(r.normal(0, 0.002, n)))
    lo = np.minimum(op, close) * (1 - np.abs(r.normal(0, 0.002, n)))
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    return pd.DataFrame({"open": op, "high": hi, "low": lo, "close": close}, index=idx)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = next((a for a in args if a.endswith(".csv")), None)
    chosen = [a for a in args if a in PROFILES] or list(PROFILES)
    data = (pd.read_csv(path, parse_dates=["timestamp"], index_col="timestamp")
            if path else synthetic())
    report(data, chosen, halt="--sin-apagado" not in sys.argv)
