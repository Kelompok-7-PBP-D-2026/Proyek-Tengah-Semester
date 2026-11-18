from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api, views

app_name = "donasi"

api_router = DefaultRouter()
api_router.register("api/donasi", api.DonasiViewSet, basename="api-donasi")

urlpatterns = [
    path("", views.daftar, name="daftar"),
    path("api/", views.api_list, name="api_list"),
    path("buat/", views.buat, name="buat"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("<int:pk>/hapus/", views.hapus, name="hapus"),
    path("<int:pk>/foto/", views.foto, name="foto"),
    path("", include(api_router.urls)),
]
