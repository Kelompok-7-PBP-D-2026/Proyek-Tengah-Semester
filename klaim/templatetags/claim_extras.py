"""Template filters for Indonesian date, time, and distance formatting."""
from django import template

from .. import utils

register = template.Library()


@register.filter
def id_time(value):
    """Render a datetime as '15.00'."""
    return utils.format_time(value) if value else ""


@register.filter
def id_datetime(value):
    """Render a datetime as '16 Okt 2026, 15.00'."""
    return utils.format_datetime(value) if value else ""


@register.filter
def id_datetime_short(value):
    """Render a datetime as '16 Okt, 15.00'."""
    return utils.format_datetime_short(value) if value else ""


@register.filter
def id_distance(value):
    """Render kilometers as '0,8 km'."""
    return utils.format_distance(value) if value is not None else ""