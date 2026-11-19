"""Serializer untuk endpoint DRF modul Klaim dan Reservasi."""
from rest_framework import serializers

from . import integrations, utils
from .models import NOTE_MAX_LENGTH, Claim


def location_payload(location_name):
    """Venue coordinates so the app can compute the distance on the device, or None."""
    point = integrations.get_location_point(location_name)
    if point is None:
        return None
    return {"lat": float(point["lat"]), "lng": float(point["lng"])}


class ClaimSerializer(serializers.ModelSerializer):
    """A claim as its recipient sees it. Read-only: every change goes through services."""

    status = serializers.SerializerMethodField()
    display_status_label = serializers.CharField(read_only=True)
    can_cancel = serializers.BooleanField(read_only=True)

    class Meta:
        model = Claim
        fields = [
            "id", "donation_id", "food_name", "donor_name", "pickup_location",
            "portions", "pickup_time", "expires_at", "note", "pickup_code",
            "status", "display_status_label", "can_cancel",
            "created_at", "picked_up_at", "closed_at",
        ]
        read_only_fields = fields

    def get_status(self, obj):
        # An overdue pending claim is reported as "expired" even before it is closed.
        return obj.display_status.value


class ClaimDetailSerializer(ClaimSerializer):
    """Claim detail: adds the status timeline and the venue coordinates."""

    timeline = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()

    class Meta(ClaimSerializer.Meta):
        fields = ClaimSerializer.Meta.fields + ["timeline", "location"]
        read_only_fields = fields

    def get_timeline(self, obj):
        return obj.get_timeline()

    def get_location(self, obj):
        return location_payload(obj.pickup_location)


class IncomingClaimSerializer(serializers.ModelSerializer):
    """A claim as its donor sees it. The pickup code is deliberately NOT included."""

    status = serializers.SerializerMethodField()
    display_status_label = serializers.CharField(read_only=True)
    can_verify = serializers.BooleanField(read_only=True)
    recipient_name = serializers.SerializerMethodField()
    recipient_label = serializers.SerializerMethodField()

    class Meta:
        model = Claim
        fields = [
            "id", "food_name", "portions", "pickup_time", "expires_at", "note",
            "recipient_name", "recipient_label",
            "status", "display_status_label", "can_verify", "created_at", "picked_up_at",
        ]
        read_only_fields = fields

    def get_status(self, obj):
        return obj.display_status.value

    def get_recipient_name(self, obj):
        return integrations.get_user_display_name(obj.recipient)

    def get_recipient_label(self, obj):
        # "Rina Sari (2506 xxxx)": the NIM is masked for donors.
        return integrations.get_recipient_label(obj.recipient)


class ClaimCreateSerializer(serializers.Serializer):
    """Input for creating a claim. Mirrors ClaimForm: only portions, slot, and note."""

    donation_id = serializers.IntegerField(min_value=1)
    portions = serializers.IntegerField(min_value=1)
    pickup_time = serializers.DateTimeField()
    note = serializers.CharField(required=False, allow_blank=True, max_length=NOTE_MAX_LENGTH)

    def validate(self, attrs):
        donation = integrations.get_donation(attrs["donation_id"])
        if donation is None:
            raise serializers.ValidationError({"donation_id": "Donasi tidak ditemukan."})
        slots = utils.build_pickup_slots(donation.pickup_deadline, start=donation.pickup_start)
        # With no slots left, create_claim answers with the proper reason instead.
        if slots and attrs["pickup_time"] not in slots:
            raise serializers.ValidationError({"pickup_time": "Pilih waktu ambil yang tersedia."})
        return attrs