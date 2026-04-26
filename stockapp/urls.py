from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from apps.stocks import views as stock_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", stock_views.dashboard, name="dashboard"),
    path("analysis/", stock_views.analysis_view, name="analysis"),
    path("commodities/", stock_views.commodities_view, name="commodities"),
    path("risk/", stock_views.risk_analyser_view, name="risk_analyser"),
    path("live/", stock_views.live_view, name="live"),
    path("about/", stock_views.about_view, name="about"),
    path("what-if/", stock_views.what_if_view, name="what_if"),
    path("sip/", stock_views.sip_view, name="sip"),
    path("privacy/", TemplateView.as_view(template_name="privacy.html"), name="privacy"),
    path("glossary/", stock_views.glossary_view, name="glossary"),
    path("encyclopedia/", stock_views.encyclopedia_view, name="encyclopedia"),
    path("live/basket/add/", stock_views.basket_add, name="basket_add"),
    path("live/basket/remove/<int:idx>/", stock_views.basket_remove, name="basket_remove"),
    path("live/basket/clear/", stock_views.basket_clear, name="basket_clear"),
    path("watchlist/", stock_views.watchlist_view, name="watchlist"),
    path("watchlist/add/", stock_views.watchlist_add, name="watchlist_add"),
    path("watchlist/remove/<str:ticker>/", stock_views.watchlist_remove, name="watchlist_remove"),

    # JSON API namespace
    path("api/quote/<str:ticker>/", stock_views.api_quote, name="api_quote"),
    path("api/history/<str:ticker>/", stock_views.api_history, name="api_history"),
    path("api/analyze/<str:ticker>/", stock_views.api_analyze, name="api_analyze"),
    path("api/watchlist/", stock_views.api_watchlist_quotes, name="api_watchlist"),

    path("portfolio/", include("apps.portfolio.urls")),
    path("learn/", include("apps.learning.urls")),
    path("screener/", include("apps.screener.urls")),
]

handler404 = "django.views.defaults.page_not_found"
handler500 = "django.views.defaults.server_error"
