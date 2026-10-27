from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("akun/", include("django.contrib.auth.urls")),
    path("donasi/", include("donasi.urls")),
    path("klaim/", include("klaim.urls")),
    path("venue/", include("venue.urls")),
    path("", include("profil.urls")),
]
