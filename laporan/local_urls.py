from django.urls import include, path

urlpatterns = [
    path("", include("pts_project.urls")),
]
