"""Business rules for claims. Views stay thin and call these functions."""
import secrets
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from . import integrations
from .models import (
    ACTIVE_STATUSES,
    MAX_PORTIONS_PER_CLAIM,
    PICKUP_GRACE_MINUTES,
    Claim,
    ClaimStatus,
)
from .utils import build_pickup_slots, normalize_pickup_code

WRONG_CODE_MESSAGE = "Kode tidak cocok. Periksa lagi dengan penerima."


class ClaimError(Exception):
    """A business-rule violation. The message is safe to show to the user."""


def calculate_expires_at(pickup_time, pickup_deadline):
    """Chosen pickup time plus grace, never later than the donation deadline."""
    return min(pickup_time + timedelta(minutes=PICKUP_GRACE_MINUTES), pickup_deadline)


def get_claim_blocker(user, donation):
    """Return a reason (Indonesian) why `user` cannot claim `donation`, or None."""
    if donation.owner_id is not None and donation.owner_id == user.pk:
        return "Kamu tidak bisa mengklaim donasimu sendiri."
    if donation.pickup_deadline <= timezone.now():
        return "Batas ambil donasi ini sudah lewat."
    if donation.available_portions <= 0:
        return "Porsi donasi ini sudah habis."
    if Claim.objects.filter(
        recipient=user, donation_id=donation.id, status__in=ACTIVE_STATUSES
    ).exists():
        return "Kamu masih punya klaim aktif untuk donasi ini."
    if not build_pickup_slots(donation.pickup_deadline, start=donation.pickup_start):
        return "Batas ambil sudah terlalu dekat, belum ada slot waktu ambil."
    return None


def _expire(claim):
    """Mark a claim expired and give its portions back. Call inside a transaction."""
    claim.status = ClaimStatus.EXPIRED
    claim.closed_at = claim.expires_at
    claim.save(update_fields=["status", "closed_at", "updated_at"])
    integrations.adjust_portions(claim.donation_id, claim.portions)


def expire_overdue_claims(*, donation_id=None):
    """Expire pending claims past their deadline and return the portions.

    Safe to call often. Returns the number of claims expired.
    """
    count = 0
    with transaction.atomic():
        overdue = Claim.objects.select_for_update().filter(
            status=ClaimStatus.PENDING, expires_at__lt=timezone.now()
        )
        if donation_id is not None:
            overdue = overdue.filter(donation_id=donation_id)
        for claim in overdue:
            _expire(claim)
            count += 1
    return count


def create_claim(*, user, donation_id, portions, pickup_time, note=""):
    """Create a claim atomically and reserve its portions on the donation."""
    try:
        with transaction.atomic():
            expire_overdue_claims(donation_id=donation_id)
            donation = integrations.get_donation(donation_id, lock=True)
            if donation is None:
                raise ClaimError("Donasi tidak ditemukan.")

            blocker = get_claim_blocker(user, donation)
            if blocker:
                raise ClaimError(blocker)
            if portions > MAX_PORTIONS_PER_CLAIM:
                raise ClaimError(f"Maksimal {MAX_PORTIONS_PER_CLAIM} porsi per klaim.")
            if portions > donation.available_portions:
                raise ClaimError(f"Porsi yang tersisa hanya {donation.available_portions}.")

            # Small grace period so a slot that just started is still accepted.
            earliest = timezone.now() - timedelta(minutes=5)
            if donation.pickup_start is not None:
                earliest = max(earliest, donation.pickup_start)
            if not (earliest <= pickup_time < donation.pickup_deadline):
                raise ClaimError("Waktu ambil tidak valid.")

            claim = Claim.objects.create(
                recipient=user,
                donor_id=donation.owner_id,
                donation_id=donation.id,
                food_name=donation.food_name,
                donor_name=donation.donor_name,
                pickup_location=donation.pickup_location,
                pickup_deadline=donation.pickup_deadline,
                portions=portions,
                pickup_time=pickup_time,
                expires_at=calculate_expires_at(pickup_time, donation.pickup_deadline),
                note=note,
            )
            integrations.adjust_portions(donation.id, -portions)
            return claim
    except IntegrityError:
        raise ClaimError(
            "Klaim tidak dapat diproses. Mungkin kamu sudah punya klaim aktif "
            "untuk donasi ini, atau porsi baru saja habis."
        )


def cancel_claim(claim):
    """Cancel a pending claim for its recipient and return the portions. Call with a locked row."""
    if claim.status == ClaimStatus.PICKED_UP:
        raise ClaimError("Makanan sudah diambil, klaim tidak bisa dibatalkan.")
    if claim.status != ClaimStatus.PENDING:
        raise ClaimError("Klaim ini sudah tidak aktif.")
    if claim.is_overdue:
        _expire(claim)
        raise ClaimError("Klaim ini sudah kedaluwarsa.")
    claim.status = ClaimStatus.CANCELLED
    claim.closed_at = timezone.now()
    claim.save(update_fields=["status", "closed_at", "updated_at"])
    integrations.adjust_portions(claim.donation_id, claim.portions)


def verify_pickup(claim, raw_code):
    """Verify the code the donor typed; on a match mark the claim as picked up.

    Portions were already reserved at claim time, so the stock does not change here.
    Call with a locked row.
    """
    if claim.status == ClaimStatus.PICKED_UP:
        raise ClaimError("Klaim ini sudah selesai, makanan sudah diambil.")
    if claim.status == ClaimStatus.CANCELLED:
        raise ClaimError("Klaim ini sudah dibatalkan oleh penerima.")
    if claim.status == ClaimStatus.EXPIRED:
        raise ClaimError("Klaim ini sudah kedaluwarsa.")
    if claim.is_overdue:
        _expire(claim)
        raise ClaimError("Klaim ini sudah kedaluwarsa.")

    entered = normalize_pickup_code(raw_code).encode()
    if not entered or not secrets.compare_digest(entered, claim.pickup_code.encode()):
        raise ClaimError(WRONG_CODE_MESSAGE)

    claim.status = ClaimStatus.PICKED_UP
    claim.picked_up_at = timezone.now()
    claim.save(update_fields=["status", "picked_up_at", "updated_at"])
    return claim