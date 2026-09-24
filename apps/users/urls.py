# path: apps/users/urls.py

"""Sign-in and sign-out. User management itself stays in /admin/ (D-034)."""

from django.urls import path

from .views import PaperPlusLoginView, PaperPlusLogoutView

urlpatterns = [
    path("login/", PaperPlusLoginView.as_view(), name="login"),
    path("logout/", PaperPlusLogoutView.as_view(), name="logout"),
]
