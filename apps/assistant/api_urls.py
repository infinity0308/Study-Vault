from django.urls import path
from . import views

urlpatterns = [
    path("", views.AskAPIView.as_view(), name="api_ask"),
]
