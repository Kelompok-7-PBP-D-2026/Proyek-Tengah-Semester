from django import template
from django.utils import timezone, translation
from django.utils.formats import date_format

register = template.Library()


@register.filter
def angka_dampak(value):
    return "—" if value is None or value == "" else f"{value:,}".replace(",", ".")


@register.filter
def tanggal_id(value):
    if not value:
        return ""
    if hasattr(value, "hour") and timezone.is_aware(value):
        value = timezone.localtime(value)
    with translation.override("id"):
        return date_format(value, "j M Y")


@register.filter
def periode_laporan(laporan):
    start, end = laporan.periode_mulai, laporan.periode_selesai
    with translation.override("id"):
        if start.year == end.year and start.month == end.month:
            return date_format(start, "F Y")
        return f"{date_format(start, 'j M Y')} – {date_format(end, 'j M Y')}"
