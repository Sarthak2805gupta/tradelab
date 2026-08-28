from django.urls import path

from . import views

urlpatterns = [
    # Backtester — used by the Analysis page
    path("api/backtest/run", views.backtest_run, name="backtest_run"),

    # Trade Analyzer — used by the Watchlist page
    path("api/tools/trade_analyzer/stream", views.trade_analyzer_stream, name="trade_analyzer_stream"),
]
