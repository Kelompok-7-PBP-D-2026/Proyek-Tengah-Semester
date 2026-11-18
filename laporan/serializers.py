"""Serializer untuk endpoint DRF modul Laporan Dampak."""
from rest_framework import serializers

from .models import Laporan


class LaporanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Laporan
        fields = "__all__"
        read_only_fields = ["dibuat_pada", "diperbarui_pada"]
