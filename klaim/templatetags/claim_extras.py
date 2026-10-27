"""Template filters and tags for the claim module."""
from django import template
from django.urls import reverse

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

    Hidden for donors and for the donation's own owner. Disabled (reason as a
    tooltip) when the user cannot claim. Anonymous users are sent to login by
    the claim_create view.
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