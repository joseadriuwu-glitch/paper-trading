"""Bot en modo SIMULADO (paper trading) con datos reales de ccxt.
Uso: python bot.py            (perfil de config.py)
     python bot.py agresivo
El modo con dinero real NO está activado a propósito: complétalo solo tras
1-2 meses de paper trading con resultados consistentes con el backtest."""
import os
import sys
import time
import json
import urllib.request
from datetime import datetime, timezone
import pandas as pd
import ccxt
from config import PROFILES, SETTINGS
from indicators import atr
from signals import final_score
from risk import size_position, RiskGuard
from news import get_news_score, in_blackout


def notify(msg: str):
    print(msg, flush=True)
    tok, chat = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if tok and chat:
        try:
            data = json.dumps({"chat_id": chat, "text": msg}).encode()
            req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage",
                                         data, {"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass


def fetch(ex, symbol, tf, limit=500) -> pd.DataFrame:
    raw = ex.fetch_ohlcv(symbol, tf, limit=limit)
    df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
    df.index = pd.to_datetime(df.pop("ts"), unit="ms")
    return df


def main():
    prof_name = sys.argv[1] if len(sys.argv) > 1 else SETTINGS["profile"]
    p = PROFILES[prof_name]
    ex = getattr(ccxt, SETTINGS["exchange"])({"enableRateLimit": True})
    equity, pos = float(SETTINGS["paper_equity"]), None
    guard = RiskGuard(p, equity)
    fee, slip = SETTINGS["fee"], SETTINGS["slippage"]
    notify(f"Bot SIMULADO iniciado | perfil={prof_name} | {SETTINGS['symbol']}")

    while True:
        try:
            df = fetch(ex, SETTINGS["symbol"], SETTINGS["timeframe"])
            last = df.iloc[-2]                  # última vela CERRADA
            now = datetime.now(timezone.utc)

            if pos:                              # revisar SL/TP con la vela cerrada
                s, ex_px = pos["side"], None
                if s == 1:
                    ex_px = pos["sl"] if last.low <= pos["sl"] else (pos["tp"] if last.high >= pos["tp"] else None)
                else:
                    ex_px = pos["sl"] if last.high >= pos["sl"] else (pos["tp"] if last.low <= pos["tp"] else None)
                if ex_px:
                    pnl = s * (ex_px - pos["entry"]) * pos["qty"] - pos["qty"] * ex_px * fee
                    equity += pnl
                    notify(f"CIERRE {'LONG' if s == 1 else 'SHORT'} @ {ex_px:.2f} | PnL {pnl:+.2f} | equity {equity:.2f}")
                    pos = None

            mtm = equity + (pos["side"] * (last.close - pos["entry"]) * pos["qty"] if pos else 0)
            guard.update(df.index[-2], mtm)
            if guard.halted:
                notify(f"BOT APAGADO: {guard.reason}")
                break

            if pos is None and guard.can_trade(mtm) and not in_blackout(now, SETTINGS["blackouts"]):
                ns = get_news_score()
                score = final_score(df.iloc[:-1], ns, SETTINGS["news_weight"]).iloc[-1]
                side = 1 if score >= p.score_threshold else -1 if score <= -p.score_threshold else 0
                if side:
                    px = df.iloc[-1].open * (1 + slip * side)
                    sl_d = atr(df.iloc[:-1], 14).iloc[-1] * p.atr_sl_mult
                    qty = size_position(equity, p.risk_per_trade, sl_d, px, p.max_leverage)
                    if qty > 0:
                        equity -= qty * px * fee
                        pos = dict(side=side, entry=px, qty=qty, sl=px - side * sl_d, tp=px + side * sl_d * p.rr)
                        notify(f"ENTRADA {'LONG' if side == 1 else 'SHORT'} @ {px:.2f} | SL {pos['sl']:.2f} "
                               f"| TP {pos['tp']:.2f} | score {score:.2f} | noticias {ns:+.2f}")
        except Exception as e:
            notify(f"Error: {e}")
        time.sleep(60 * 5)   # revisa cada 5 min; solo actúa con velas nuevas cerradas


if __name__ == "__main__":
    main()
