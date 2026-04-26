from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="screener"),

    # Screener
    path("api/screener/config", views.screener_config, name="screener_config"),
    path("api/screener/stream", views.screener_stream, name="screener_stream"),

    # Backtester
    path("api/backtest/run", views.backtest_run, name="backtest_run"),

    # Stock data + news + search
    path("api/stock/data", views.stock_data, name="screener_stock_data"),
    path("api/stock/live", views.stock_live, name="screener_stock_live"),
    path("api/stock/news", views.stock_news, name="screener_stock_news"),
    path("api/search/ticker", views.search_ticker, name="screener_search_ticker"),

    # Dashboard integration
    path("api/dashboard/top-picks", views.dashboard_top_picks, name="dashboard_top_picks"),

    # Tools
    path("api/tools/confluence", views.tools_confluence, name="tools_confluence"),
    path("api/tools/sr", views.tools_sr, name="tools_sr"),
    path("api/tools/rs_ranker", views.tools_rs_ranker, name="tools_rs_ranker"),
    path("api/tools/monte_carlo", views.tools_monte_carlo, name="tools_monte_carlo"),
    path("api/tools/portfolio_risk", views.tools_portfolio_risk, name="tools_portfolio_risk"),
    path("api/tools/pairs", views.tools_pairs, name="tools_pairs"),
    path("api/tools/supertrend", views.tools_supertrend, name="tools_supertrend"),
    path("api/tools/trade_analyzer/stream", views.trade_analyzer_stream, name="trade_analyzer_stream"),
]
