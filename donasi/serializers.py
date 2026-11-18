"""Serializer untuk endpoint DRF modul Donasi Makanan."""
from rest_framework import serializers

from .models import Donasi


class DonasiSerializer(serializers.ModelSerializer):
    """Serialisasi donasi; status dihitung ulang karena bukan field DB."""

    status = serializers.CharField(read_only=True)

    class Meta:
        model = Donasi
        fields = "__all__"
        read_only_fields = ["donor", "dibuat_pada", "diperbarui_pada"]
