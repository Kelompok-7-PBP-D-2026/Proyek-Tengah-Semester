from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.contrib.auth.views import LoginView, redirect_to_login
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone, translation
from django.views.decorators.http import require_GET, require_http_methods
from klaim.models import Claim, ClaimStatus
from klaim.services import expire_overdue_claims
from venue.models import Venue

from .forms import DonasiForm
from .models import Donasi
from .permissions import is_donor, is_recipient

WIB = ZoneInfo("Asia/Jakarta")
LOGIN_URL = "donasi:login"


# ===== Helper request, izin, dan context =====

def wants_json(request):
    """Membedakan request AJAX/JSON dari request halaman biasa."""
    return "application/json" in request.headers.get("Accept", "")


def donor_access_error(request):
    """Mengembalikan respons error jika pengguna bukan donor yang sah."""
    if not request.user.is_authenticated:
        if wants_json(request):
            return JsonResponse(
                {"message": "Silakan masuk untuk mengelola donasi."},
                status=401,
            )
        return redirect_to_login(request.get_full_path(), reverse(LOGIN_URL))

    if not is_donor(request.user):
        if wants_json(request):
            return JsonResponse(
                {"message": "Hanya akun donor yang dapat mengelola donasi."},
                status=403,
            )
        return render(
            request,
            "donasi/forbidden.html",
            layout_context(request),
            status=403,
        )

    return None


def layout_context(request):
    """Mengirim role pengguna yang dibutuhkan oleh kondisi pada template."""
    donor = is_donor(request.user)
    return {
        "is_donor": donor,
        "is_recipient": is_recipient(request.user),
    }


# ===== View autentikasi sementara =====

class DonasiLoginView(LoginView):
    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), **layout_context(self.request)}


# ===== Helper query dan JSON =====

def filtered_donations(request):
    """Menerapkan filter GET dan mengembalikan QuerySet beserta nilai filternya."""
    # Klaim kedaluwarsa diproses dulu agar stok yang ditampilkan selalu terbaru.
    expire_overdue_claims()
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
        # Tab Donasi Saya hanya menampilkan donasi milik akun yang sedang masuk.
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
    if filters["waktu"] == "hari_ini":
        start_date = today
        end_date = today + timedelta(days=1)
    elif filters["waktu"] == "besok":
        start_date = today + timedelta(days=1)
        end_date = start_date + timedelta(days=1)
    elif filters["waktu"] == "pekan_ini":
        start_date = today
        end_date = today + timedelta(days=7 - today.weekday())
    else:
        start_date = None
        end_date = None
        filters["waktu"] = ""

    if start_date and end_date:
        start = datetime.combine(start_date, time.min, tzinfo=WIB)
        end = datetime.combine(end_date, time.min, tzinfo=WIB)
        # Tampilkan donasi jika rentang pengambilannya bertumpang tindih dengan filter.
        items = items.filter(waktu_tersedia__lt=end, waktu_akhir_pengambilan__gt=start)

    return items, filters


def serialize_donasi(item, request):
    """Mengubah satu Donasi menjadi dictionary yang aman dikirim sebagai JSON."""
    data = {
        "id": item.pk,
        "nama": item.nama,
        "jumlah_porsi": item.jumlah_porsi,
        "lokasi": item.lokasi,
        "waktu_tersedia": item.waktu_tersedia.isoformat(),
        "waktu_akhir_pengambilan": item.waktu_akhir_pengambilan.isoformat(),
        "status": item.status,
        "status_tampilan": item.status_tampilan,
        "catatan": item.catatan,
        "url": item.get_absolute_url(),
        "foto_url": reverse("donasi:foto", args=[item.pk]) if item.foto else None,
        "can_edit": is_donor(request.user) and item.donor_id == request.user.pk,
    }
    # Identitas donor tidak diberikan kepada pengunjung yang belum login.
    if request.user.is_authenticated:
        data["donor"] = {
            "id": item.donor_id,
            "nama": item.donor.get_full_name() or item.donor.get_username(),
        }
    return data


# ===== Halaman daftar dan endpoint API =====

@require_GET
@timezone.override(WIB)
@translation.override("id")
def daftar(request):
    """Menampilkan daftar HTML atau partial card JSON untuk filter AJAX."""
    # Filter Donasi Saya bersifat pribadi, sehingga pengunjung harus login.
    if request.GET.get("mine") == "1" and not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path(), reverse(LOGIN_URL))

    items, filters = filtered_donations(request)
    # Setiap halaman berisi paling banyak enam card Donasi.
    page = Paginator(items, 6).get_page(request.GET.get("page"))
    context = {
        **layout_context(request),
        "page_obj": page,
        "filters": filters,
        # distinct() mencegah nama lokasi yang sama muncul berulang di filter.
        "lokasi_list": Donasi.objects.order_by("lokasi")
        .values_list("lokasi", flat=True)
        .distinct(),
    }
    # AJAX hanya membutuhkan potongan card; request biasa menerima halaman lengkap.
    if wants_json(request):
        html = render_to_string(
            "donasi/partials/results.html",
            context,
            request=request,
        )
        return JsonResponse(
            {
                "html": html,
                "count": page.paginator.count,
                "page": page.number,
            }
        )
    return render(request, "donasi/daftar.html", context)


@require_GET
def api_list(request):
    """Mengirim daftar Donasi sebagai data JSON untuk konsumen API."""
    if request.GET.get("mine") == "1" and not request.user.is_authenticated:
        return JsonResponse({"message": "Masuk untuk melihat donasi sendiri."}, status=401)
    items, _ = filtered_donations(request)
    page = Paginator(items, 6).get_page(request.GET.get("page"))
    results = [serialize_donasi(item, request) for item in page]
    return JsonResponse(
        {
            "results": results,
            "count": page.paginator.count,
            "page": page.number,
            "pages": page.paginator.num_pages,
        }
    )


# ===== Halaman detail =====

@require_GET
@timezone.override(WIB)
@translation.override("id")
def detail(request, pk):
    """Menampilkan satu Donasi beserta statistik Klaim dan tautan Venue."""
    item = get_object_or_404(Donasi.objects.select_related("donor"), pk=pk)
    # Jika ada klaim kedaluwarsa, kembalikan porsinya sebelum detail ditampilkan.
    if expire_overdue_claims(donation_id=item.pk):
        item.refresh_from_db(fields=["jumlah_porsi"])
    if wants_json(request):
        return JsonResponse(serialize_donasi(item, request))

    jumlah_diklaim = 0
    jumlah_diambil = 0
    # Pending dan sudah diambil dihitung sebagai pernah diklaim; hanya picked_up yang diambil.
    for claim in Claim.objects.filter(donation_id=item.pk):
        if claim.status in [ClaimStatus.PENDING, ClaimStatus.PICKED_UP]:
            jumlah_diklaim += claim.portions
        if claim.status == ClaimStatus.PICKED_UP:
            jumlah_diambil += claim.portions

    recipient = is_recipient(request.user)
    # Nama lokasi teks dicocokkan ke Venue agar detail dapat memberi tautan peta.
    venue = Venue.objects.filter(nama__iexact=item.lokasi).first()
    return render(request, "donasi/detail.html", {
        **layout_context(request), "item": item,
        "venue": venue,
        "can_edit": is_donor(request.user) and item.donor_id == request.user.pk,
        "can_claim": recipient and item.jumlah_porsi > 0 and not item.pengambilan_selesai,
        "jumlah_diklaim": jumlah_diklaim,
        "jumlah_diambil": jumlah_diambil,
    })


# ===== CRUD: buat, edit, dan hapus =====

@require_http_methods(["GET", "POST"])
def buat(request):
    """Menampilkan dan memproses form Donasi baru milik donor."""
    error = donor_access_error(request)
    if error is not None:
        return error
    return save_form(request)


@require_http_methods(["GET", "POST"])
def edit(request, pk):
    """Mengubah Donasi hanya jika user yang login adalah pemiliknya."""
    error = donor_access_error(request)
    if error is not None:
        return error
    item = get_object_or_404(Donasi, pk=pk, donor=request.user)
    return save_form(request, item)


def save_form(request, item=None):
    """Menjalankan alur form yang sama untuk fitur buat dan edit."""
    with timezone.override(WIB), translation.override("id"):
        form = DonasiForm(
            request.POST if request.method == "POST" else None,
            request.FILES or None,
            instance=item,
        )
        if request.method == "POST":
            if form.is_valid():
                # commit=False memberi kesempatan memasang donor dari user yang login.
                donation = form.save(commit=False)
                donation.donor = request.user
                donation.save()
                messages.success(request, "Donasi berhasil disimpan.")
                if wants_json(request):
                    return JsonResponse(
                        {
                            "message": "Donasi berhasil disimpan.",
                            "url": donation.get_absolute_url(),
                        },
                        status=200 if item else 201,
                    )
                return redirect(donation)
            if wants_json(request):
                return JsonResponse(
                    {
                        "errors": form.errors.get_json_data(),
                        "message": "Periksa kembali isian form.",
                    },
                    status=400,
                )
        context = {
            **layout_context(request),
            "form": form,
            "item": item,
        }
        status = 400 if request.method == "POST" else 200
        return render(request, "donasi/form.html", context, status=status)


@require_http_methods(["GET", "POST"])
def hapus(request, pk):
    """Menampilkan konfirmasi lewat GET dan menghapus Donasi lewat POST."""
    error = donor_access_error(request)
    if error is not None:
        return error
    item = get_object_or_404(Donasi, pk=pk, donor=request.user)
    if request.method == "POST":
        # GET hanya menampilkan konfirmasi; penghapusan sungguhan harus melalui POST.
        item.delete()
        messages.success(request, "Donasi berhasil dihapus.")
        if wants_json(request):
            return JsonResponse(
                {
                    "message": "Donasi berhasil dihapus.",
                    "url": reverse("donasi:daftar"),
                }
            )
        return redirect("donasi:daftar")
    return render(request, "donasi/hapus.html", {**layout_context(request), "item": item})


# ===== File foto =====

@require_GET
def foto(request, pk):
    """Mengirim file foto Donasi atau respons 404 jika tidak tersedia."""
    item = get_object_or_404(Donasi, pk=pk)
    if not item.foto:
        raise Http404("Foto tidak tersedia.")
    try:
        response = FileResponse(item.foto.open("rb"))
    except FileNotFoundError:
        raise Http404("Foto tidak ditemukan.")
    # Mencegah browser menebak tipe file unggahan sebagai konten lain.
    response["X-Content-Type-Options"] = "nosniff"
    return response
