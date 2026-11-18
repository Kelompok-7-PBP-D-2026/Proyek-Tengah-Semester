"""Viewset DRF modul Venue dan Lokasi.

Venue dikelola admin/donor lewat halaman web; API ini dipakai aplikasi
mobile untuk menampilkan daftar/detail venue. Penulisan melalui API
diizinkan untuk pengguna terautentikasi.
"""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from .models import Venue
from .serializers import VenueSerializer


class VenueViewSet(viewsets.ModelViewSet):
    queryset = Venue.objects.all()
    serializer_class = VenueSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
