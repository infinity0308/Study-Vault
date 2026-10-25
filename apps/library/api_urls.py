from django.urls import path
from . import views

urlpatterns = [
    # Documents
    path("documents/", views.DocumentListCreateAPIView.as_view(), name="api_documents"),
    path("documents/<uuid:pk>/", views.DocumentDetailAPIView.as_view(), name="api_document_detail"),
    path("documents/<uuid:pk>/retry/", views.DocumentRetryAPIView.as_view(), name="api_document_retry"),
    # Collections
    path("collections/", views.CollectionListCreateAPIView.as_view(), name="api_collections"),
    path("collections/<uuid:pk>/", views.CollectionDetailAPIView.as_view(), name="api_collection_detail"),
]
