import numpy as np, pandas as pd

def old_swing_score(d):
    s = pd.Series(0, index=d.index)
    both = d.sma20.notna() & d.sma50.notna()
    s += np.where(both & (d.sma20 > d.sma50), 1, np.where(both, -1, 0))
    s += np.where(d.rsi > 60, 1, np.where(d.rsi < 40, -1, 0))
    s += np.where(d.macd > d.macd_sig, 1, -1)
    return s

def old_action(d):
    s = old_swing_score(d)
    verdict = np.where(s >= 2, "BULLISH", np.where(s <= -2, "BEARISH", "NEUTRAL"))
    high = d.bbw > 0.15
    return pd.Series(np.where((verdict == "BULLISH") & ~high, "Buy", np.where(verdict == "BEARISH", "Avoid", "Watch")), index=d.index)

def old_rating_tech(d):
    s = old_swing_score(d)
    t = np.select([s >= 2, s == 1, s == 0, s == -1], [1.5, 1.0, 0.75, 0.3], 0.0)
    t = t + np.where(d.macd > d.macd_sig, 0.5, 0)
    t = t + np.select([d.bbw < 0.07, d.bbw < 0.12], [0.5, 0.25], 0)
    r = d.rsi
    m = np.select([(r >= 50) & (r <= 65), (r >= 40) & (r < 50), (r > 65) & (r <= 75), r > 75, (r >= 30) & (r < 40)], [2, 1, 1, 0, 0.5], 0)
    return pd.Series(t + m, index=d.index)

def old_intraday(d):
    """Live-desk verdict evaluated at the close (price = close)."""
    p = d.close; chg = d.ret_1d * 100
    bull = ((p > d.sma5 * 1.005).astype(int) + (p > d.sma20 * 1.01) + (chg > 0.5) + (d.range_pos > 0.75))
    bear = ((p < d.sma5 * 0.995).astype(int) + (p < d.sma20 * 0.99) + (chg < -0.5) + (d.range_pos < 0.25))
    net = bull - bear
    return pd.Series(np.select([net >= 2, net == 1, net <= -2, net == -1], ["BUY", "LEAN BUY", "SELL", "LEAN SELL"], "HOLD"), index=d.index)

def table(d, label, rcol, horizons=("xs_21", "xs_63")):
    g = d.groupby(label)
    out = pd.DataFrame({"n": g.size()})
    for h in horizons:
        out[f"{h}_mean%"] = g[h].mean() * 100
        out[f"{h}_hit%"] = g[h].apply(lambda x: (x > 0).mean() * 100)
    return out.round(2)

def rank_ic(d, feat, target="xs_63"):
    x = d[["Date", feat, target]].dropna()
    ics = x.groupby("Date").apply(lambda g: g[feat].rank().corr(g[target].rank()) if len(g) > 20 else np.nan).dropna()
    return ics.mean(), ics.mean() / ics.std() * np.sqrt(len(ics)) if len(ics) > 1 else np.nan, len(ics)

def new_swing_score(d):
    above = d.close / d.sma200 - 1
    s = np.where(above > 0.05, 1, np.where(above < -0.05, -1, 0))
    s = s + np.where(d.mom_fit > 0.10, 1, np.where(d.mom_fit < -0.10, -1, 0))
    s = s + np.where(d.hi_fit >= 0.90, 1, np.where(d.hi_fit < 0.75, -1, 0))
    return pd.Series(s, index=d.index).where(d.sma200.notna() & d.mom_fit.notna() & d.hi_fit.notna(), 0)

def new_action(d, risk_filter=True):
    s = new_swing_score(d)
    high = (d.bbw > 0.15) if risk_filter else False
    return pd.Series(np.where((s >= 2) & ~high, "Buy", np.where(s <= -2, "Avoid", "Watch")), index=d.index)

def new_mom_pts(d):
    m = d.mom_fit
    return pd.Series(np.select([m > .4, m > .2, m > .1, m > 0, m > -.1], [2, 1.75, 1.5, 1.0, 0.5], 0.0), index=d.index).where(m.notna(), 1.0)

def new_rating_tech(d):
    s = new_swing_score(d)
    t = s.map({3: 1.5, 2: 1.25, 1: 1.0, 0: 0.75, -1: 0.4, -2: 0.15, -3: 0.0})
    t = t + np.where(d.macd > d.macd_sig, 0.5, 0) + np.select([d.bbw < 0.07, d.bbw < 0.12], [0.5, 0.25], 0)
    return t + new_mom_pts(d)
