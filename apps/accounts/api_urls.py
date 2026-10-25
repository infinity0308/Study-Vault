from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.APILoginView.as_view(), name="api_login"),
    path("logout/", views.APILogoutView.as_view(), name="api_logout"),
    path("register/", views.APIRegisterView.as_view(), name="api_register"),
    path("me/", views.APIMeView.as_view(), name="api_me"),
    path("csrf/", views.APICSRFView.as_view(), name="api_csrf"),
]
