from django.conf import settings
from django.db import models


class Watchlist(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="watchlist_items",
        null=True, blank=True,
    )
    ticker = models.CharField(max_length=32)
    alert_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "ticker")
        ordering = ["ticker"]

    def __str__(self):
        return f"{self.ticker} ({self.user_id})"


class PriceCache(models.Model):
    """Lightweight cache so we don't hammer yfinance more than once a minute."""
    ticker = models.CharField(max_length=32, unique=True)
    data_json = models.JSONField()
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.ticker} @ {self.last_updated:%H:%M:%S}"
