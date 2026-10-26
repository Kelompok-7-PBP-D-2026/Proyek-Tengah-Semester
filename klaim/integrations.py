"""Single adapter between the klaim app and the donation module.

Everything that touches the donation model (owned by another team member)
lives in this file. Field names below were verified against donasi/models.py.
"""
import logging
from dataclasses import dataclass
from datetime import timedelta

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db.models import F
from django.urls import NoReverseMatch, reverse

from .utils import ensure_aware, next_slot_start

logger = logging.getLogger(__name__)

# "app_label.ModelName" of the donation model.
DONATION_MODEL = "donasi.Donasi"

# Maps our keys to attribute paths on the donation model.
# Dotted paths (e.g. "venue.nama") and zero-argument callables/properties work,
# except "available_portions", which must be a plain model field (it is written to).
# None means "not available on the donation model".
FIELD_MAP = {
    "id": "pk",
    "food_name": "nama",
    # Donasi has no display-name field; the owner's full name or username is used.
    "donor_name": None,
    "pickup_location": "lokasi",
    "pickup_start": "waktu_tersedia",
    "pickup_deadline": "waktu_akhir_pengambilan",
    # REMAINING stock. Claims subtract from it, cancel/expire add back.
    "available_portions": "jumlah_porsi",
    "owner_id": "donor_id",
    "distance_km": None,
}
REQUIRED_FIELDS = (
    "id", "food_name", "pickup_location", "pickup_deadline",
    "available_portions", "owner_id",
)

# URL names in the donation app.
DONATION_DETAIL_URL_NAME = "donasi:detail"  # takes pk
DONATION_LIST_URL_NAME = "donasi:daftar"

# Demo mode (DEBUG only, when the donation model is not installed).
DEMO_DONOR_USERNAME = "demo_donor"

_MISSING = object()


@dataclass(frozen=True)
class DonationInfo:
    """Normalized donation data used by the klaim app."""

    id: int
    food_name: str
    donor_name: str
    pickup_location: str
    pickup_deadline: object
    available_portions: int
    owner_id: object
    pickup_start: object = None
    distance_km: object = None


def is_recipient(user):
    """Return True if the user may claim food.

    The donation module has no separate recipient role, so any active signed-in
    user may claim (a donor just cannot claim their own donation).
    TODO: tighten this once the profil module defines a recipient role.
    """
    return bool(user.is_authenticated and user.is_active)


def is_donor(user):
    """Return True if the user may manage incoming claims (delegates to donasi)."""
    try:
        from donasi.permissions import is_donor as donasi_is_donor
    except ImportError:
        return bool(user.is_authenticated)
    return bool(donasi_is_donor(user))


def _get_donation_model():
    """Return the donation model class, or None when it is not installed."""
    try:
        return apps.get_model(DONATION_MODEL)
    except (LookupError, ValueError):
        return None


def _read(obj, path):
    """Resolve a dotted attribute path; return _MISSING if any part is absent."""
    value = obj
    for part in path.split("."):
        if value is None:
            return None
        value = getattr(value, part, _MISSING)
        if value is _MISSING:
            return _MISSING
        if callable(value):
            value = value()
    return value


def _to_donation_info(obj):
    """Convert a donation model instance into DonationInfo using FIELD_MAP."""
    values, missing = {}, []
    for key, path in FIELD_MAP.items():
        value = _read(obj, path) if path else _MISSING
        if value is _MISSING:
            if key in REQUIRED_FIELDS:
                missing.append(f"{key} -> {path!r}")
            value = None
        values[key] = value
    if missing:
        raise ImproperlyConfigured(
            "klaim.integrations.FIELD_MAP does not match the donation model "
            f"{DONATION_MODEL}. Unresolved: {', '.join(missing)}"
        )

    donor_name = values["donor_name"]
    if not donor_name:
        owner = get_user_model().objects.filter(pk=values["owner_id"]).first()
        donor_name = (owner.get_full_name() or owner.get_username()) if owner else "Donor"

    distance = values["distance_km"]
    return DonationInfo(
        id=int(values["id"]),
        food_name=str(values["food_name"]),
        donor_name=str(donor_name),
        pickup_location=str(values["pickup_location"]),
        pickup_deadline=ensure_aware(values["pickup_deadline"]),
        available_portions=int(values["available_portions"]),
        owner_id=values["owner_id"],
        pickup_start=ensure_aware(values["pickup_start"]),
        distance_km=float(distance) if distance is not None else None,
    )


def donation_info_from_instance(donation):
    """Public wrapper: convert a donation model instance into DonationInfo."""
    return _to_donation_info(donation)


def _demo_donations():
    """Return demo donations (DEBUG only) so pages can be tested without the donation model."""
    deadline = next_slot_start() + timedelta(hours=3)
    owner_id = (
        get_user_model()
        .objects.filter(username=DEMO_DONOR_USERNAME)
        .values_list("pk", flat=True)
        .first()
    )
    return {
        1: DonationInfo(
            id=1,
            food_name="Nasi ayam bakar box",
            donor_name="BEM Fasilkom UI",
            pickup_location="Lobi Gedung A",
            pickup_deadline=deadline,
            available_portions=40,
            owner_id=owner_id,
            distance_km=0.8,
        ),
        2: DonationInfo(
            id=2,
            food_name="Roti isi dan snack",
            donor_name="UKM Pecinta Alam",
            pickup_location="Gedung Pusat Kegiatan",
            pickup_deadline=deadline + timedelta(hours=1),
            available_portions=15,
            owner_id=owner_id,
            distance_km=1.2,
        ),
    }


def get_donation(donation_id, *, lock=False):
    """Return DonationInfo for an id, or None. With lock=True the row is locked.

    `lock=True` must be called inside transaction.atomic().
    """
    model = _get_donation_model()
    if model is None:
        if settings.DEBUG:
            return _demo_donations().get(int(donation_id))
        logger.error("Donation model %s is not installed.", DONATION_MODEL)
        return None

    queryset = model._default_manager.all()
    if lock:
        queryset = queryset.select_for_update()
    obj = queryset.filter(pk=donation_id).first()
    return _to_donation_info(obj) if obj else None


def adjust_portions(donation_id, delta):
    """Add `delta` to the donation's remaining stock (negative reserves portions).

    Must run inside transaction.atomic(). Uses an F() expression so the update is
    atomic in the database. Does nothing in demo mode or when the donation was deleted.
    """
    model = _get_donation_model()
    if model is None:
        return
    field = FIELD_MAP["available_portions"]
    if not field or "." in field:
        raise ImproperlyConfigured(
            "FIELD_MAP['available_portions'] must be a plain field on the donation model."
        )
    model._default_manager.filter(pk=donation_id).update(**{field: F(field) + delta})


def _safe_reverse(url_name, *args):
    """Reverse a URL name defensively; return None when unavailable."""
    if not url_name:
        return None
    try:
        return reverse(url_name, args=args)
    except NoReverseMatch:
        return None


def get_donation_detail_url(donation_id):
    """Return the donation detail URL, or None when the donation no longer exists.

    Claims keep a snapshot, so a claim may outlive a deleted donation.
    """
    model = _get_donation_model()
    if model is not None and not model._default_manager.filter(pk=donation_id).exists():
        return None
    return _safe_reverse(DONATION_DETAIL_URL_NAME, donation_id)


def get_donation_list_url():
    """Return the donation list URL, or None if unavailable."""
    return _safe_reverse(DONATION_LIST_URL_NAME)