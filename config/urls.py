from django.contrib import admin
from django.urls import path, include
from apps.library.views import home_view, overview_view
from apps.core.views import HealthCheckView, HealthLiveView, HealthReadyView
from apps.assistant.views import (
    chat_view,
    AskAPIView,
    ConversationListCreateAPIView,
    ConversationDetailAPIView,
)

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),

    # Chat-first Core Interface (Public landing when logged out, Chat Home when logged in)
    path("", home_view, name="home"),
    path("overview/", overview_view, name="overview"),
    path("c/<uuid:conversation_id>/", chat_view, name="root_conversation_detail"),

    # HTML Sections
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("library/", include("apps.library.urls", namespace="library")),
    path("ask/", include("apps.assistant.urls", namespace="assistant")),

    # REST API v1
    path("api/v1/auth/", include("apps.accounts.api_urls")),
    path("api/v1/", include("apps.library.api_urls")),
    path("api/v1/ask/", AskAPIView.as_view(), name="api_ask"),
    path("api/v1/conversations/", ConversationListCreateAPIView.as_view(), name="api_conversations"),
    path("api/v1/conversations/<uuid:pk>/", ConversationDetailAPIView.as_view(), name="api_conversation_detail"),
    path("api/v1/health/", HealthCheckView.as_view(), name="api_health_check"),
    path("api/v1/health/live/", HealthLiveView.as_view(), name="api_health_live"),
    path("api/v1/health/ready/", HealthReadyView.as_view(), name="api_health_ready"),

    # Root Health Probes
    path("health/", HealthCheckView.as_view(), name="health_check"),
    path("health/live/", HealthLiveView.as_view(), name="health_live"),
    path("health/ready/", HealthReadyView.as_view(), name="health_ready"),
]
