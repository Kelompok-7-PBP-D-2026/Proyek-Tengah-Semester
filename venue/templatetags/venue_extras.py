from django import template

from venue.utils import format_km

register = template.Library()


@register.filter
def koma(value, places=4):
    """Angka dengan koma desimal: -6.3641 -> '-6,3641'."""
    try:
        return f"{float(value):.{int(places)}f}".replace(".", ",")
    except (TypeError, ValueError):
        return ""


@register.filter
def km(value):
    try:
        return format_km(value)
    except (TypeError, ValueError):
        return ""
