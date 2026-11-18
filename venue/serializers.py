"""Serializer untuk endpoint DRF modul Venue dan Lokasi."""
from rest_framework import serializers

from .models import Venue


class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = "__all__"
