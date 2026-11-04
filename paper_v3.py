"""Paper trading v3 (SIMULADO, velas diarias, 12 criptos, solo largos, sin apalancamiento).

Se ejecuta UNA vez al día, después del cierre diario (00:00 UTC = 7 pm Ecuador).
Guarda su estado en paper_state.json; cada ejecución procesa las velas nuevas ya cerradas
(si te saltas días, las recupera en orden). NO opera dinero real.

Uso:  python paper_v3.py                (perfil conservador)
      python paper_v3.py --reiniciar    (borra el estado y empieza de cero)
"""
import os
import sys
import json
import argparse
import urllib.request
import urllib.error
import numpy as np
import pandas as pd
from config import PROFILES, SETTINGS, UNIVERSO
from indicators import ema, atr
import backtest_v3 as v3

DAY_MS = 86_400_000


def notify(msg: str):
    """Imprime el mensaje y, si hay secretos, lo envía por Telegram. Informa del resultado SIN mostrar el token."""
    print(msg, flush=True)
    tok, chat = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        faltan = [n for n, v in (("TELEGRAM_TOKEN", tok), ("TELEGRAM_CHAT_ID", chat)) if not v]
        print(f"[Telegram] NO enviado: faltan los secretos {', '.join(faltan)} "
              f"(deben estar en Settings > Secrets and variables > Actions > Repository secrets)", flush=True)
        return
    try:
        data = json.dumps({"chat_id": chat, "text": msg[:3500]}).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage",
                                     data, {"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=15)
        print("[Telegram] enviado correctamente", flush=True)
    except urllib.error.HTTPError as e:
        try:
            desc = json.loads(e.read().decode()).get("description", "")
        except Exception:
            desc = ""
        pista = {401: "el token es incorrecto o está incompleto",
                 400: "el chat id es incorrecto, o no le has escrito /start a tu bot",
                 403: "el bot no puede escribirte: abre tu bot y toca Iniciar"}.get(e.code, "")
        print(f"[Telegram] ERROR {e.code}: {desc} -> {pista}", flush=True)
    except Exception as e:
        print(f"[Telegram] ERROR de conexión: {type(e).__name__}", flush=True)


def make_ccxt_fetcher(exchange="binanceus", limit=900):
    import ccxt
    ex = getattr(ccxt, exchange)({"enableRateLimit": True})

    def fetch(sym) -> pd.DataFrame:
        raw = ex.fetch_ohlcv(sym, "1d", limit=limit)
        now = ex.milliseconds()
        raw = [r for r in raw if r[0] + DAY_MS <= now]          # solo velas CERRADAS
        df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
        df.index = pd.to_datetime(df.pop("ts"), unit="ms")
        return df
    return fetch


def indicators(df):
    return (atr(df, 14).values,
            ema(df["close"], v3.FILTER_EMA).values,
            df["high"].rolling(v3.ENTRY_N).max().shift(1).values,
            df["low"].rolling(v3.EXIT_N).min().shift(1).values)


def process_bar(st, i, arr, ind, ts, risk, fee, slip, log):
    """Misma lógica que backtest_v3.run_trend, vela a vela, sobre un estado guardable."""
    o, h, l, c = arr
    a, e200, hh, ll = ind
    pos = st["pos"]
    day = str(ts.date())

    def close_pos(px):
        nonlocal pos
        pnl = pos["qty"] * (px - pos["entry"]) - pos["qty"] * px * fee
        st["equity"] += pnl
        log.append(dict(activo=st["name"], entrada=pos["t"], salida=day,
                        precio_entrada=round(pos["entry"], 6), precio_salida=round(px, 6), pnl=round(pnl, 2)))
        pos = None

    if st["pend_out"] and pos:
        close_pos(o[i] * (1 - slip))
    st["pend_out"] = False
    if st["pend_in"] and pos is None:
        px = o[i] * (1 + slip)
        sl_d = a[i - 1] * v3.ATR_STOP
        if sl_d > 0:
            qty = min(st["equity"] * risk / sl_d, st["equity"] / (px * (1 + fee)))
            if qty > 0:
                st["equity"] -= qty * px * fee
                pos = dict(entry=float(px), qty=float(qty), sl=float(px - sl_d), t=day)
    st["pend_in"] = False
    if pos:
        if o[i] <= pos["sl"]:
            close_pos(o[i] * (1 - slip))
        elif l[i] <= pos["sl"]:
            close_pos(pos["sl"] * (1 - slip))
    st["mtm"] = float(st["equity"] + (pos["qty"] * (c[i] - pos["entry"]) if pos else 0))
    if pos:
        st["pend_out"] = bool(c[i] < ll[i])
    elif c[i] > hh[i] and c[i] > e200[i]:
        st["pend_in"] = True
    st["pos"] = pos


def run(state_path="paper_state.json", profile="conservador", fetcher=None, symbols=UNIVERSO,
        reset=False, capital=10_000.0, out_dir="."):
    risk = PROFILES[profile].risk_per_trade
    fee, slip = SETTINGS["fee"], SETTINGS["slippage"]
    fetcher = fetcher or make_ccxt_fetcher()
    if reset and os.path.exists(state_path):
        os.remove(state_path)
    if os.path.exists(state_path):
        state = json.load(open(state_path))
    else:
        state = dict(profile=profile, capital=capital, assets={})
    risk = PROFILES[state["profile"]].risk_per_trade
    log, new_assets = [], []

    for sym in symbols:
        try:
            df = fetcher(sym)
            if len(df) < v3.WARM + 5:
                raise ValueError("pocas velas")
        except Exception as e:
            print(f"  [{sym}] sin datos: {str(e)[:80]}")
            continue
        arr = tuple(df[k].values for k in ("open", "high", "low", "close"))
        ind = indicators(df)
        st = state["assets"].get(sym)
        if st is None:                                         # alta del activo
            init = state["capital"] / len(symbols)
            st = dict(name=sym, init=init, equity=init, mtm=init, pos=None, pend_in=False, pend_out=False,
                      last=str(df.index[-1].date()), start_price=float(arr[3][-1]), last_close=float(arr[3][-1]))
            c, e200, hh = arr[3][-1], ind[1][-1], ind[2][-1]
            st["pend_in"] = bool(c > hh and c > e200)           # señal vigente al arrancar
            state["assets"][sym] = st
            new_assets.append(sym)
            continue
        for i in range(len(df)):
            if str(df.index[i].date()) > st["last"]:
                process_bar(st, i, arr, ind, df.index[i], risk, fee, slip, log)
                st["last"] = str(df.index[i].date())
        st["last_close"] = float(arr[3][-1])

    json.dump(state, open(state_path, "w"), indent=1)

    A = state["assets"]
    if not A:
        print("Sin datos de ningún activo; revisa tu conexión o el exchange.")
        return state
    if new_assets:
        notify(f"Paper trading v3 INICIADO con {len(new_assets)} activos (perfil {state['profile']}, "
               f"capital simulado {state['capital']:,.0f}).")
    # --- registros ---
    if log:
        p = os.path.join(out_dir, "paper_trades.csv")
        pd.DataFrame(log).to_csv(p, mode="a", header=not os.path.exists(p), index=False)
        for t in log:
            notify(f"CIERRE {t['activo']}: {t['entrada']} -> {t['salida']} | PnL {t['pnl']:+.2f}")
    total = sum(s["mtm"] for s in A.values())
    bh = sum(s["init"] * s["last_close"] / s["start_price"] for s in A.values())
    cap = state["capital"] * len(A) / len(symbols) if len(A) < len(symbols) else state["capital"]
    last_day = max(s["last"] for s in A.values())
    ep = os.path.join(out_dir, "paper_equity.csv")
    prev = pd.read_csv(ep) if os.path.exists(ep) else pd.DataFrame(columns=["fecha", "estrategia", "comprar_mantener"])
    if last_day not in set(prev["fecha"].astype(str)):
        pd.concat([prev, pd.DataFrame([dict(fecha=last_day, estrategia=round(total, 2),
                                            comprar_mantener=round(bh, 2))])]).to_csv(ep, index=False)

    # --- informe ---
    rows = []
    for s in A.values():
        pend = "COMPRAR a la apertura de mañana" if s["pend_in"] else "VENDER a la apertura de mañana" if s["pend_out"] else "-"
        pos = f"{s['pos']['qty']:.4g} @ {s['pos']['entry']:.4g} (stop {s['pos']['sl']:.4g})" if s["pos"] else "en efectivo"
        rows.append({"activo": s["name"], "capital": round(s["mtm"], 1), "posición": pos, "pendiente": pend, "última vela": s["last"]})
    print("\n" + pd.DataFrame(rows).to_string(index=False))
    pend_msgs = [f"{s['name']}: {'COMPRAR' if s['pend_in'] else 'VENDER'} mañana" for s in A.values() if s["pend_in"] or s["pend_out"]]
    if pend_msgs and not new_assets:
        notify("Órdenes simuladas pendientes -> " + " | ".join(pend_msgs))
    n_tr = len(pd.read_csv(os.path.join(out_dir, "paper_trades.csv"))) if os.path.exists(os.path.join(out_dir, "paper_trades.csv")) else 0
    print(f"\nTOTAL estrategia: {total:,.2f} ({(total / cap - 1) * 100:+.2f}%) | comprar y mantener: {bh:,.2f} ({(bh / cap - 1) * 100:+.2f}%)"
          f" | operaciones cerradas: {n_tr} | última vela: {last_day}")
    if os.getenv("RESUMEN_DIARIO") == "1":
        n_open = sum(1 for s in A.values() if s["pos"])
        notify(f"Resumen {last_day}: estrategia {total:,.2f} ({(total / cap - 1) * 100:+.2f}%) | "
               f"comprar y mantener {bh:,.2f} ({(bh / cap - 1) * 100:+.2f}%) | "
               f"posiciones abiertas {n_open} | operaciones cerradas {n_tr}")
    print("Nota: con ~1-2 operaciones por activo al año, 2-3 meses darán MUY pocas operaciones. "
          "Esto valida el funcionamiento, no la ventaja estadística.")
    return state


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--perfil", default="conservador", choices=list(PROFILES))
    ap.add_argument("--reiniciar", action="store_true")
    ap.add_argument("--estado", default="paper_state.json")
    ap.add_argument("--exchange", default="binanceus")
    a = ap.parse_args()
    run(a.estado, a.perfil, make_ccxt_fetcher(a.exchange), reset=a.reiniciar)
