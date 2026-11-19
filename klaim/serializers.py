"""Serializer untuk endpoint DRF modul Klaim dan Reservasi."""
from rest_framework import serializers

from .models import Claim


class ClaimSerializer(serializers.ModelSerializer):
    """Serialisasi klaim; kode ambil & status diatur sisi server."""

    display_status_label = serializers.CharField(read_only=True)

    class Meta:
        model = Claim
        fields = "__all__"
        read_only_fields = [
            "recipient",
            "donor",
            "pickup_code",
            "status",
            "picked_up_at",
            "closed_at",
            "created_at",
            "updated_at",
        ]
