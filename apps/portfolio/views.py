import csv
from datetime import date
from decimal import Decimal

from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods

from .models import UserPortfolio
from apps.stocks.services import fetcher


def _user_filter(request):
    return {"user": request.user} if request.user.is_authenticated else {"user__isnull": True}


def _enrich(rows):
    out = []
    total_invested = total_current = Decimal("0")
    for r in rows:
        q = fetcher.fetch_quote(r.ticker)
        price = Decimal(str(q["price"])) if q else r.buy_price
        invested = r.buy_price * r.quantity
        current = price * r.quantity
        pnl = current - invested
        pnl_pct = (pnl / invested * 100) if invested else 0
        total_invested += invested
        total_current += current
        out.append({
            "row": r,
            "current_price": price,
            "invested": invested,
            "current": current,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
        })
    total_pnl = total_current - total_invested
    return out, {
        "invested": total_invested,
        "current": total_current,
        "pnl": total_pnl,
        "pnl_pct": (total_pnl / total_invested * 100) if total_invested else 0,
    }


def index(request):
    rows = UserPortfolio.objects.filter(**_user_filter(request))
    holdings, totals = _enrich(rows)
    # Allocation pie data
    pie = [{"label": h["row"].ticker, "value": float(h["current"])} for h in holdings]
    return render(request, "portfolio.html", {
        "holdings": holdings,
        "totals": totals,
        "pie": pie,
        "today": date.today().isoformat(),
    })


@require_http_methods(["POST"])
def add(request):
    UserPortfolio.objects.create(
        user=request.user if request.user.is_authenticated else None,
        ticker=request.POST.get("ticker", "").strip().upper(),
        buy_price=request.POST.get("buy_price") or 0,
        quantity=int(request.POST.get("quantity") or 0),
        date_bought=request.POST.get("date_bought") or date.today(),
    )
    return redirect("portfolio")


@require_http_methods(["POST"])
def delete(request, pk: int):
    UserPortfolio.objects.filter(pk=pk, **_user_filter(request)).delete()
    return redirect("portfolio")


def export_csv(request):
    rows = UserPortfolio.objects.filter(**_user_filter(request))
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="portfolio.csv"'
    w = csv.writer(response)
    w.writerow(["ticker", "buy_price", "quantity", "date_bought", "current_price", "pnl"])
    holdings, _ = _enrich(rows)
    for h in holdings:
        w.writerow([
            h["row"].ticker,
            h["row"].buy_price,
            h["row"].quantity,
            h["row"].date_bought,
            h["current_price"],
            h["pnl"],
        ])
    return response
