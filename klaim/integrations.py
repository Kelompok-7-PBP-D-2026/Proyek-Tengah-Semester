"""Single adapter between the klaim app and the donation, profile, and venue modules.

Everything that touches the donation model (donasi), the user profiles (profil),
or the venues (venue), all owned by other team members, lives in this file.
Field names below were verified against donasi/models.py, profil/models.py,
and venue/models.py.
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

# ---- donation module (donasi) ---------------------------------------------

# "app_label.ModelName" of the donation model.
DONATION_MODEL = "donasi.Donasi"

# Maps our keys to attribute paths on the donation model.
# Dotted paths (e.g. "donor.profil_donor.nama_unit") and zero-argument
# callables/properties work, except "available_portions", which must be a plain
# model field (it is written to). A path that cannot be resolved is treated as
# missing, and optional keys then fall back to a default.
FIELD_MAP = {
    "id": "pk",
    "food_name": "nama",
    # Organisation name from the donor's profile; falls back to the owner's name.
    "donor_name": "donor.profil_donor.nama_unit",
    "pickup_location": "lokasi",
    "pickup_start": "waktu_tersedia",
    "pickup_deadline": "waktu_akhir_pengambilan",
    # REMAINING stock. Claims subtract from it, cancel/expire add back.
    "available_portions": "jumlah_porsi",
    "owner_id": "donor_id",
    # Distance is not stored: it is computed in the browser (see claim_distance.js).
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

# ---- profile module (profil) ----------------------------------------------

# Reverse OneToOne names defined in profil/models.py.
DONOR_PROFILE_ATTR = "profil_donor"
RECIPIENT_PROFILE_ATTR = "profil_penerima"
PROFILE_URL_NAME = "profil:profil_saya"

# Set to True to require admin verification ("terverifikasi") before acting.
REQUIRE_VERIFIED_DONOR = False
REQUIRE_VERIFIED_RECIPIENT = False

# Donors see a masked NIM like "2506 xxxx". Set to None to show the full NIM.
NIM_VISIBLE_DIGITS = 4

# ---- venue module (venue) ---------------------------------------------------

# Donasi.lokasi stores the venue name as text, so a claim's pickup_location is
# matched to Venue.nama (case-insensitive). If two venues share a name across
# faculties, the one with the lowest id is used.
VENUE_MODEL = "venue.Venue"
VENUE_NAME_FIELD = "nama"
VENUE_LATITUDE_FIELD = "latitude"
VENUE_LONGITUDE_FIELD = "longitude"
VENUE_DETAIL_URL_NAME = "venue:detail"  

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


# ---- roles and display names ------------------------------------------------

def _get_profile(user, attr):
    """Return a related profile, or None when the user has none.

    A missing reverse OneToOne raises RelatedObjectDoesNotExist, which is an
    AttributeError, so getattr's default catches it.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    return getattr(user, attr, None)


def get_donor_profile(user):
    """Return the user's donor profile or None."""
    return _get_profile(user, DONOR_PROFILE_ATTR)


def get_recipient_profile(user):
    """Return the user's recipient profile or None."""
    return _get_profile(user, RECIPIENT_PROFILE_ATTR)


def recipient_block_reason(user):
    """Return an Indonesian reason why `user` may not claim food, or None."""
    if not (user.is_authenticated and user.is_active):
        return "Masuk dulu untuk mengklaim makanan."
    profile = get_recipient_profile(user)
    if profile is None:
        if get_donor_profile(user) is not None:
            return "Akun donor tidak bisa mengklaim makanan. Gunakan akun penerima."
        return "Lengkapi profil penerima dulu sebelum mengklaim makanan."
    if REQUIRE_VERIFIED_RECIPIENT and not profile.terverifikasi:
        return "Akun penerimamu belum diverifikasi admin."
    return None


def is_recipient(user):
    """Return True if the user may claim food (has a recipient profile)."""
    return recipient_block_reason(user) is None


def is_donor(user):
    """Return True if the user may manage incoming claims.

    Uses the donor profile. Accounts without any profile (e.g. older accounts or
    superusers managed through the donasi module) fall back to donasi.permissions.
    """
    if not (user.is_authenticated and user.is_active):
        return False
    if get_recipient_profile(user) is not None:
        return False  # one role per account
    profile = get_donor_profile(user)
    if profile is not None:
        return profile.terverifikasi or not REQUIRE_VERIFIED_DONOR
    try:
        from donasi.permissions import is_donor as donasi_is_donor
    except ImportError:
        return False
    return bool(donasi_is_donor(user))


def get_user_display_name(user):
    """Best human name: recipient full name, donor unit name, full name, or username."""
    recipient = get_recipient_profile(user)
    if recipient is not None and recipient.nama_lengkap:
        return recipient.nama_lengkap
    donor = get_donor_profile(user)
    if donor is not None and donor.nama_unit:
        return donor.nama_unit
    return user.get_full_name() or user.get_username()


def mask_nim(nim):
    """Mask a NIM for display, e.g. '2506000001' -> '2506 xxxx'."""
    nim = str(nim).strip()
    if NIM_VISIBLE_DIGITS is None:
        return nim
    return f"{nim[:NIM_VISIBLE_DIGITS]} xxxx"


def get_recipient_label(user):
    """Return 'Name (masked NIM)' for a recipient, or just the name."""
    name = get_user_display_name(user)
    profile = get_recipient_profile(user)
    if profile is None or not profile.nim:
        return name
    return f"{name} ({mask_nim(profile.nim)})"


# ---- donation access --------------------------------------------------------

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
        donor_name = get_user_display_name(owner) if owner else "Donor"

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


# ---- venue access -----------------------------------------------------------

def _get_venue_model():
    """Return the venue model class, or None when it is not installed."""
    try:
        return apps.get_model(VENUE_MODEL)
    except (LookupError, ValueError):
        return None


def get_location_point(location_name):
    """Return the venue point for a pickup location, or None.

    Result: {'lat': '-6.364500', 'lng': '106.828700', 'url': '/venue/3/'}.
    The coordinates are strings with a dot as decimal separator so they can be put
    safely in HTML data attributes regardless of the active locale. `url` is the
    venue detail page (map and route), or None when that route is unavailable.
    Returns None when the venue module is missing, the name is empty, or no
    venue matches.
    """
    model = _get_venue_model()
    name = (location_name or "").strip()
    if model is None or not name:
        return None
    venue = (
        model._default_manager.filter(**{f"{VENUE_NAME_FIELD}__iexact": name})
        .order_by("pk")
        .first()
    )
    if venue is None:
        return None
    lat = getattr(venue, VENUE_LATITUDE_FIELD, None)
    lng = getattr(venue, VENUE_LONGITUDE_FIELD, None)
    if lat is None or lng is None:
        return None
    return {
        "lat": f"{float(lat):.6f}",
        "lng": f"{float(lng):.6f}",
        "url": _safe_reverse(VENUE_DETAIL_URL_NAME, venue.pk),
    }

def get_campus_center():
    """Return the campus center as {'lat': ..., 'lng': ...} strings, or None.

    Used as the fallback start point when the browser cannot share the viewer's
    location. Reuses the venue module's CAMPUS_CENTER.
    """
    try:
        from venue.utils import CAMPUS_CENTER
    except ImportError:
        return None
    return {"lat": f"{CAMPUS_CENTER[0]:.6f}", "lng": f"{CAMPUS_CENTER[1]:.6f}"}


# ---- URLs -------------------------------------------------------------------

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


def get_profile_url():
    """Return the current user's profile page URL, or None if unavailable."""
    return _safe_reverse(PROFILE_URL_NAME)