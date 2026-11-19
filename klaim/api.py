"""Viewset DRF modul Klaim dan Reservasi.

Penerima membuat klaim lewat API; penerima/donor hanya boleh melihat
klaim yang berhubungan dengan mereka. Pembatalan dan verifikasi kode
masih lewat halaman web sampai halaman mobile-nya jadi.
"""
from django.db.models import Q
from rest_framework import permissions, viewsets

from .models import Claim
from .serializers import ClaimSerializer


class ClaimViewSet(viewsets.ModelViewSet):
    serializer_class = ClaimSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Claim.objects.all()
        return Claim.objects.filter(Q(recipient=user) | Q(donor=user)).distinct()

    def perform_create(self, serializer):
        serializer.save(recipient=self.request.user)
