from django.urls import path
from . import views

urlpatterns = [
    path("", views.AskAPIView.as_view(), name="api_ask"),
    path("conversations/", views.ConversationListCreateAPIView.as_view(), name="api_conversations"),
    path("conversations/<uuid:pk>/", views.ConversationDetailAPIView.as_view(), name="api_conversation_detail"),
]
