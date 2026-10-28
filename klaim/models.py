"""Models for the claim and reservation module."""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .utils import format_datetime_short, generate_pickup_code

MAX_PORTIONS_PER_CLAIM = 3
NOTE_MAX_LENGTH = 140
# A recipient may arrive up to this many minutes after the pickup time they chose.
# Set to 0 for a strict cutoff. The claim never outlives the donation's pickup deadline.
PICKUP_GRACE_MINUTES = 30


class ClaimStatus(models.TextChoices):
    """Claim lifecycle statuses (DB value -> Indonesian label)."""

    PENDING = "pending", "Menunggu"
    PICKED_UP = "picked_up", "Sudah diambil"
    CANCELLED = "cancelled", "Dibatalkan"
    EXPIRED = "expired", "Kedaluwarsa"


# Claims that still reserve portions and can be acted on.
ACTIVE_STATUSES = (ClaimStatus.PENDING,)


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
    pickup_deadline = models.DateTimeField(verbose_name="Batas ambil donasi")

    portions = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(MAX_PORTIONS_PER_CLAIM)],
        verbose_name="Jumlah porsi",
    )
    pickup_time = models.DateTimeField(verbose_name="Waktu ambil")
    expires_at = models.DateTimeField(
        verbose_name="Batas ambil klaim",
        help_text="After this moment a pending claim counts as not picked up.",
    )
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
    picked_up_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(
        null=True, blank=True, help_text="When the claim was cancelled or expired."
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Klaim"
        verbose_name_plural = "Klaim"
        indexes = [
            models.Index(fields=["recipient", "status"]),
            models.Index(fields=["donor", "status"]),
            models.Index(fields=["donation_id", "status"]),
            models.Index(fields=["status", "expires_at"]),
        ]
        constraints = [
            # DB-level safety net: one pending claim per recipient per donation.
            models.UniqueConstraint(
                fields=["recipient", "donation_id"],
                condition=Q(status="pending"),
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

    # ---- state helpers -------------------------------------------------

    @property
    def is_overdue(self):
        """True when a pending claim passed its expiry but was not yet marked expired."""
        return self.status == ClaimStatus.PENDING and timezone.now() > self.expires_at

    @property
    def is_expired(self):
        """True when the claim is expired (persisted or just overdue)."""
        return self.status == ClaimStatus.EXPIRED or self.is_overdue

    @property
    def can_cancel(self):
        """Recipient may cancel only pending claims that have not expired."""
        return self.status == ClaimStatus.PENDING and not self.is_overdue

    @property
    def can_verify(self):
        """Donor may verify the pickup code only for pending, non-expired claims."""
        return self.can_cancel

    @property
    def is_code_valid(self):
        """True while the pickup code can still be used."""
        return self.can_cancel

    # ---- display helpers -----------------------------------------------

    @property
    def display_status(self):
        """Status used for display; an overdue pending claim shows as expired."""
        return ClaimStatus.EXPIRED if self.is_overdue else ClaimStatus(self.status)

    @property
    def display_status_label(self):
        """Indonesian status label for display."""
        return self.display_status.label

    @property
    def badge_modifier(self):
        """CSS modifier for the status badge (BEM style, hyphenated)."""
        return self.display_status.value.replace("_", "-")

    def get_timeline(self):
        """Build the status timeline steps shown on the detail page."""
        steps = [
            {
                "label": "Klaim dikirim",
                "caption": format_datetime_short(self.created_at),
                "state": "done",
            }
        ]
        status = self.display_status
        if status == ClaimStatus.PICKED_UP:
            steps.append(
                {
                    "label": "Makanan diambil",
                    "caption": format_datetime_short(self.picked_up_at or self.updated_at),
                    "state": "done",
                }
            )
        elif status == ClaimStatus.CANCELLED:
            steps.append(
                {
                    "label": "Klaim dibatalkan pengguna",
                    "caption": format_datetime_short(self.closed_at or self.updated_at),
                    "state": "failed",
                }
            )
        elif status == ClaimStatus.EXPIRED:
            steps.append(
                {
                    "label": "Klaim kedaluwarsa",
                    "caption": format_datetime_short(self.closed_at or self.expires_at),
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