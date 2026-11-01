"""Convierte el estado del paper trading en docs/status.json (lo lee el panel web).
No modifica el estado ni las reglas; solo lee archivos."""
import os
import json
import sys
from datetime import datetime, timezone
import pandas as pd

TRADES_HEADER = "activo,entrada,salida,precio_entrada,precio_salida,pnl\n"


def main(state_path="paper_state.json", out="docs/status.json",
         trades_path="paper_trades.csv", equity_path="paper_equity.csv"):
    st = json.load(open(state_path))
    A = st["assets"]
    if not os.path.exists(trades_path):
        open(trades_path, "w").write(TRADES_HEADER)           # para que el commit siempre tenga el archivo
    trades = pd.read_csv(trades_path)
    eq = pd.read_csv(equity_path) if os.path.exists(equity_path) else pd.DataFrame(columns=["fecha", "estrategia", "comprar_mantener"])

    init = sum(s["init"] for s in A.values())
    total = sum(s["mtm"] for s in A.values())
    bh = sum(s["init"] * s["last_close"] / s["start_price"] for s in A.values())
    activos = []
    for s in A.values():
        pos = None
        if s["pos"]:
            p = s["pos"]
            pos = dict(entrada=p["entry"], stop=p["sl"], cantidad=p["qty"], fecha=p["t"],
                       pnl_abierto=p["qty"] * (s["last_close"] - p["entry"]))
        activos.append(dict(
            nombre=s["name"], capital=s["mtm"], inicial=s["init"],
            rend_pct=(s["mtm"] / s["init"] - 1) * 100,
            bh_pct=(s["last_close"] / s["start_price"] - 1) * 100,
            ultimo_precio=s["last_close"], pos=pos,
            pend_compra=bool(s["pend_in"]), pend_venta=bool(s["pend_out"])))
    dias = 0
    if len(eq):
        dias = (pd.Timestamp(max(s["last"] for s in A.values())) - pd.Timestamp(str(eq["fecha"].iloc[0]))).days
    data = dict(
        generado=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        perfil=st.get("profile", ""), ultima_vela=max(s["last"] for s in A.values()), dias=dias,
        inicial=init, total=total, bh=bh,
        total_pct=(total / init - 1) * 100, bh_pct=(bh / init - 1) * 100,
        n_operaciones=int(len(trades)), activos=activos,
        operaciones=json.loads(trades.tail(30).iloc[::-1].to_json(orient="records")),
        curva=json.loads(eq.to_json(orient="records")))
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    json.dump(data, open(out, "w"), ensure_ascii=False, allow_nan=False)
    print(f"Panel actualizado: {out} (última vela {data['ultima_vela']}, {len(activos)} activos)")


if __name__ == "__main__":
    main(*sys.argv[1:])
