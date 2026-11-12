# Downloads 10y of daily OHLCV for every ticker in data/nse_stocks.json + NIFTY 50 index.
import json, sys, time, pathlib
import pandas as pd, yfinance as yf
repo = pathlib.Path(sys.argv[1]); out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
src = next(repo.rglob("nse_stocks.json"))
tickers = sorted({d["ticker"] for d in json.load(open(src))} | {"^NSEI"})
frames = []
for i in range(0, len(tickers), 25):
    chunk = tickers[i:i+25]
    for attempt in range(3):
        try:
            df = yf.download(chunk, period="10y", interval="1d", auto_adjust=True, group_by="ticker", progress=False, threads=True)
            break
        except Exception as e:
            print("retry", e); time.sleep(5)
    for t in chunk:
        try:
            sub = df[t].dropna(how="all")
        except KeyError:
            continue
        if sub.empty: continue
        sub = sub.reset_index().rename(columns={"index": "Date"}); sub["Ticker"] = t
        frames.append(sub[["Date","Ticker","Open","High","Low","Close","Volume"]])
    print(i+len(chunk), "/", len(tickers)); time.sleep(1)
all_ = pd.concat(frames); all_.to_csv(out/"ohlcv.csv.gz", index=False, compression="gzip")
print("rows", len(all_), "tickers", all_.Ticker.nunique(), "->", out/"ohlcv.csv.gz")
