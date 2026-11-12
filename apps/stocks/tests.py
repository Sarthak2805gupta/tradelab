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
