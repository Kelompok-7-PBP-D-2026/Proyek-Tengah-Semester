"""Serializer untuk endpoint DRF modul Donasi Makanan."""
from rest_framework import serializers

from .models import Donasi
from .permissions import is_donor
from venue.models import Venue


class DonasiSerializer(serializers.ModelSerializer):
    """Serialisasi donasi; status dihitung ulang karena bukan field DB."""

    status = serializers.CharField(read_only=True)
    status_tampilan = serializers.CharField(read_only=True)
    foto_url = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = Donasi
        fields = [
            "id",
            "donor",
            "nama",
            "jumlah_porsi",
            "lokasi",
            "waktu_tersedia",
            "waktu_akhir_pengambilan",
            "foto",
            "foto_url",
            "catatan",
            "status",
            "status_tampilan",
            "can_edit",
            "dibuat_pada",
            "diperbarui_pada",
        ]
        read_only_fields = [
            "donor",
            "foto_url",
            "status",
            "status_tampilan",
            "can_edit",
            "dibuat_pada",
            "diperbarui_pada",
        ]

    def get_foto_url(self, obj):
        if not obj.foto:
            return None
        return obj.foto.url

    def get_can_edit(self, obj):
        request = self.context.get("request")
        return bool(request and is_donor(request.user) and obj.donor_id == request.user.id)

    def validate_nama(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Nama makanan wajib diisi.")
        return value

    def validate_lokasi(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Lokasi pengambilan wajib diisi.")
        if not Venue.objects.filter(nama=value).exists():
            raise serializers.ValidationError("Pilih lokasi pengambilan yang tersedia.")
        return value

    def validate(self, attrs):
        instance = self.instance
        start = attrs.get("waktu_tersedia", getattr(instance, "waktu_tersedia", None))
        end = attrs.get(
            "waktu_akhir_pengambilan",
            getattr(instance, "waktu_akhir_pengambilan", None),
        )
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"waktu_akhir_pengambilan": "Akhir pengambilan harus setelah waktu mulai pengambilan."}
            )
        return attrs
