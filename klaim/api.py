"""Viewsets DRF modul Klaim dan Reservasi (dipakai aplikasi Flutter).
"""
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from . import integrations, services, utils
from .models import (
    MAX_PORTIONS_PER_CLAIM,
    NOTE_MAX_LENGTH,
    PICKUP_GRACE_MINUTES,
    Claim,
    ClaimStatus,
)
from .serializers import (
    ClaimCreateSerializer,
    ClaimDetailSerializer,
    ClaimSerializer,
    IncomingClaimSerializer,
    location_payload,
)
from .services import ClaimError


class IsDonor(permissions.BasePermission):
    """Only accounts with a donor role (as defined in integrations.is_donor)."""

    message = "Hanya akun donor yang dapat mengelola klaim masuk."

    def has_permission(self, request, view):
        return integrations.is_donor(request.user)


class ClaimPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50


def _status_filter(queryset, request):
    """Apply ?status= when it is a known status; unknown values are ignored."""
    value = request.query_params.get("status", "")
    return queryset.filter(status=value) if value in ClaimStatus.values else queryset


class ClaimViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """The recipient's own claims: list, detail, create, cancel, and claim-form data."""

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ClaimPagination
    lookup_value_regex = "[0-9]+"

    def get_serializer_class(self):
        return ClaimDetailSerializer if self.action == "retrieve" else ClaimSerializer

    def get_queryset(self):
        services.expire_overdue_claims()
        queryset = Claim.objects.filter(recipient=self.request.user)
        return _status_filter(queryset, self.request)

    def create(self, request, *args, **kwargs):
        """POST /klaim/api/claim/: create a claim through services.create_claim."""
        reason = integrations.recipient_block_reason(request.user)
        if reason:
            return Response({"detail": reason}, status=status.HTTP_403_FORBIDDEN)
        serializer = ClaimCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            claim = services.create_claim(user=request.user, **serializer.validated_data)
        except ClaimError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ClaimDetailSerializer(claim).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """POST /klaim/api/claim/<id>/cancel/: cancel the recipient's own pending claim."""
        with transaction.atomic():
            claim = get_object_or_404(
                Claim.objects.select_for_update(), pk=pk, recipient=request.user
            )
            try:
                services.cancel_claim(claim)
            except ClaimError as error:
                # Answered inside atomic() so an expiry done before the error is kept.
                return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        claim.refresh_from_db()
        return Response(ClaimDetailSerializer(claim).data)

    @action(detail=False, methods=["get"], url_path=r"form/(?P<donation_id>[0-9]+)")
    def form(self, request, donation_id=None):
        """GET /klaim/api/claim/form/<donation_id>/: stock, limits, slots, or why it is blocked."""
        services.expire_overdue_claims(donation_id=int(donation_id))
        donation = integrations.get_donation(int(donation_id))
        if donation is None:
            return Response({"detail": "Donasi tidak ditemukan."}, status=status.HTTP_404_NOT_FOUND)

        blocker = integrations.recipient_block_reason(request.user) or services.get_claim_blocker(
            request.user, donation
        )
        slots = [] if blocker else utils.build_pickup_slots(
            donation.pickup_deadline, start=donation.pickup_start
        )
        return Response({
            "can_claim": blocker is None,
            "blocker": blocker,
            "donation": {
                "id": donation.id,
                "food_name": donation.food_name,
                "donor_name": donation.donor_name,
                "pickup_location": donation.pickup_location,
                "available_portions": donation.available_portions,
                "pickup_deadline": donation.pickup_deadline.isoformat(),
            },
            "max_portions": max(min(MAX_PORTIONS_PER_CLAIM, donation.available_portions), 1),
            "note_max_length": NOTE_MAX_LENGTH,
            "grace_minutes": PICKUP_GRACE_MINUTES,
            "slots": [{"value": s.isoformat(), "label": utils.format_datetime(s)} for s in slots],
            "location": location_payload(donation.pickup_location),
        })


class IncomingClaimViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Claims on the donor's own donations: list, summary stats, and code verification."""

    permission_classes = [permissions.IsAuthenticated, IsDonor]
    pagination_class = ClaimPagination
    serializer_class = IncomingClaimSerializer
    lookup_value_regex = "[0-9]+"

    def get_queryset(self):
        services.expire_overdue_claims()
        queryset = Claim.objects.filter(donor=self.request.user).select_related(
            "recipient", "recipient__profil_penerima"
        )
        return _status_filter(queryset, self.request)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """GET /klaim/api/incoming/stats/: the three summary numbers."""
        services.expire_overdue_claims()
        rows = (
            Claim.objects.filter(donor=request.user)
            .order_by().values("status").annotate(total=Count("pk"))
        )
        counts = {row["status"]: row["total"] for row in rows}
        return Response({
            "waiting": counts.get(ClaimStatus.PENDING, 0),
            "picked_up": counts.get(ClaimStatus.PICKED_UP, 0),
            "not_picked": counts.get(ClaimStatus.CANCELLED, 0) + counts.get(ClaimStatus.EXPIRED, 0),
        })

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        """POST /klaim/api/incoming/<id>/verify/ with {"pickup_code": "..."}."""
        with transaction.atomic():
            claim = get_object_or_404(
                Claim.objects.select_for_update(), pk=pk, donor=request.user
            )
            try:
                services.verify_pickup(claim, str(request.data.get("pickup_code", "")))
            except ClaimError as error:
                return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        claim.refresh_from_db()
        return Response({
            "detail": f"Kode cocok. {claim.portions} porsi {claim.food_name} sudah diserahkan.",
            "claim": IncomingClaimSerializer(claim).data,
        })