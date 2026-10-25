from django.urls import path
from . import views

app_name = "library"

urlpatterns = [
    path("", views.library_view, name="document_list"),
    path("collections/", views.collections_view, name="collections"),
    path("collections/<uuid:pk>/", views.collection_detail_view, name="collection_detail"),
    path("documents/<uuid:pk>/preview/", views.document_preview_view, name="document_preview"),
]
