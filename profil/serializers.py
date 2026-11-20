"""Serializer untuk endpoint DRF modul Profil Pengguna.

Field dibatasi eksplisit. Kontak dan NIM penerima tidak ikut dikirim ke
API, sama seperti halaman web yang menyembunyikan kontak dari tamu.
"""
from rest_framework import serializers

from .models import ProfilDonor, ProfilPenerima


class ProfilDonorSerializer(serializers.ModelSerializer):
    inisial = serializers.CharField(read_only=True)
    jenis_label = serializers.CharField(source="get_jenis_display", read_only=True)

    class Meta:
        model = ProfilDonor
        fields = [
            "id",
            "nama_unit",
            "jenis",
            "jenis_label",
            "deskripsi",
            "alamat",
            "latitude",
            "longitude",
            "terverifikasi",
            "inisial",
        ]
        read_only_fields = fields


class ProfilPenerimaSerializer(serializers.ModelSerializer):
    inisial = serializers.CharField(read_only=True)
    fakultas_label = serializers.CharField(source="get_fakultas_display", read_only=True)

    class Meta:
        model = ProfilPenerima
        fields = [
            "id",
            "nama_lengkap",
            "fakultas",
            "fakultas_label",
            "terverifikasi",
            "inisial",
        ]
        read_only_fields = fields
