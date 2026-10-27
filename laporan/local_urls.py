from django.urls import include, path

urlpatterns = [
    path("laporan/", include("laporan.urls")),
    path("", include("pts_project.urls")),
]
