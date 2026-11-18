"""Viewset DRF modul Donasi Makanan.

Donor membuat/menyunting donasi lewat halaman web; API ini dipakai
aplikasi mobile untuk menampilkan daftar/detail donasi. Penulisan
melalui API juga diizinkan dan donor di-set otomatis dari sesi.
"""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from .models import Donasi
from .serializers import DonasiSerializer


class DonasiViewSet(viewsets.ModelViewSet):
    queryset = Donasi.objects.select_related("donor").all()
    serializer_class = DonasiSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(donor=self.request.user)
