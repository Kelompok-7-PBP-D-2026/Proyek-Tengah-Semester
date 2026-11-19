from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api, views

app_name = "profil"

api_router = DefaultRouter()
api_router.register("api/profil-donor", api.ProfilDonorViewSet, basename="api-profil-donor")
api_router.register("api/profil-penerima", api.ProfilPenerimaViewSet, basename="api-profil-penerima")

urlpatterns = [
    path("", views.home, name="home"),
    path("daftar/", views.daftar, name="daftar"),
    path("profil/", views.profil_saya, name="profil_saya"),
    path("profil/edit/", views.edit_profil, name="edit_profil"),
    path("donor/", views.daftar_donor, name="daftar_donor"),
    path("donor/<int:pk>/", views.detail_donor, name="detail_donor"),
    path("api/cari-lokasi/", views.cari_lokasi, name="cari_lokasi"),
    path("", include(api_router.urls)),
]
