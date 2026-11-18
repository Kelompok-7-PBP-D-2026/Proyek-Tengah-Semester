"""Viewset DRF modul Laporan Dampak.

Laporan disusun admin lewat halaman web; API ini dipakai aplikasi
mobile untuk menampilkan laporan dampak (read-only).
"""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Laporan
from .serializers import LaporanSerializer


class LaporanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Laporan.objects.all()
    serializer_class = LaporanSerializer
    permission_classes = [IsAuthenticated]
