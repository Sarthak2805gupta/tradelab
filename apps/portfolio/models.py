from django.conf import settings
from django.db import models


class UserPortfolio(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="holdings",
        null=True, blank=True,
    )
    ticker = models.CharField(max_length=32)
    buy_price = models.DecimalField(max_digits=14, decimal_places=2)
    quantity = models.PositiveIntegerField()
    date_bought = models.DateField()
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_bought"]

    def __str__(self):
        return f"{self.ticker} x{self.quantity}"

    @property
    def invested(self):
        return self.buy_price * self.quantity
