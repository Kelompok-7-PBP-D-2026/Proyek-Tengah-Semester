"""Views for recipients (create/list/detail/cancel) and donors (incoming claims)."""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from . import integrations, services
from .forms import ClaimForm
from .models import MAX_PORTIONS_PER_CLAIM, PICKUP_GRACE_MINUTES, Claim, ClaimStatus
from .services import ClaimError

CLAIMS_PER_PAGE = 5
INCOMING_CLAIMS_PER_PAGE = 10


# ---- helpers -----------------------------------------------------------

def donor_required(view):
    """Allow only donors (as defined by the donation module). Use below @login_required."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not integrations.is_donor(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


def _locked_claim_or_404(**filters):
    """Fetch a claim with a row lock (must run inside transaction.atomic())."""
    return get_object_or_404(Claim.objects.select_for_update(), **filters)


def _redirect_back(request, default_name):
    """Redirect to a safe `next` URL from POST data, else to `default_name`."""
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(target)
    return redirect(default_name)


def _status_counts(queryset):
    """Return {status: count} for a claim queryset."""
    return {
        row["status"]: row["total"]
        for row in queryset.order_by().values("status").annotate(total=Count("pk"))
    }


def _build_status_filters(queryset, selected):
    """Build status filter chips (Semua + the 4 statuses) with counts."""
    counts = _status_counts(queryset)
    filters = [
        {"key": "", "label": "Semua", "count": sum(counts.values()), "active": not selected}
    ]
    for value, label in ClaimStatus.choices:
        filters.append(
            {
                "key": value,
                "label": label,
                "count": counts.get(value, 0),
                "active": selected == value,
            }
        )
    return filters


def _filtered_page(request, queryset):
    """Apply the ?status= filter and paginate. Returns template context pieces."""
    selected = request.GET.get("status", "")
    if selected not in ClaimStatus.values:
        selected = ""
    filters = _build_status_filters(queryset, selected)
    filtered = queryset.filter(status=selected) if selected else queryset
    page_obj = Paginator(filtered, CLAIMS_PER_PAGE).get_page(request.GET.get("page"))
    return {
        "page_obj": page_obj,
        "status_filters": filters,
        "selected_status": selected,
        "extra_query": f"&status={selected}" if selected else "",
    }


@login_required
def claim_create(request, donation_id):
    """Show and process the claim form for one donation."""
    reason = integrations.recipient_block_reason(request.user)
    if reason:
        messages.error(request, reason)
        return redirect(
            integrations.get_profile_url() or integrations.get_donation_list_url() or "/"
        )
    
    services.expire_overdue_claims(donation_id=donation_id)
    donation = integrations.get_donation(donation_id)
    if donation is None:
        raise Http404("Donasi tidak ditemukan.")

    blocker = services.get_claim_blocker(request.user, donation)
    if blocker:
        messages.error(request, blocker)
        return redirect("klaim:claim_list")

    form_kwargs = {"donation": donation, "remaining_portions": donation.available_portions}
    if request.method == "POST":
        form = ClaimForm(request.POST, **form_kwargs)
        if form.is_valid():
            try:
                claim = services.create_claim(
                    user=request.user,
                    donation_id=donation.id,
                    portions=form.cleaned_data["portions"],
                    pickup_time=form.cleaned_data["pickup_time"],
                    note=form.cleaned_data["note"],
                )
            except ClaimError as error:
                form.add_error(None, str(error))
            else:
                messages.success(request, "Klaim terkirim. Tunjukkan kode ambil saat datang.")
                return redirect("klaim:claim_detail", pk=claim.pk)
    else:
        form = ClaimForm(**form_kwargs)

    return render(
        request,
        "klaim/claim_form.html",
        {
            "form": form,
            "donation": donation,
            "deadline": donation.pickup_deadline,
            "remaining": donation.available_portions,
            "max_per_claim": MAX_PORTIONS_PER_CLAIM,
            "grace_minutes": PICKUP_GRACE_MINUTES,
            "donation_detail_url": integrations.get_donation_detail_url(donation.id),
            "donation_list_url": integrations.get_donation_list_url(),
        },
    )

@require_GET
@never_cache
def claim_check(request, donation_id):
    """Tell the donation page whether the current user may open the claim form.

    Answers JSON {"ok": bool, "message": str}. Anonymous users get ok=True so the
    link proceeds and claim_create sends them to the login page. The real
    validation still happens in claim_create and services.create_claim.
    """
    if not request.user.is_authenticated:
        return JsonResponse({"ok": True})

    reason = integrations.recipient_block_reason(request.user)
    if reason is None:
        services.expire_overdue_claims(donation_id=donation_id)
        donation = integrations.get_donation(donation_id)
        if donation is None:
            reason = "Donasi tidak ditemukan."
        else:
            reason = services.get_claim_blocker(request.user, donation)
    return JsonResponse({"ok": reason is None, "message": reason or ""})

@login_required
def claim_list(request):
    """List the current recipient's claims with status filters and pagination."""
    services.expire_overdue_claims()
    queryset = Claim.objects.filter(recipient=request.user)
    context = _filtered_page(request, queryset)
    context["donation_list_url"] = integrations.get_donation_list_url()
    return render(request, "klaim/claim_list.html", context)


@login_required
def claim_detail(request, pk):
    """Show one of the recipient's own claims: pickup code, timeline, details."""
    services.expire_overdue_claims()
    claim = get_object_or_404(Claim, pk=pk, recipient=request.user)
    return render(
        request,
        "klaim/claim_detail.html",
        {
            "claim": claim,
            "timeline": claim.get_timeline(),
            # None when the donation was deleted; the claim keeps its snapshot.
            "donation_detail_url": integrations.get_donation_detail_url(claim.donation_id),
        },
    )


@login_required
@require_POST
def claim_cancel(request, pk):
    """Cancel the recipient's own pending claim (returns the portions)."""
    with transaction.atomic():
        claim = _locked_claim_or_404(pk=pk, recipient=request.user)
        try:
            services.cancel_claim(claim)
        except ClaimError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Klaim berhasil dibatalkan.")
    return _redirect_back(request, "klaim:claim_list")


@login_required
@donor_required
def incoming_claim_list(request):
    """List claims on the current donor's donations, with summary counts."""
    services.expire_overdue_claims()
    queryset = Claim.objects.filter(donor=request.user).select_related(
        "recipient", "recipient__profil_penerima"
    )
    counts = _status_counts(queryset)
    stats = [
        {"value": counts.get(ClaimStatus.PENDING, 0), "label": "klaim menunggu diambil"},
        {"value": counts.get(ClaimStatus.PICKED_UP, 0), "label": "klaim sudah diambil"},
        {
            "value": counts.get(ClaimStatus.CANCELLED, 0) + counts.get(ClaimStatus.EXPIRED, 0),
            "label": "klaim tidak diambil",
        },
    ]
    page_obj = Paginator(queryset, INCOMING_CLAIMS_PER_PAGE).get_page(request.GET.get("page"))
    return render(
        request,
        "klaim/incoming_claims.html",
        {"page_obj": page_obj, "stats": stats, "extra_query": ""},
    )


@login_required
@require_POST
@donor_required
def claim_verify_code(request, pk):
    """Verify the pickup code typed by the donor ("Setujui") and finish the claim.

    Answers JSON for the modal (AJAX) and falls back to messages + redirect.
    """
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    with transaction.atomic():
        claim = _locked_claim_or_404(pk=pk, donor=request.user)
        try:
            services.verify_pickup(claim, request.POST.get("pickup_code", ""))
        except ClaimError as error:
            success, message = False, str(error)
        else:
            success = True
            message = f"Kode cocok. {claim.portions} porsi {claim.food_name} sudah diserahkan."

    if success:
        messages.success(request, message)
    if is_ajax:
        return JsonResponse({"ok": success, "message": message}, status=200 if success else 400)
    if not success:
        messages.error(request, message)
    return redirect("klaim:incoming_claim_list")