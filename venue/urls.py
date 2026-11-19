from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api, views

app_name = "venue"

api_router = DefaultRouter()
api_router.register("api/venue", api.VenueViewSet, basename="api-venue")

urlpatterns = [
    path("", views.daftar, name="daftar"),
    path("tambah/", views.buat, name="buat"),
    path("api/cari-alamat/", views.cari_alamat, name="cari_alamat"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("<int:pk>/hapus/", views.hapus, name="hapus"),
    path("", include(api_router.urls)),
]
