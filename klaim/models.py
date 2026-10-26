"""Models for the claim and reservation module."""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

from .utils import format_datetime_short, generate_pickup_code

MAX_PORTIONS_PER_CLAIM = 3
NOTE_MAX_LENGTH = 140


class ClaimStatus(models.TextChoices):
    """Claim lifecycle statuses (DB value -> Indonesian label)."""

    PENDING = "pending", "Menunggu"
    APPROVED = "approved", "Disetujui"
    PICKED_UP = "picked_up", "Sudah diambil"
    CANCELLED = "cancelled", "Dibatalkan"
    REJECTED = "rejected", "Ditolak"


# Claims a recipient may still act on.
ACTIVE_STATUSES = (ClaimStatus.PENDING, ClaimStatus.APPROVED)
# Claims that keep their portions reserved.
PORTION_HOLDING_STATUSES = (
    ClaimStatus.PENDING,
    ClaimStatus.APPROVED,
    ClaimStatus.PICKED_UP,
)


class ClaimQuerySet(models.QuerySet):
    """Custom queryset helpers for Claim."""

    def holding_portions(self):
        """Return claims whose portions are still reserved."""
        return self.filter(status__in=PORTION_HOLDING_STATUSES)


class Claim(models.Model):
    """A recipient's claim on a donation, with a snapshot of the donation data."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="claims_made",
        verbose_name="Penerima",
    )
    donor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="claims_received",
        verbose_name="Donor",
    )
    # Plain integer on purpose: the donation model belongs to another member.
    donation_id = models.PositiveIntegerField(db_index=True, verbose_name="Donasi")

    # Snapshot of donation data at claim time.
    food_name = models.CharField(max_length=200, verbose_name="Makanan")
    donor_name = models.CharField(max_length=150, verbose_name="Nama donor")
    pickup_location = models.CharField(max_length=200, verbose_name="Lokasi ambil")
    pickup_deadline = models.DateTimeField(verbose_name="Batas ambil")

    portions = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(MAX_PORTIONS_PER_CLAIM)],
        verbose_name="Jumlah porsi",
    )
    pickup_time = models.DateTimeField(verbose_name="Waktu ambil")
    note = models.CharField(
        max_length=NOTE_MAX_LENGTH, blank=True, verbose_name="Catatan untuk donor"
    )
    pickup_code = models.CharField(
        max_length=8, unique=True, editable=False, verbose_name="Kode ambil"
    )
    status = models.CharField(
        max_length=20,
        choices=ClaimStatus.choices,
        default=ClaimStatus.PENDING,
        db_index=True,
        verbose_name="Status",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(
        null=True, blank=True, help_text="When the claim was cancelled or rejected."
    )

    objects = ClaimQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Klaim"
        verbose_name_plural = "Klaim"
        indexes = [
            models.Index(fields=["recipient", "status"]),
            models.Index(fields=["donor", "status"]),
            models.Index(fields=["donation_id", "status"]),
        ]
        constraints = [
            # DB-level safety net: one active claim per recipient per donation.
            models.UniqueConstraint(
                fields=["recipient", "donation_id"],
                condition=Q(status__in=["pending", "approved"]),
                name="unique_active_claim_per_donation",
            ),
            models.CheckConstraint(
                condition=Q(portions__gte=1, portions__lte=MAX_PORTIONS_PER_CLAIM),
                name="claim_portions_between_1_and_max",
            ),
        ]

    def __str__(self):
        return f"{self.pickup_code} - {self.food_name} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        """Assign a unique pickup code on first save."""
        if not self.pickup_code:
            self.pickup_code = self._generate_unique_code()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_unique_code():
        """Generate a pickup code that is not used yet."""
        for _ in range(20):
            code = generate_pickup_code()
            if not Claim.objects.filter(pickup_code=code).exists():
                return code
        raise RuntimeError("Could not generate a unique pickup code.")

    @classmethod
    def remaining_portions(cls, donation_id, total_portions):
        """Return total portions minus portions held by pending/approved/picked_up claims."""
        held = (
            cls.objects.holding_portions()
            .filter(donation_id=donation_id)
            .aggregate(total=Sum("portions"))["total"]
            or 0
        )
        return max(total_portions - held, 0)

    # ---- state helpers -------------------------------------------------

    @property
    def is_expired(self):
        """True when an active claim passed its pickup deadline (counts as not picked up)."""
        return self.status in ACTIVE_STATUSES and timezone.now() > self.pickup_deadline

    @property
    def can_cancel(self):
        """Recipient may cancel pending/approved claims that have not expired."""
        return self.status in ACTIVE_STATUSES and not self.is_expired

    @property
    def can_approve(self):
        """Donor may approve pending claims that have not expired."""
        return self.status == ClaimStatus.PENDING and not self.is_expired

    @property
    def can_reject(self):
        """Donor may reject pending claims."""
        return self.status == ClaimStatus.PENDING

    @property
    def can_delete(self):
        """Donor may delete cancelled, rejected, or expired claims."""
        return self.status in (ClaimStatus.CANCELLED, ClaimStatus.REJECTED) or self.is_expired

    @property
    def is_code_valid(self):
        """True while the pickup code can still be used."""
        return self.status in ACTIVE_STATUSES and not self.is_expired

    # ---- display helpers -----------------------------------------------

    @property
    def display_status(self):
        """Status key for display; 'expired' overrides active statuses."""
        return "expired" if self.is_expired else self.status

    @property
    def display_status_label(self):
        """Indonesian status label for display."""
        return "Kedaluwarsa" if self.is_expired else self.get_status_display()

    @property
    def badge_modifier(self):
        """CSS modifier for the status badge (BEM style, hyphenated)."""
        return self.display_status.replace("_", "-")

    def get_timeline(self):
        """Build the status timeline steps shown on the detail page."""
        steps = [
            {
                "label": "Klaim dikirim",
                "caption": format_datetime_short(self.created_at),
                "state": "done",
            }
        ]
        if self.status == ClaimStatus.REJECTED:
            steps.append(
                {
                    "label": "Ditolak donor",
                    "caption": format_datetime_short(self.closed_at or self.updated_at),
                    "state": "failed",
                }
            )
            return steps
        if self.status == ClaimStatus.CANCELLED:
            if self.approved_at:
                steps.append(
                    {
                        "label": "Disetujui donor",
                        "caption": format_datetime_short(self.approved_at),
                        "state": "done",
                    }
                )
            steps.append(
                {
                    "label": "Klaim dibatalkan",
                    "caption": format_datetime_short(self.closed_at or self.updated_at),
                    "state": "failed",
                }
            )
            return steps

        if self.approved_at:
            steps.append(
                {
                    "label": "Disetujui donor",
                    "caption": format_datetime_short(self.approved_at),
                    "state": "done",
                }
            )
        else:
            steps.append(
                {
                    "label": "Disetujui donor",
                    "caption": "Menunggu persetujuan donor",
                    "state": "pending",
                }
            )

        if self.status == ClaimStatus.PICKED_UP:
            steps.append(
                {
                    "label": "Makanan diambil",
                    "caption": format_datetime_short(self.picked_up_at or self.updated_at),
                    "state": "done",
                }
            )
        elif self.is_expired:
            steps.append(
                {
                    "label": "Tidak diambil",
                    "caption": "Batas ambil sudah lewat",
                    "state": "failed",
                }
            )
        else:
            steps.append(
                {
                    "label": "Makanan diambil",
                    "caption": "Menunggu kamu datang",
                    "state": "pending",
                }
            )
        return steps