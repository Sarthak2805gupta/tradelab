from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="learning"),
    path("<slug:slug>/", views.module_detail, name="learning_module"),
    path("<slug:slug>/quiz/", views.submit_quiz, name="learning_quiz"),
]
