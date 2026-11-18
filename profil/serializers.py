"""Serializer untuk endpoint DRF modul Profil Pengguna."""
from rest_framework import serializers

from .models import ProfilDonor, ProfilPenerima


class ProfilDonorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfilDonor
        fields = "__all__"


class ProfilPenerimaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfilPenerima
        fields = "__all__"
