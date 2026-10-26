"""Business rules for claims. Views stay thin and call these functions."""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from . import integrations
from .models import (
    ACTIVE_STATUSES,
    MAX_PORTIONS_PER_CLAIM,
    Claim,
    ClaimStatus,
)
from .utils import build_pickup_slots


class ClaimError(Exception):
    """A business-rule violation. The message is safe to show to the user."""


def get_claim_blocker(user, donation, remaining_portions):
    """Return a reason (Indonesian) why `user` cannot claim `donation`, or None."""
    if donation.owner_id is not None and donation.owner_id == user.pk:
        return "Kamu tidak bisa mengklaim donasimu sendiri."
    if donation.pickup_deadline <= timezone.now():
        return "Batas ambil donasi ini sudah lewat."
    if remaining_portions <= 0:
        return "Porsi donasi ini sudah habis."
    if Claim.objects.filter(
        recipient=user, donation_id=donation.id, status__in=ACTIVE_STATUSES
    ).exists():
        return "Kamu masih punya klaim aktif untuk donasi ini."
    if not build_pickup_slots(donation.pickup_deadline, start=donation.pickup_start):
        return "Batas ambil sudah terlalu dekat, belum ada slot waktu ambil."
    return None


def create_claim(*, user, donation_id, portions, pickup_time, note=""):
    """Create a claim atomically, locking the donation row to prevent overbooking."""
    try:
        with transaction.atomic():
            donation = integrations.get_donation(donation_id, lock=True)
            if donation is None:
                raise ClaimError("Donasi tidak ditemukan.")

            remaining = Claim.remaining_portions(donation.id, donation.total_portions)
            blocker = get_claim_blocker(user, donation, remaining)
            if blocker:
                raise ClaimError(blocker)
            if portions > MAX_PORTIONS_PER_CLAIM:
                raise ClaimError(f"Maksimal {MAX_PORTIONS_PER_CLAIM} porsi per klaim.")
            if portions > remaining:
                raise ClaimError(f"Porsi yang tersisa hanya {remaining}.")

            # Small grace period so a slot that just started is still accepted.
            earliest = timezone.now() - timedelta(minutes=5)
            if donation.pickup_start is not None:
                earliest = max(earliest, donation.pickup_start)
            if not (earliest <= pickup_time < donation.pickup_deadline):
                raise ClaimError("Waktu ambil tidak valid.")

            return Claim.objects.create(
                recipient=user,
                donor_id=donation.owner_id,
                donation_id=donation.id,
                food_name=donation.food_name,
                donor_name=donation.donor_name,
                pickup_location=donation.pickup_location,
                pickup_deadline=donation.pickup_deadline,
                portions=portions,
                pickup_time=pickup_time,
                note=note,
            )
    except IntegrityError:
        raise ClaimError("Kamu masih punya klaim aktif untuk donasi ini.")


def _close(claim, status):
    """Move a claim to a closed status (cancelled/rejected) and stamp the time."""
    claim.status = status
    claim.closed_at = timezone.now()
    claim.save(update_fields=["status", "closed_at", "updated_at"])


def cancel_claim(claim):
    """Cancel a claim on behalf of its recipient. Call with a locked row."""
    if not claim.can_cancel:
        raise ClaimError("Klaim ini tidak bisa dibatalkan.")
    _close(claim, ClaimStatus.CANCELLED)


def approve_claim(claim):
    """Approve a pending claim on behalf of the donor. Call with a locked row."""
    if not claim.can_approve:
        raise ClaimError("Hanya klaim berstatus Menunggu yang belum kedaluwarsa yang bisa disetujui.")
    claim.status = ClaimStatus.APPROVED
    claim.approved_at = timezone.now()
    claim.save(update_fields=["status", "approved_at", "updated_at"])


def reject_claim(claim):
    """Reject a pending claim on behalf of the donor. Call with a locked row."""
    if not claim.can_reject:
        raise ClaimError("Hanya klaim berstatus Menunggu yang bisa ditolak.")
    _close(claim, ClaimStatus.REJECTED)


def delete_claim(claim):
    """Delete a cancelled, rejected, or expired claim. Call with a locked row."""
    if not claim.can_delete:
        raise ClaimError("Hanya klaim yang dibatalkan, ditolak, atau kedaluwarsa yang bisa dihapus.")
    claim.delete()


def verify_pickup(claim):
    """Mark an approved claim as picked up after its code matched. `claim` may be None."""
    if claim is None:
        raise ClaimError("Kode ambil tidak cocok dengan klaim mana pun di donasimu.")
    if claim.status == ClaimStatus.PICKED_UP:
        raise ClaimError("Kode ini sudah dipakai, makanan sudah diambil.")
    if claim.status == ClaimStatus.PENDING:
        raise ClaimError("Klaim ini belum disetujui. Setujui dulu sebelum memverifikasi kode.")
    if claim.status in (ClaimStatus.CANCELLED, ClaimStatus.REJECTED):
        raise ClaimError("Klaim ini sudah tidak berlaku.")
    if claim.is_expired:
        raise ClaimError("Batas ambil sudah lewat, klaim dianggap tidak diambil.")
    claim.status = ClaimStatus.PICKED_UP
    claim.picked_up_at = timezone.now()
    claim.save(update_fields=["status", "picked_up_at", "updated_at"])
    return claim