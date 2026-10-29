from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "donasi"

urlpatterns = [
    path("", views.daftar, name="daftar"),
    path("masuk/", views.DonasiLoginView.as_view(template_name="donasi/login.html", next_page=reverse_lazy("donasi:daftar")), name="login"),
    path("keluar/", auth_views.LogoutView.as_view(next_page=reverse_lazy("donasi:daftar")), name="logout"),
    path("api/", views.api_list, name="api_list"),
    path("buat/", views.buat, name="buat"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("<int:pk>/hapus/", views.hapus, name="hapus"),
    path("<int:pk>/foto/", views.foto, name="foto"),
]
