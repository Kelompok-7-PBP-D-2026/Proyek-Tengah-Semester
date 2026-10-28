from django.urls import path

from . import views

app_name = "laporan"

urlpatterns = [
    path("", views.dashboard_laporan, name="dashboard"),
    path("login/", views.AdminLoginView.as_view(), name="login"),
    path("logout/", views.AdminLogoutView.as_view(), name="logout"),
    path("buat/", views.buat_laporan, name="buat"),
    path("pratinjau/", views.pratinjau_laporan, name="pratinjau"),
    path("<int:pk>/", views.detail_laporan, name="detail"),
    path("<int:pk>/edit/", views.edit_laporan, name="edit"),
    path("<int:pk>/hapus/", views.hapus_laporan, name="hapus"),
    path("<int:pk>/generate/", views.hitung_ulang_laporan, name="generate"),
    path("<int:pk>/ekspor.csv", views.ekspor_laporan_csv, name="ekspor_csv"),
    path("<int:pk>/ekspor.pdf", views.ekspor_laporan_pdf, name="ekspor_pdf"),
]
