"""Pure helper functions: time slots, pickup codes, and Indonesian formatting."""
import secrets
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

# The donation module hardcodes WIB, so slots and formatting do the same
# and do not depend on the project's TIME_ZONE setting.
WIB = ZoneInfo("Asia/Jakarta")

SLOT_MINUTES = 30
MAX_SLOTS = 48

PICKUP_CODE_PREFIX = "MBG-"
# Uppercase letters and digits without 0, O, 1, I to avoid visual confusion.
PICKUP_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PICKUP_CODE_LENGTH = 4

MONTH_ABBREVIATIONS = [
    "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
    "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
]


def ensure_aware(value):
    """Return an aware datetime, assuming WIB for naive values."""
    if value is not None and timezone.is_naive(value):
        return timezone.make_aware(value, WIB)
    return value


def to_wib(value):
    """Convert a datetime to WIB."""
    return timezone.localtime(ensure_aware(value), WIB)


def next_slot_start(now=None):
    """Return the next 30-minute boundary at or after `now` (WIB)."""
    now = to_wib(now or timezone.now())
    base = now.replace(second=0, microsecond=0)
    minutes_over = base.minute % SLOT_MINUTES
    if minutes_over or now.second or now.microsecond:
        base += timedelta(minutes=SLOT_MINUTES - minutes_over)
    return base


def build_pickup_slots(deadline, now=None, start=None):
    """Return 30-minute pickup slots strictly before `deadline`.

    Slots begin at the later of `now` and `start` (when the food becomes available).
    """
    deadline = ensure_aware(deadline)
    earliest = to_wib(now or timezone.now())
    if start is not None:
        earliest = max(earliest, to_wib(start))
    slots = []
    slot = next_slot_start(earliest)
    while slot < deadline and len(slots) < MAX_SLOTS:
        slots.append(slot)
        slot += timedelta(minutes=SLOT_MINUTES)
    return slots


def generate_pickup_code():
    """Generate a random code like MBG-7K2Q."""
    suffix = "".join(
        secrets.choice(PICKUP_CODE_ALPHABET) for _ in range(PICKUP_CODE_LENGTH)
    )
    return f"{PICKUP_CODE_PREFIX}{suffix}"


def normalize_pickup_code(raw_code):
    """Normalize user input ('7k2q', 'mbg7k2q', 'MBG-7K2Q') to 'MBG-7K2Q'."""
    code = (raw_code or "").strip().upper().replace(" ", "")
    if not code:
        return ""
    if not code.startswith(PICKUP_CODE_PREFIX):
        if code.startswith("MBG"):
            code = code[3:]
        code = f"{PICKUP_CODE_PREFIX}{code}"
    return code


def format_time(value):
    """Format as '15.00' (WIB)."""
    local = to_wib(value)
    return f"{local:%H}.{local:%M}"


def format_date_short(value):
    """Format as '16 Okt' (WIB)."""
    local = to_wib(value)
    return f"{local.day} {MONTH_ABBREVIATIONS[local.month - 1]}"


def format_datetime_short(value):
    """Format as '16 Okt, 15.00' (WIB)."""
    return f"{format_date_short(value)}, {format_time(value)}"


def format_datetime(value):
    """Format as '16 Okt 2026, 15.00' (WIB)."""
    local = to_wib(value)
    return f"{local.day} {MONTH_ABBREVIATIONS[local.month - 1]} {local.year}, {format_time(value)}"


def format_distance(value):
    """Format kilometers as '0,8 km'."""
    return f"{float(value):.1f}".replace(".", ",") + " km"