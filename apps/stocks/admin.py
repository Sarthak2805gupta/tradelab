from django.contrib import admin
from .models import Watchlist, PriceCache

admin.site.register(Watchlist)
admin.site.register(PriceCache)
