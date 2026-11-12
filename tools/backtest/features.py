"""Build per-(ticker, date) features with the site's exact indicator code, plus forward returns."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
from apps.stocks.services import indicators as ind

def per_ticker(g):
    g = g.sort_values("Date").set_index("Date")
    c = g["Close"].astype(float); h = g["High"]; l = g["Low"]; o = g["Open"]; v = g["Volume"]
    f = pd.DataFrame(index=g.index)
    f["close"] = c
    f["sma20"] = ind.sma(c, 20); f["sma50"] = ind.sma(c, 50); f["sma200"] = ind.sma(c, 200)
    f["rsi"] = ind.rsi(c, 14)
    m = ind.macd(c); f["macd"] = m["macd"]; f["macd_sig"] = m["signal"]
    bb = ind.bollinger(c); f["bbw"] = (bb["upper"] - bb["lower"]) / c
    f["ret_1d"] = c.pct_change()
    f["ret_5d"] = c.pct_change(5); f["ret_21d"] = c.pct_change(21)
    f["mom_12_1"] = c.shift(21) / c.shift(252) - 1
    f["mom_6_1"] = c.shift(21) / c.shift(126) - 1
    f["hi52"] = c / c.rolling(252, min_periods=200).max()
    f["vol63"] = c.pct_change().rolling(63).std() * np.sqrt(252)
    f["sma5"] = c.rolling(5).mean()
    f["range_pos"] = ((c - l) / (h - l)).where(h > l)
    f["avgvol20"] = v.rolling(20).mean().shift(1)
    f["volratio"] = v / f["avgvol20"]
    f["n_bars"] = np.arange(1, len(c) + 1)
    # forward returns (close-to-close) and next-day open->close
    for k in (1, 5, 21, 63):
        f[f"fwd_{k}"] = c.shift(-k) / c - 1
    f["fwd_oc1"] = c.shift(-1) / o.shift(-1) - 1
    return f

def build(path):
    raw = pd.read_csv(path, parse_dates=["Date"])
    raw = raw.dropna(subset=["Close"])
    raw = raw[raw["Close"] > 0]
    feats = {t: per_ticker(g) for t, g in raw.groupby("Ticker")}
    idx = feats.pop("^NSEI")
    df = pd.concat(feats, names=["Ticker", "Date"]).reset_index()
    for k in (1, 5, 21, 63):
        df[f"mkt_fwd_{k}"] = df["Date"].map(idx[f"fwd_{k}"])
        df[f"xs_{k}"] = df[f"fwd_{k}"] - df[f"mkt_fwd_{k}"]
    df["mkt_above200"] = df["Date"].map(idx["close"] > idx["sma200"])
    return df

if __name__ == "__main__":
    df = build(sys.argv[1]); df.to_pickle(sys.argv[2]); print(df.shape)
