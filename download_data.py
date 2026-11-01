"""Descarga velas históricas y las guarda en CSV listo para backtest.py

Uso:
    python download_data.py                         -> BTC/USDT, 1h, 2 años, binance
    python download_data.py ETH/USDT 1h 3           -> símbolo, temporalidad, años
    python download_data.py BTC/USDT 1h 2 kraken    -> cambiar de exchange
"""
import os
import sys
import ccxt
import pandas as pd


def download(symbol="BTC/USDT", timeframe="1h", years=2.0, exchange="binance", outdir=None):
    ex = getattr(ccxt, exchange)({"enableRateLimit": True})
    step = ex.parse_timeframe(timeframe) * 1000
    since = ex.milliseconds() - int(years * 365 * 24 * 3600 * 1000)
    rows = []
    while since < ex.milliseconds():
        batch = ex.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
        if not batch:
            break
        rows += batch
        since = batch[-1][0] + step
        print(f"  {len(rows)} velas descargadas...", end="\r", flush=True)

    if not rows:
        raise ValueError("sin datos para " + symbol)
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = df.drop_duplicates("timestamp").sort_values("timestamp")
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    out = f"{symbol.replace('/', '_').lower()}_{timeframe}.csv"
    if outdir:
        os.makedirs(outdir, exist_ok=True)
        out = os.path.join(outdir, out)
    df.to_csv(out, index=False)
    print(f"\nListo: {len(df)} velas ({df.timestamp.iloc[0]} -> {df.timestamp.iloc[-1]}) guardadas en {out}")
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    download(a[0] if len(a) > 0 else "BTC/USDT",
             a[1] if len(a) > 1 else "1h",
             float(a[2]) if len(a) > 2 else 2.0,
             a[3] if len(a) > 3 else "binance")
