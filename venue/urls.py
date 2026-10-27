from django.urls import path

from . import views

app_name = "venue"

urlpatterns = [
    path("", views.daftar, name="daftar"),
    path("tambah/", views.buat, name="buat"),
    path("api/cari-alamat/", views.cari_alamat, name="cari_alamat"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("<int:pk>/hapus/", views.hapus, name="hapus"),
]
