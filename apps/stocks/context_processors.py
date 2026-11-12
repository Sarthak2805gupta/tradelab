"""
Global context processors:
  - search_universe: ticker autocomplete data for every page
  - market_status: is the Indian equity market open right now? (Used for heading
    hover colours — green when open, red when closed.)
"""
from datetime import time as dtime
from django.utils import timezone

from apps.stocks.services.universe import SEARCH_UNIVERSE


def search_universe(request):
    return {"search_universe": SEARCH_UNIVERSE}


def market_status(request):
    now = timezone.localtime()
    is_weekday = now.weekday() < 5
    is_open = is_weekday and (dtime(9, 15) <= now.time() <= dtime(15, 30))
    return {
        "market_is_open": is_open,
        # Convenience: the Tailwind hover class to use on headings so we don't
        # have to repeat the conditional in every template.
        "heading_hover_class": "hover:text-accent" if is_open else "hover:text-danger",
    }


def oauth_providers(request):
    """Expose which social providers actually have a SocialApp row in DB.
    Templates use this to hide OAuth buttons that would otherwise 404."""
    configured = set()
    try:
        from allauth.socialaccount.models import SocialApp
        configured = set(SocialApp.objects.values_list("provider", flat=True))
    except Exception:
        pass
    return {
        "oauth_configured": configured,
        "any_oauth_configured": bool(configured),
    }
