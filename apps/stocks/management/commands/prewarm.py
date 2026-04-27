"""
Pre-warm caches for the most commonly viewed tickers.

Run periodically (e.g., every 30 min via Render Cron) so the first user to
hit /analysis/?ticker=X gets cached data instead of waiting on yfinance.

Usage:
    python manage.py prewarm                # warm the default popular set
    python manage.py prewarm RELIANCE TCS   # warm specific tickers
"""
import time
from django.core.management.base import BaseCommand

# Top names by retail interest in India — covers most analysis page hits.
POPULAR_TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "HCLTECH.NS",
    "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS", "NESTLEIND.NS",
    "BAJFINANCE.NS", "POWERGRID.NS", "NTPC.NS", "TECHM.NS", "TATAMOTORS.NS",
    "ONGC.NS", "TATASTEEL.NS", "ADANIENT.NS", "BAJAJFINSV.NS", "JSWSTEEL.NS",
    "COALINDIA.NS", "INDUSINDBK.NS", "DRREDDY.NS", "CIPLA.NS", "EICHERMOT.NS",
    "BRITANNIA.NS", "APOLLOHOSP.NS", "BPCL.NS", "GRASIM.NS", "TATACONSUM.NS",
    "DIVISLAB.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "M&M.NS", "SBILIFE.NS",
    "HDFCLIFE.NS", "ADANIPORTS.NS", "ZOMATO.NS", "DMART.NS", "ADANIGREEN.NS",
    "^NSEI",  # Nifty 50 index — used as benchmark across the app
]


class Command(BaseCommand):
    help = "Warm caches for popular tickers so users get instant responses."

    def add_arguments(self, parser):
        parser.add_argument("tickers", nargs="*", help="Specific tickers to warm (default: popular set)")
        parser.add_argument("--quiet", action="store_true", help="Suppress per-ticker output")

    def handle(self, *args, **opts):
        from apps.stocks.services import fetcher, analysis

        tickers = opts["tickers"] or POPULAR_TICKERS
        quiet = opts["quiet"]
        ok, fail, t0 = 0, 0, time.time()

        if not quiet:
            self.stdout.write(self.style.NOTICE(f"Pre-warming {len(tickers)} tickers..."))

        for t in tickers:
            try:
                # Touch all the slow paths users hit
                fetcher.fetch_quote(t)
                fetcher.fetch_history(t, period="1mo", interval="1d")
                fetcher.fetch_history(t, period="1y", interval="1d")
                # Skip indices for full analysis (analyze() expects equities)
                if not t.startswith("^"):
                    analysis.analyze(t)
                ok += 1
                if not quiet:
                    self.stdout.write(f"  ok   {t}")
            except Exception as e:  # noqa: BLE001
                fail += 1
                if not quiet:
                    self.stdout.write(self.style.WARNING(f"  fail {t}: {e}"))

        elapsed = time.time() - t0
        self.stdout.write(self.style.SUCCESS(
            f"Done in {elapsed:.1f}s. ok={ok} fail={fail}"
        ))
