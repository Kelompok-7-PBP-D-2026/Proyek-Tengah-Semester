"""Viewset DRF modul Profil Pengguna.

Read-only untuk semua pengguna terautentikasi: profil disunting lewat
halaman web (form), bukan lewat API. API ini dipakai aplikasi mobile
untuk menampilkan profil sendiri dan daftar donor.
"""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import ProfilDonor, ProfilPenerima
from .serializers import ProfilDonorSerializer, ProfilPenerimaSerializer


class ProfilDonorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProfilDonor.objects.select_related("user").all()
    serializer_class = ProfilDonorSerializer
    permission_classes = [IsAuthenticated]


class ProfilPenerimaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ProfilPenerima.objects.select_related("user").all()
    serializer_class = ProfilPenerimaSerializer
    permission_classes = [IsAuthenticated]
