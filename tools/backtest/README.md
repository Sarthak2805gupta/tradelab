# Trade-rule backtest

Replays the site's trend score weekly on every stock in `apps/stocks/data/nse_stocks.json`
and measures the return over the next 1 and 3 months, relative to the NIFTY 50.
Data: Yahoo daily bars, 2016-2026. Train period 2017-2022, test period 2023-2026.

    python download.py ../.. data/                 # needs network access to Yahoo
    python features.py data/ohlcv.csv.gz data/features.pkl
    python compare.py data/features.pkl data/ohlcv.csv.gz

Caveat: uses today's stock list, so delisted stocks are missing (survivorship bias).
Compare the buckets with each other, not the absolute returns.

Result (Nov 2026), 3-month return vs NIFTY, share of picks that beat it:

| Rule | Period | Buy | Avoid |
|---|---|---|---|
| old (SMA20/50, RSI, MACD) | 2017-22 | 48.2% | 48.7% |
| old | 2023-26 | 50.9% | 45.8% |
| new (200-day avg, 11-month return, 1-year high) | 2017-22 | 50.9% | 46.4% |
| new | 2023-26 | 51.9% | 45.3% |

Rank correlation of the buy-rating's technical+momentum points with the next
3-month excess return: old -0.004 / -0.007, new +0.055 / +0.059 (t > 5 in both periods).
The live-desk intraday verdict was also tested: its BUY vs SELL gap is about
0.04-0.09% per day, below typical trading costs, so it was left unchanged.
