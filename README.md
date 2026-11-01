# Bot de trading (cripto) – v0.2

## En Colab
!unzip -o trading_bot.zip
%cd trading_bot
!pip install ccxt feedparser
!python download_data.py BTC/USDT 4h 4 binanceus
!python backtest.py btc_usdt_4h.csv
!python backtest.py btc_usdt_4h.csv --sin-apagado     # mide la señal pura
from IPython.display import Image; Image('curvas.png')  # (en una celda de Python)

## Cómo leer el reporte
- tramo1 vs tramo2: si solo funciona en uno, NO hay ventaja real.
- Compara siempre contra COMPRAR-Y-MANTENER.
- PF (profit factor) > 1.3 y estable en ambos tramos es lo mínimo razonable.

## v3 (varios activos, tendencia lenta, criterios fijados de antemano)
%cd /content/trading_bot
!python download_multi.py binanceus
!python backtest_v3.py data conservador
# gráfico (celda de Python): from IPython.display import Image; Image('/content/trading_bot/curvas_v3.png')
# bot.py sigue usando la estrategia v2; solo se conectará la v3 si el veredicto es APROBADO.

## Paper trading v3 (diario, SIMULADO)
Ejecutar UNA vez al día, después de las 7 pm hora Ecuador (cierre diario 00:00 UTC):
    python paper_v3.py
Primera ejecución = arranque. Archivos que genera: paper_state.json (estado), paper_trades.csv, paper_equity.csv.
Si te saltas días no pasa nada: procesa las velas pendientes en orden.
    python paper_v3.py --reiniciar     # empezar de cero

## Automatización y panel (v0.4)
Ver GUIA_GITHUB.md: GitHub Actions ejecuta paper_v3.py cada día (.github/workflows/diario.yml),
make_status.py genera docs/status.json y docs/index.html es el panel instalable (PWA).
