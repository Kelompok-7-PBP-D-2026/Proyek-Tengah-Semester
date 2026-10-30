from django.urls import path

from . import views

app_name = "profil"

urlpatterns = [
    path("", views.home, name="home"),
    path("daftar/", views.daftar, name="daftar"),
    path("profil/", views.profil_saya, name="profil_saya"),
    path("profil/edit/", views.edit_profil, name="edit_profil"),
    path("donor/", views.daftar_donor, name="daftar_donor"),
    path("donor/<int:pk>/", views.detail_donor, name="detail_donor"),
    path("api/cari-lokasi/", views.cari_lokasi, name="cari_lokasi"),
]
