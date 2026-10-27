from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from . import integrations, osm
from .forms import VenueForm
from .models import SINGKAT, UnitVenue, Venue
from .permissions import can_manage_venue
from .utils import format_km, haversine_km, origin_from_request


def _akses_ditolak(request):
    """Kembalikan response penolakan, atau None bila pengguna boleh mengelola venue."""
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    if not can_manage_venue(request.user):
        return render(request, "venue/forbidden.html", status=403)
    return None


def _kode_unit_cocok(kata_kunci):
    """Kode fakultas/unit yang namanya memuat kata kunci (agar 'Fasilkom' ikut mencari unit)."""
    q = kata_kunci.lower()
    return [
        kode
        for kode, label in UnitVenue.choices
        if q in label.lower() or q in SINGKAT[kode].lower()
    ]


def _tambah_jarak(venue, asal_lat, asal_lng):
    venue.jarak_km = haversine_km(asal_lat, asal_lng, venue.latitude, venue.longitude)
    venue.jarak_teks = format_km(venue.jarak_km)
    return venue


def daftar(request):
    """Titik pengambilan: filter fakultas (?fakultas=), pencarian (?q=), peta, dan jarak.

    Permintaan HTMX hanya mengambil bagian #venue-layout dari halaman penuh (hx-select),
    jadi tanpa JavaScript halaman tetap berfungsi sebagai form GET biasa.
    """
    q = request.GET.get("q", "").strip()[:100]
    fakultas = request.GET.get("fakultas", "")
    if fakultas not in UnitVenue.values:
        fakultas = ""

    jumlah = {
        row["fakultas"]: row["n"]
        for row in Venue.objects.values("fakultas").annotate(n=Count("pk"))
    }
    chips = [
        {"kode": kode, "singkat": SINGKAT[kode], "n": jumlah[kode]}
        for kode, _ in UnitVenue.choices
        if jumlah.get(kode)
    ]

    # Urutan input (sama seperti desain Figma); Meta.ordering (nama) hanya untuk admin.
    queryset = Venue.objects.order_by("pk")
    if fakultas:
        queryset = queryset.filter(fakultas=fakultas)
    if q:
        queryset = queryset.filter(
            Q(nama__icontains=q)
            | Q(alamat__icontains=q)
            | Q(fakultas__in=_kode_unit_cocok(q))
        )

    asal_lat, asal_lng, dari_pengguna = origin_from_request(request)
    venues = [_tambah_jarak(v, asal_lat, asal_lng) for v in queryset]
    markers = [
        {
            "id": v.pk,
            "nama": v.nama,
            "unit": v.unit_singkat,
            "lat": float(v.latitude),
            "lng": float(v.longitude),
            "url": v.get_absolute_url(),
        }
        for v in venues
    ]
    return render(request, "venue/daftar.html", {
        "venues": venues,
        "markers": markers,
        "chips": chips,
        "total": sum(jumlah.values()),
        "q": q,
        "fakultas_aktif": fakultas,
        "unit_choices": UnitVenue.choices,
        "dari_pengguna": dari_pengguna,
        "can_manage": can_manage_venue(request.user),
    })


def detail(request, pk):
    venue = get_object_or_404(Venue, pk=pk)
    asal_lat, asal_lng, dari_pengguna = origin_from_request(request)
    _tambah_jarak(venue, asal_lat, asal_lng)
    donasi = list(integrations.donasi_di_venue(venue))
    return render(request, "venue/detail.html", {
        "venue": venue,
        "dari_pengguna": dari_pengguna,
        "donasi_list": donasi[:3],
        "donasi_jumlah": len(donasi),
        "donasi_aktif": integrations.jumlah_donasi_aktif(venue),
        "can_manage": can_manage_venue(request.user),
    })


def buat(request):
    ditolak = _akses_ditolak(request)
    if ditolak:
        return ditolak
    if request.method == "POST":
        form = VenueForm(request.POST)
        if form.is_valid():
            venue = form.save(commit=False)
            venue.dibuat_oleh = request.user
            venue.save()
            messages.success(request, f"Venue “{venue.nama}” berhasil disimpan.")
            return redirect(venue)
    else:
        form = VenueForm()
    return render(request, "venue/form.html", {"form": form, "mode": "buat"})


def edit(request, pk):
    ditolak = _akses_ditolak(request)
    if ditolak:
        return ditolak
    venue = get_object_or_404(Venue, pk=pk)
    if request.method == "POST":
        form = VenueForm(request.POST, instance=venue)
        if form.is_valid():
            venue = form.save()
            messages.success(request, f"Venue “{venue.nama}” berhasil diperbarui.")
            return redirect(venue)
    else:
        form = VenueForm(instance=venue)
    return render(request, "venue/form.html", {"form": form, "venue": venue, "mode": "edit"})


@require_POST
def hapus(request, pk):
    ditolak = _akses_ditolak(request)
    if ditolak:
        return ditolak
    venue = get_object_or_404(Venue, pk=pk)
    aktif = integrations.jumlah_donasi_aktif(venue)
    if aktif:
        messages.error(
            request,
            f"Ada {aktif} donasi aktif di venue ini. Pindahkan lokasinya dulu.",
        )
        return redirect(venue)
    nama = venue.nama
    venue.delete()
    messages.success(request, f"Venue “{nama}” dihapus.")
    return redirect("venue:daftar")


@require_GET
def cari_alamat(request):
    """Proksi pencarian alamat OpenStreetMap (Nominatim) untuk form venue."""
    if not request.user.is_authenticated:
        return JsonResponse({"message": "Masuk dulu untuk mencari alamat."}, status=401)
    if not can_manage_venue(request.user):
        return JsonResponse({"message": "Hanya admin dan donor yang dapat mencari alamat."}, status=403)
    q = request.GET.get("q", "").strip()
    if len(q) < 3:
        return JsonResponse({"hasil": []})
    try:
        hasil = osm.cari_alamat(q)
    except osm.OSMError:
        return JsonResponse(
            {"message": "Pencarian OpenStreetMap sedang tidak tersedia. Isi koordinat secara manual."},
            status=502,
        )
    return JsonResponse({"hasil": hasil})
