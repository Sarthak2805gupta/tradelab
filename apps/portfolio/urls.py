from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="portfolio"),
    path("add/", views.add, name="portfolio_add"),
    path("delete/<int:pk>/", views.delete, name="portfolio_delete"),
    path("export/", views.export_csv, name="portfolio_export"),
]
