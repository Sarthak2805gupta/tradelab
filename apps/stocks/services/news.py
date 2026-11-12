"""
Headline feed for the Analysis page — free via yfinance, cached 30 minutes.
Extracted from the analysis view; the parsing is defensive because the
shape of yfinance's news payload varies between versions.
"""
from __future__ import annotations

from django.core.cache import cache

NEWS_CACHE_SECONDS = 30 * 60
MAX_ITEMS = 6


def _parse_item(n: dict) -> dict | None:
    item = n.get("content") or n
    title = item.get("title") or n.get("title") or ""
    publisher = (item.get("provider") or {}).get("displayName") if isinstance(item.get("provider"), dict) else (item.get("publisher") or n.get("publisher") or "")
    link = (item.get("canonicalUrl") or {}).get("url") if isinstance(item.get("canonicalUrl"), dict) else (item.get("link") or n.get("link") or "")
    pub_time = item.get("pubDate") or n.get("providerPublishTime")
    thumb = None
    tb = item.get("thumbnail")
    if isinstance(tb, dict):
        res = tb.get("resolutions") or []
        if res:
            thumb = res[0].get("url")
    synopsis = (item.get("summary") or item.get("description") or n.get("summary") or "").strip()
    if not (title and link):
        return None
    return {"title": title, "publisher": publisher, "link": link, "time": pub_time, "thumb": thumb, "synopsis": synopsis}


def fetch_news(ticker: str) -> list[dict]:
    """Return up to MAX_ITEMS parsed headlines, or [] on any failure."""
    try:
        import yfinance as yf
        key = f"news:{ticker}"
        news = cache.get(key)
        if news is None:
            raw = yf.Ticker(ticker).news or []
            news = [item for item in (_parse_item(n) for n in raw[:MAX_ITEMS]) if item]
            cache.set(key, news, NEWS_CACHE_SECONDS)
        return news
    except Exception:
        return []
