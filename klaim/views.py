"""Views for recipients (create/list/detail/cancel) and donors (incoming claims)."""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import integrations, services
from .forms import ClaimForm
from .models import MAX_PORTIONS_PER_CLAIM, Claim, ClaimStatus
from .services import ClaimError
from .utils import normalize_pickup_code

CLAIMS_PER_PAGE = 5


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


def _build_status_filters(queryset, selected):
    """Build status filter chips with counts."""
    counts = {
        row["status"]: row["total"]
        for row in queryset.order_by().values("status").annotate(total=Count("pk"))
    }
    filters = [
        {"key": "", "label": "Semua", "count": sum(counts.values()), "active": not selected}
    ]
    for value, label in ClaimStatus.choices:
        count = counts.get(value, 0)
        if value == ClaimStatus.REJECTED and count == 0 and selected != value:
            continue  # the design only shows chips that matter
        filters.append(
            {"key": value, "label": label, "count": count, "active": selected == value}
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


# ---- recipient views -----------------------------------------------------

@login_required
def claim_create(request, donation_id):
    """Show and process the claim form for one donation."""
    if not integrations.is_recipient(request.user):
        raise PermissionDenied
    donation = integrations.get_donation(donation_id)
    if donation is None:
        raise Http404("Donasi tidak ditemukan.")

    remaining = Claim.remaining_portions(donation.id, donation.total_portions)
    blocker = services.get_claim_blocker(request.user, donation, remaining)
    if blocker:
        messages.error(request, blocker)
        return redirect("klaim:claim_list")

    form_kwargs = {"donation": donation, "remaining_portions": remaining}
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
                messages.success(request, "Klaim terkirim. Tunggu persetujuan donor ya.")
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
            "remaining": remaining,
            "max_per_claim": MAX_PORTIONS_PER_CLAIM,
            "donation_detail_url": integrations.get_donation_detail_url(donation.id),
            "donation_list_url": integrations.get_donation_list_url(),
        },
    )


@login_required
def claim_list(request):
    """List the current recipient's claims with status filters and pagination."""
    queryset = Claim.objects.filter(recipient=request.user)
    context = _filtered_page(request, queryset)
    context["donation_list_url"] = integrations.get_donation_list_url()
    return render(request, "klaim/claim_list.html", context)


@login_required
def claim_detail(request, pk):
    """Show one of the recipient's own claims: pickup code, timeline, details."""
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
    """Cancel the recipient's own pending/approved claim (returns the portions)."""
    with transaction.atomic():
        claim = _locked_claim_or_404(pk=pk, recipient=request.user)
        try:
            services.cancel_claim(claim)
        except ClaimError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Klaim berhasil dibatalkan.")
    return _redirect_back(request, "klaim:claim_list")


# ---- donor views -----------------------------------------------------------

@login_required
@donor_required
def incoming_claim_list(request):
    """List claims on the current donor's donations."""
    queryset = Claim.objects.filter(donor=request.user).select_related("recipient")
    return render(request, "klaim/incoming_claims.html", _filtered_page(request, queryset))


@login_required
@require_POST
@donor_required
def claim_approve(request, pk):
    """Approve a pending claim on the donor's own donation."""
    with transaction.atomic():
        claim = _locked_claim_or_404(pk=pk, donor=request.user)
        try:
            services.approve_claim(claim)
        except ClaimError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, f"Klaim {claim.pickup_code} disetujui.")
    return _redirect_back(request, "klaim:incoming_claim_list")


@login_required
@require_POST
@donor_required
def claim_reject(request, pk):
    """Reject a pending claim on the donor's own donation (returns the portions)."""
    with transaction.atomic():
        claim = _locked_claim_or_404(pk=pk, donor=request.user)
        try:
            services.reject_claim(claim)
        except ClaimError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, f"Klaim {claim.pickup_code} ditolak.")
    return _redirect_back(request, "klaim:incoming_claim_list")


@login_required
@require_POST
@donor_required
def claim_verify_code(request):
    """Verify a pickup code entered by the donor and mark the claim as picked up."""
    code = normalize_pickup_code(request.POST.get("pickup_code", ""))
    if not code:
        messages.error(request, "Masukkan kode ambil terlebih dahulu.")
        return redirect("klaim:incoming_claim_list")

    with transaction.atomic():
        claim = (
            Claim.objects.select_for_update()
            .filter(pickup_code=code, donor=request.user)
            .select_related("recipient")
            .first()
        )
        try:
            claim = services.verify_pickup(claim)
        except ClaimError as error:
            messages.error(request, str(error))
        else:
            messages.success(
                request,
                f"Kode {claim.pickup_code} cocok. {claim.portions} porsi "
                f"{claim.food_name} sudah diserahkan.",
            )
    return redirect("klaim:incoming_claim_list")


@login_required
@require_POST
@donor_required
def claim_delete(request, pk):
    """Delete a cancelled, rejected, or expired claim on the donor's own donation."""
    with transaction.atomic():
        claim = _locked_claim_or_404(pk=pk, donor=request.user)
        try:
            services.delete_claim(claim)
        except ClaimError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Klaim berhasil dihapus.")
    return _redirect_back(request, "klaim:incoming_claim_list")