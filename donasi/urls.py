from django.urls import path

from . import views

app_name = "donasi"

urlpatterns = [
    path("", views.daftar, name="daftar"),
    path("api/", views.api_list, name="api_list"),
    path("buat/", views.buat, name="buat"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("<int:pk>/hapus/", views.hapus, name="hapus"),
    path("<int:pk>/foto/", views.foto, name="foto"),
]
