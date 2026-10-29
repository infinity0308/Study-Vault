from django.urls import path
from . import views

app_name = "assistant"

urlpatterns = [
    path("", views.chat_view, name="ask"),
    path("c/<uuid:conversation_id>/", views.chat_view, name="conversation_detail"),
]
