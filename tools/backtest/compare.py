"""Old vs new trend rules: python compare.py features.pkl ohlcv.csv.gz"""
import sys, pandas as pd, numpy as np
from rules import *
df = pd.read_pickle(sys.argv[1]); df = df[df.n_bars >= 252]
# windows that fit inside the site's 1y fetch (~245 bars)
raw = pd.read_csv(sys.argv[2], parse_dates=["Date"])
raw = raw.dropna(subset=["Close"]).sort_values(["Ticker","Date"])
g = raw.groupby("Ticker")["Close"]
raw["mom_fit"] = g.shift(21) / g.shift(230) - 1
raw["hi_fit"] = raw.Close / g.transform(lambda s: s.rolling(231, min_periods=200).max())
df = df.merge(raw[["Ticker","Date","mom_fit","hi_fit"]], on=["Ticker","Date"], how="left")

wk = df[df.Date.dt.weekday == 4].copy(); S = pd.Timestamp("2023-01-01")
wk["old_action"] = old_action(wk); wk["new_action"] = new_action(wk); wk["new_action_norisk"] = new_action(wk, False)
wk["new_score"] = new_swing_score(wk); wk["old_score"] = old_swing_score(wk)
wk["old_tech"] = old_rating_tech(wk); wk["new_tech"] = new_rating_tech(wk)
def med(p, col): return p.groupby(col)["xs_63"].median().mul(100).round(2)
for nm, p in (("TRAIN", wk[wk.Date < S]), ("TEST", wk[wk.Date >= S])):
    print(f"\n######## {nm}")
    for col in ["old_action", "new_action", "new_action_norisk", "old_score", "new_score"]:
        t = table(p, col, None); t["xs_63_median%"] = med(p, col); print(f"-- {col}"); print(t)
    print("IC old_tech", rank_ic(p, "old_tech")[:2], " new_tech", rank_ic(p, "new_tech")[:2])
    # by year Buy-Avoid spread
    p = p.assign(yr=p.Date.dt.year)
    for col in ["old_action", "new_action"]:
        sp = p.groupby(["yr", col])["xs_63"].mean().unstack()
        print(col, "Buy-Avoid 63d spread by year %:", ((sp["Buy"] - sp["Avoid"]) * 100).round(2).to_dict())
