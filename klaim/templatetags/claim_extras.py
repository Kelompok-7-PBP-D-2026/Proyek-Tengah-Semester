"""Template filters and tags for the claim module."""
from django import template
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import format_html

from .. import integrations, services, utils

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


@register.filter
def profile_name(user):
    """Render a user's display name (recipient name, donor unit, or username)."""
    return integrations.get_user_display_name(user)


@register.filter
def profile_label(user):
    """Render a recipient as 'Rina Sari (2506 xxxx)'."""
    return integrations.get_recipient_label(user)


@register.inclusion_tag("klaim/_claim_button.html", takes_context=True)
def claim_button(context, donation):
    """Render a "Klaim" button for a donation instance.

    Hidden for donors and for the donation's own owner. When the user cannot
    claim, the button stays clickable and shows the reason in a popover.
    Anonymous users are sent to login by the claim_create view.
    """
    request = context.get("request")
    user = getattr(request, "user", None)
    url = reverse("klaim:claim_create", args=[donation.pk])

    if user is None or not user.is_authenticated:
        return {"show": True, "url": url, "blocker": None}
    if integrations.get_donor_profile(user) is not None:
        return {"show": False}

    reason = integrations.recipient_block_reason(user)
    if reason:
        return {"show": True, "url": url, "blocker": reason}

    info = integrations.donation_info_from_instance(donation)
    if info.owner_id is not None and info.owner_id == user.pk:
        return {"show": False}
    return {"show": True, "url": url, "blocker": services.get_claim_blocker(user, info)}


@register.simple_tag
def claim_button_scripts():
    """Output the script that activates the Klaim popover (use inside extra_scripts)."""
    return format_html('<script src="{}" defer></script>', static("klaim/js/claim_popover.js"))


def _venue_context(location_name):
    """Venue point and campus fallback shared by the distance tags."""
    return {
        "point": integrations.get_location_point(location_name),
        "campus": integrations.get_campus_center(),
    }


@register.inclusion_tag("klaim/_location_card.html")
def claim_location_card(location_name, show_route=True):
    """Render the "Lokasi Pengambilan" card: pickup place, map link, route and distance.

    The route mode dropdown and the distance are driven by claim_distance.js.
    With show_route=False only the place and the map link are shown.
    """
    context = _venue_context(location_name)
    context.update({"location_name": location_name, "show_route": show_route})
    return context


@register.inclusion_tag("klaim/_distance_rows.html")
def claim_distance_rows(location_name):
    """Render the "Rute" (mode dropdown) and "Jarak" rows for a <dl class="detail-list">."""
    return _venue_context(location_name)


@register.inclusion_tag("klaim/_distance_inline.html")
def claim_distance_inline(location_name):
    """Render ' · 2,1 km' for inline use. Stays hidden until a route mode is chosen."""
    return _venue_context(location_name)