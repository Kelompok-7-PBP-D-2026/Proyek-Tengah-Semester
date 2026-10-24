from datetime import datetime, time, timedelta
from functools import wraps
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.db.models.deletion import ProtectedError
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone, translation
from django.views.decorators.http import require_GET, require_http_methods

from .forms import DonasiForm
from .models import Donasi
from .permissions import is_donor

WIB = ZoneInfo("Asia/Jakarta")
LOGIN_URL = "donasi:login"


def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


def donor_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            login = redirect_to_login(request.get_full_path(), reverse(LOGIN_URL))
            if wants_json(request):
                return JsonResponse({"message": "Sesi masuk sudah berakhir. Masuk kembali untuk melanjutkan.", "login_url": login.url}, status=401)
            return login
        if not is_donor(request.user):
            if wants_json(request):
                return JsonResponse({"message": "Hanya akun donor yang dapat mengelola donasi."}, status=403)
            return render(request, "donasi/forbidden.html", layout_context(request), status=403)
        return view(request, *args, **kwargs)
    return wrapped


def layout_context(request):
    return {"is_donor": is_donor(request.user), "csrf_cookie_name": settings.CSRF_COOKIE_NAME}


def filtered_donations(request):
    filters = {
        "q": request.GET.get("q", "").strip()[:140],
        "lokasi": request.GET.get("lokasi", "").strip()[:200],
        "waktu": request.GET.get("waktu", ""),
        "status": request.GET.get("status", ""),
        "mine": request.GET.get("mine") == "1",
    }
    items = Donasi.objects.select_related("donor")
    now = timezone.now()
    if filters["mine"]:
        items = items.filter(donor=request.user)
    else:
        items = items.filter(waktu_akhir_pengambilan__gt=now)
    if filters["q"]:
        items = items.filter(nama__icontains=filters["q"])
    if filters["lokasi"]:
        items = items.filter(lokasi=filters["lokasi"])
    if filters["status"] in Donasi.Status.values:
        if filters["status"] == Donasi.Status.TERSEDIA:
            items = items.filter(jumlah_porsi__gt=0, waktu_akhir_pengambilan__gt=now)
        else:
            items = items.filter(jumlah_porsi=0)
    else:
        filters["status"] = ""
    today = timezone.localdate(now, WIB)
    if filters["waktu"] in {"hari_ini", "besok", "pekan_ini"}:
        start_date = today + timedelta(days=1) if filters["waktu"] == "besok" else today
        end_date = today + timedelta(days=7 - today.weekday()) if filters["waktu"] == "pekan_ini" else start_date + timedelta(days=1)
        start = datetime.combine(start_date, time.min, tzinfo=WIB)
        end = datetime.combine(end_date, time.min, tzinfo=WIB)
        # Include food whose availability overlaps the chosen period.
        items = items.filter(waktu_tersedia__lt=end, waktu_akhir_pengambilan__gt=start)
    else:
        filters["waktu"] = ""
    return items, filters


def serialize_donasi(item, request):
    data = {
        "id": item.pk, "nama": item.nama, "jumlah_porsi": item.jumlah_porsi,
        "lokasi": item.lokasi, "waktu_tersedia": item.waktu_tersedia.isoformat(),
        "waktu_akhir_pengambilan": item.waktu_akhir_pengambilan.isoformat(),
        "status": item.status, "status_tampilan": item.status_tampilan,
        "catatan": item.catatan, "url": item.get_absolute_url(),
        "foto_url": reverse("donasi:foto", args=[item.pk]) if item.foto else None,
        "can_edit": is_donor(request.user) and item.donor_id == request.user.pk,
    }
    if request.user.is_authenticated:
        data["donor"] = {"id": item.donor_id, "nama": item.donor.get_full_name() or item.donor.get_username()}
    return data


@require_GET
@timezone.override(WIB)
@translation.override("id")
def daftar(request):
    if request.GET.get("mine") == "1" and not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path(), reverse(LOGIN_URL))
    items, filters = filtered_donations(request)
    page = Paginator(items, 6).get_page(request.GET.get("page"))
    context = {
        **layout_context(request), "page_obj": page, "filters": filters,
        "lokasi_list": Donasi.objects.order_by("lokasi").values_list("lokasi", flat=True).distinct(),
    }
    if wants_json(request):
        return JsonResponse({
            "html": render_to_string("donasi/partials/results.html", context, request=request),
            "count": page.paginator.count, "page": page.number,
        })
    return render(request, "donasi/daftar.html", context)


@require_GET
def api_list(request):
    if request.GET.get("mine") == "1" and not request.user.is_authenticated:
        return JsonResponse({"message": "Masuk untuk melihat donasi sendiri."}, status=401)
    items, _ = filtered_donations(request)
    page = Paginator(items, 6).get_page(request.GET.get("page"))
    return JsonResponse({"results": [serialize_donasi(item, request) for item in page],
                         "count": page.paginator.count, "page": page.number,
                         "pages": page.paginator.num_pages})


@require_GET
@timezone.override(WIB)
@translation.override("id")
def detail(request, pk):
    item = get_object_or_404(Donasi.objects.select_related("donor"), pk=pk)
    if wants_json(request):
        return JsonResponse(serialize_donasi(item, request))
    return render(request, "donasi/detail.html", {
        **layout_context(request), "item": item,
        "can_edit": is_donor(request.user) and item.donor_id == request.user.pk,
    })


@donor_required
@require_http_methods(["GET", "POST"])
def buat(request):
    return save_form(request)


@donor_required
@require_http_methods(["GET", "POST"])
def edit(request, pk):
    item = get_object_or_404(Donasi, pk=pk, donor=request.user)
    return save_form(request, item)


def save_form(request, item=None):
    with timezone.override(WIB), translation.override("id"):
        form = DonasiForm(request.POST if request.method == "POST" else None, request.FILES or None, instance=item)
        if request.method == "POST":
            if form.is_valid():
                donation = form.save(commit=False)
                donation.donor = request.user
                donation.save()
                messages.success(request, "Donasi berhasil disimpan.")
                if wants_json(request):
                    return JsonResponse({"message": "Donasi berhasil disimpan.", "url": donation.get_absolute_url()}, status=200 if item else 201)
                return redirect(donation)
            if wants_json(request):
                return JsonResponse({"errors": form.errors.get_json_data(), "message": "Periksa kembali isian form."}, status=400)
        return render(request, "donasi/form.html", {
            **layout_context(request), "form": form, "item": item,
            "lokasi_list": Donasi.objects.order_by("lokasi").values_list("lokasi", flat=True).distinct(),
        }, status=400 if request.method == "POST" else 200)


@donor_required
@require_http_methods(["GET", "POST"])
def hapus(request, pk):
    item = get_object_or_404(Donasi, pk=pk, donor=request.user)
    if request.method == "POST":
        try:
            item.delete()
        except ProtectedError:
            message = "Donasi masih memiliki data terkait dan belum dapat dihapus."
            if wants_json(request):
                return JsonResponse({"message": message}, status=409)
            return render(request, "donasi/hapus.html", {**layout_context(request), "item": item, "error": message}, status=409)
        messages.success(request, "Donasi berhasil dihapus.")
        if wants_json(request):
            return JsonResponse({"message": "Donasi berhasil dihapus.", "url": reverse("donasi:daftar")})
        return redirect("donasi:daftar")
    return render(request, "donasi/hapus.html", {**layout_context(request), "item": item})


@require_GET
def foto(request, pk):
    item = get_object_or_404(Donasi, pk=pk)
    if not item.foto:
        raise Http404("Foto tidak tersedia.")
    try:
        response = FileResponse(item.foto.open("rb"))
    except FileNotFoundError:
        raise Http404("Foto tidak ditemukan.")
    response["X-Content-Type-Options"] = "nosniff"
    return response
