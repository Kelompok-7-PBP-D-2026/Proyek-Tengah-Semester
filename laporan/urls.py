from django.urls import path

from . import views

app_name = "laporan"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("login/", views.AdminLoginView.as_view(), name="login"),
    path("logout/", views.AdminLogoutView.as_view(), name="logout"),
    path("buat/", views.buat, name="buat"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("<int:pk>/hapus/", views.hapus, name="hapus"),
    path("<int:pk>/generate/", views.generate, name="generate"),
    path("<int:pk>/ekspor.csv", views.ekspor_csv, name="ekspor_csv"),
    path("<int:pk>/ekspor.pdf", views.ekspor_pdf, name="ekspor_pdf"),
]
