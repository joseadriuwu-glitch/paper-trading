"""Descarga velas diarias (6 años) de varias criptos a la carpeta data/
Uso: python download_multi.py [exchange]     (por defecto binanceus)"""
import sys
from download_data import download
from config import UNIVERSO


if __name__ == "__main__":
    exchange = sys.argv[1] if len(sys.argv) > 1 else "binanceus"
    ok = []
    for sym in UNIVERSO:
        print(f"== {sym}")
        try:
            download(sym, "1d", 6, exchange, outdir="data")
            ok.append(sym)
        except Exception as e:
            print(f"  saltado: {str(e)[:100]}")
    print(f"\nDescargados {len(ok)}/{len(UNIVERSO)}: {', '.join(ok)}")
