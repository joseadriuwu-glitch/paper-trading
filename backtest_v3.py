"""v3: tendencia lenta, SOLO largos y SIN apalancamiento, velas diarias, varios activos.

Reglas (clásicas tipo 'Turtle', no optimizadas por nosotros):
  Entrada : cierre > máximo de 55 días  Y  cierre > EMA 200      (ejecuta en la apertura siguiente)
  Salida  : cierre < mínimo de 20 días  O  stop inicial de 2 ATR
  Tamaño  : arriesga `risk_per_trade` del capital hasta el stop, tope = 100% del capital (spot)

CRITERIOS DE APROBACIÓN (fijados ANTES de correr; no se cambian tras ver resultados):
  A) VENTAJA   : PF >= 1.3 y >= 8 operaciones en AMBOS tramos, en >= 50% de los activos.
  B) PROTECCIÓN: caída máxima <= 50% de la de comprar-y-mantener y retorno > 0
                 (periodo completo), en >= 70% de los activos.
  APROBADO = A y B | SOLO PROTECCIÓN = B | RECHAZADO = el resto.

Uso: python backtest_v3.py [carpeta_datos] [perfil]
"""
import sys
import glob
import os
import numpy as np
import pandas as pd
from config import PROFILES, SETTINGS
from indicators import ema, atr
from backtest import metrics, buy_hold

ENTRY_N, EXIT_N, FILTER_EMA, ATR_STOP = 55, 20, 200, 2.0   # CONGELADOS
WARM, MIN_BARS, MIN_TRADES = 250, 100, 8
EDGE_PF, EDGE_SHARE, DD_RATIO, PROT_SHARE = 1.3, 0.5, 0.5, 0.7
PPY = 365


def run_trend(df, risk, start, end, equity0=10_000, fee=SETTINGS["fee"], slip=SETTINGS["slippage"]):
    o, h, l, c = (df[k].values for k in ("open", "high", "low", "close"))
    a = atr(df, 14).values
    e200 = ema(df["close"], FILTER_EMA).values
    hh = df["high"].rolling(ENTRY_N).max().shift(1).values
    ll = df["low"].rolling(EXIT_N).min().shift(1).values
    idx = df.index
    equity, pos, pend_in, pend_out = equity0, None, False, False
    trades, curve = [], []

    def close_pos(px, i):
        nonlocal equity, pos
        pnl = pos["qty"] * (px - pos["entry"]) - pos["qty"] * px * fee
        equity += pnl
        trades.append(dict(entrada=pos["t"], salida=idx[i], pnl=pnl))
        pos = None

    for i in range(start, end):
        if pend_out and pos:                                   # salida por canal
            close_pos(o[i] * (1 - slip), i)
        pend_out = False
        if pend_in and pos is None:                            # entrada
            px = o[i] * (1 + slip)
            sl_d = a[i - 1] * ATR_STOP
            if sl_d > 0:
                qty = min(equity * risk / sl_d, equity / (px * (1 + fee)))
                if qty > 0:
                    equity -= qty * px * fee
                    pos = dict(entry=px, qty=qty, sl=px - sl_d, t=idx[i])
        pend_in = False
        if pos:                                                # stop intradía
            if o[i] <= pos["sl"]:
                close_pos(o[i] * (1 - slip), i)
            elif l[i] <= pos["sl"]:
                close_pos(pos["sl"] * (1 - slip), i)
        curve.append(equity + (pos["qty"] * (c[i] - pos["entry"]) if pos else 0))
        if pos:
            pend_out = bool(c[i] < ll[i])
        elif c[i] > hh[i] and c[i] > e200[i]:
            pend_in = True
    return pd.DataFrame(trades), pd.Series(curve, index=idx[start:end])


def load(folder):
    out = {}
    for f in sorted(glob.glob(os.path.join(folder, "*_1d.csv"))):
        name = os.path.basename(f).replace("_1d.csv", "").upper().replace("_", "/")
        out[name] = pd.read_csv(f, parse_dates=["timestamp"], index_col="timestamp")
    return out


def main(folder="data", profile="conservador"):
    risk = PROFILES[profile].risk_per_trade
    data = {k: d for k, d in load(folder).items() if len(d) > WARM + 2 * MIN_BARS}
    if len(data) < 3:
        sys.exit(f"Se necesitan al menos 3 activos con datos en '{folder}/'. Encontrados: {len(data)}")
    gstart = min(d.index[WARM] for d in data.values())
    gend = max(d.index[-1] for d in data.values())
    split = gstart + (gend - gstart) / 2
    print(f"Perfil: {profile} (riesgo {risk:.2%} por operación, sin apalancamiento, solo largos)")
    print(f"Activos: {len(data)} | Periodo: {gstart.date()} -> {gend.date()} | Corte entre tramos: {split.date()}\n")

    rows, res, curves, bhs = [], {}, {}, {}
    for name, d in data.items():
        sm = int(d.index.searchsorted(split))
        segs = {"completo": (WARM, len(d)), "tramo1": (WARM, sm), "tramo2": (sm, len(d))}
        res[name] = {}
        for k, (s, e) in segs.items():
            if e - s < MIN_BARS:
                continue
            t, cv = run_trend(d, risk, s, e)
            m, bh = metrics(t, cv, PPY), buy_hold(d, s, e, PPY)
            res[name][k] = (m, bh)
            if k == "completo":
                curves[name] = cv
                bhs[name] = d["close"].iloc[s:] / d["close"].iloc[s]
            rows.append({"activo": name, "tramo": k, "ops": m["ops"], "retorno_%": m["retorno_%"],
                         "maxDD_%": m["maxDD_%"], "PF": m["PF"],
                         "BH_ret_%": bh["retorno_%"], "BH_maxDD_%": bh["maxDD_%"]})
    print(pd.DataFrame(rows).to_string(index=False))

    # ---- criterios ----
    n = len(res)
    edge = sum(1 for r in res.values() if "tramo1" in r and "tramo2" in r and
               all(r[k][0]["ops"] >= MIN_TRADES and r[k][0]["PF"] >= EDGE_PF for k in ("tramo1", "tramo2")))
    prot = sum(1 for r in res.values() if "completo" in r and
               abs(r["completo"][0]["maxDD_%"]) <= DD_RATIO * abs(r["completo"][1]["maxDD_%"])
               and r["completo"][0]["retorno_%"] > 0)
    okA, okB = edge / n >= EDGE_SHARE, prot / n >= PROT_SHARE
    verdict = "APROBADO" if okA and okB else "SOLO PROTECCIÓN" if okB else "RECHAZADO"

    # ---- cartera de pesos iguales ----
    cdf = pd.concat({k: v / v.iloc[0] for k, v in curves.items()}, axis=1).sort_index().ffill().fillna(1.0)
    bdf = pd.concat(bhs, axis=1).sort_index().ffill().fillna(1.0)
    port, bport = cdf.mean(axis=1) * 10_000, bdf.mean(axis=1) * 10_000
    pm, bm = metrics(pd.DataFrame(), port, PPY), metrics(pd.DataFrame(), bport, PPY)
    print("\nCARTERA DE PESOS IGUALES (todos los activos)")
    print(f"  Estrategia v3     : retorno {pm['retorno_%']}% | caída máx {pm['maxDD_%']}% | sharpe {pm['sharpe']}")
    print(f"  Comprar-y-mantener: retorno {bm['retorno_%']}% | caída máx {bm['maxDD_%']}% | sharpe {bm['sharpe']}")

    print("\nCRITERIOS (fijados de antemano)")
    print(f"  A) Ventaja    : {edge}/{n} activos con PF>={EDGE_PF} en ambos tramos (necesita {EDGE_SHARE:.0%}) -> {'CUMPLE' if okA else 'NO CUMPLE'}")
    print(f"  B) Protección : {prot}/{n} activos con caída <= {DD_RATIO:.0%} de B&H y retorno>0 (necesita {PROT_SHARE:.0%}) -> {'CUMPLE' if okB else 'NO CUMPLE'}")
    print(f"\n  VEREDICTO: {verdict}")
    print("\nAviso: la lista de activos son los que sobreviven HOY (sesgo de supervivencia): "
          "los resultados reales serían algo peores.")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.figure(figsize=(10, 5))
        plt.plot(port.index, port.values, label="estrategia v3 (cartera)")
        plt.plot(bport.index, bport.values, "k--", label="comprar y mantener (cartera)")
        plt.axvline(split, color="gray", ls=":")
        plt.yscale("log"); plt.legend(); plt.title("Cartera pesos iguales (log). Punteada = corte de tramos")
        plt.tight_layout(); plt.savefig("curvas_v3.png", dpi=110)
        print("Gráfico guardado en curvas_v3.png")
    except Exception as ex:
        print("(sin gráfico:", ex, ")")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:]]
    prof = next((x for x in a if x in PROFILES), "conservador")
    folder = next((x for x in a if x not in PROFILES), "data")
    main(folder, prof)
