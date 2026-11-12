"""Smoke tests — every main page should return 200 and contain a key string.

Run with:  python manage.py test apps.stocks
"""
from django.test import TestCase, Client


class SmokeTests(TestCase):
    def test_pages_render(self):
        c = Client()
        # (url, status, expected-substring)
        checks = [
            ("/",          200, "Dashboard"),
            ("/about/",    200, "TradeLab"),
            ("/privacy/",  200, "Privacy"),
            ("/learn/",    200, "Learning"),
            ("/watchlist/",200, "Watchlist"),
            ("/portfolio/",200, "Portfolio"),
            ("/risk/",     200, "Risk"),
            ("/commodities/", 200, "Commodities"),
            ("/sip/",      200, "SIP"),
            ("/what-if/",  200, "What if"),
            ("/accounts/login/",  200, "Sign in"),
            ("/accounts/signup/", 200, "Join"),
        ]
        for url, status, token in checks:
            r = c.get(url)
            self.assertEqual(r.status_code, status, f"{url} returned {r.status_code}")
            self.assertIn(token, r.content.decode(), f"{url!r} missing {token!r}")


class IndicatorAccuracyTests(TestCase):
    """Unit tests for the pure indicator maths (no network)."""

    def _df(self, closes):
        import pandas as pd
        closes = pd.Series([float(c) for c in closes])
        return pd.DataFrame({"Open": closes, "High": closes * 1.01, "Low": closes * 0.99,
                             "Close": closes, "Volume": 1_000_000})

    def test_sma_needs_full_window(self):
        from apps.stocks.services import indicators
        ind = indicators.compute_all(self._df(range(100, 130)))  # 30 bars
        self.assertIsNotNone(ind["sma20"])
        self.assertIsNone(ind["sma50"], "SMA50 must not be reported from 30 bars")

    def test_rsi_is_100_when_price_only_rises(self):
        from apps.stocks.services import indicators
        import pandas as pd
        r = indicators.rsi(pd.Series([float(i) for i in range(1, 60)]))
        self.assertAlmostEqual(float(r.iloc[-1]), 100.0)

    def test_rsi_neutral_on_flat_price(self):
        from apps.stocks.services import indicators
        import pandas as pd
        r = indicators.rsi(pd.Series([100.0] * 40))
        self.assertAlmostEqual(float(r.iloc[-1]), 50.0)

    def test_bollinger_uses_population_std(self):
        from apps.stocks.services import indicators
        import numpy as np, pandas as pd
        closes = pd.Series(np.linspace(100, 120, 40))
        bb = indicators.bollinger(closes, window=20, num_std=2.0)
        window = closes.tail(20)
        expected_upper = window.mean() + 2 * window.std(ddof=0)
        self.assertAlmostEqual(float(bb["upper"].iloc[-1]), float(expected_upper), places=9)

    def test_wilder_atr_decays_old_shock(self):
        from apps.stocks.services.day_trading import _atr_pct
        # 40 calm bars, one 10% shock on bar 20, calm again: the shock should still
        # be visible (decayed) at the end rather than dropping out abruptly.
        bars = []
        price = 100.0
        for i in range(40):
            rng = 10.0 if i == 20 else 1.0
            bars.append({"open": price, "high": price + rng / 2, "low": price - rng / 2, "close": price, "volume": 1})
        calm = _atr_pct(bars[:20])
        after = _atr_pct(bars)
        self.assertGreater(after, calm)
        self.assertLess(after, 3.0)

    def test_session_fraction(self):
        from datetime import datetime
        from apps.stocks.services.day_trading import _session_fraction_elapsed
        from django.utils import timezone
        tz = timezone.get_current_timezone()
        mid = datetime(2026, 11, 12, 12, 22, 30, tzinfo=tz)   # Thursday, exactly half-way
        self.assertAlmostEqual(_session_fraction_elapsed(mid), 0.5, places=2)
        self.assertEqual(_session_fraction_elapsed(datetime(2026, 11, 12, 17, 0, tzinfo=tz)), 1.0)
        self.assertEqual(_session_fraction_elapsed(datetime(2026, 11, 14, 11, 0, tzinfo=tz)), 1.0)  # Saturday
        self.assertEqual(_session_fraction_elapsed(datetime(2026, 11, 12, 9, 16, tzinfo=tz)), 0.10)

    def test_downside_reacts_to_recent_volatility_spike(self):
        from apps.stocks.services.risk_analyser import _estimate_downside_pct
        import numpy as np, pandas as pd
        rng = np.random.default_rng(1)
        calm = rng.normal(0, 0.004, 50)
        wild = rng.normal(0, 0.04, 10)
        closes = pd.Series(100 * np.cumprod(1 + np.concatenate([calm, wild])))
        calm_only = pd.Series(100 * np.cumprod(1 + calm))
        self.assertGreater(_estimate_downside_pct(closes), 2 * _estimate_downside_pct(calm_only))

    def test_yoy_requires_year_ago_quarter(self):
        from apps.stocks.services import financials
        import pandas as pd
        cols = pd.to_datetime(["2026-09-30", "2026-06-30", "2026-03-31"])
        df = pd.DataFrame({c: [100.0 * (1 + i), 10.0, 1.0] for i, c in enumerate(cols)},
                          index=["Total Revenue", "Net Income", "Basic EPS"])

        class _T:
            quarterly_income_stmt = df
            info = {"sector": "Technology", "financialCurrency": "INR"}

        real = financials.yf
        try:
            financials.yf = type("YF", (), {"Ticker": staticmethod(lambda t: _T())})
            fin = financials.get_financials("X.NS")
        finally:
            financials.yf = real
        self.assertIsNone(fin["yoy_revenue_pct"])
        self.assertIsNotNone(fin["qoq_revenue_pct"])

    def test_banks_not_flagged_for_leverage(self):
        from apps.stocks.services.financials import _assess
        snap = {"debt_to_equity": 800.0}
        latest = {"margin": 15.0}
        _, concerns_bank = _assess(snap, latest, None, None, sector="Financial Services")
        _, concerns_other = _assess(snap, latest, None, None, sector="Industrials")
        self.assertFalse(any("leverage" in c.lower() for c in concerns_bank))
        self.assertTrue(any("leverage" in c.lower() for c in concerns_other))
