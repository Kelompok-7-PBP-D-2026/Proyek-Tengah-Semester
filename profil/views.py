from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    DaftarDonorForm,
    DaftarPenerimaForm,
    ProfilDonorForm,
    ProfilPenerimaForm,
)
from .models import JenisDonor, ProfilDonor, ProfilPenerima

MODUL_LIST = [
    {"nama": "Profil Pengguna", "pic": "Fikri"},
    {"nama": "Donasi Makanan", "pic": "Rindu"},
    {"nama": "Klaim dan Reservasi", "pic": "Kireina"},
    {"nama": "Venue dan Lokasi", "pic": "Marvin"},
    {"nama": "Laporan Dampak", "pic": "Joshua"},
]

# Angka dampak contoh — nanti diganti agregasi asli dari modul laporan (Joshua).
DAMPAK_LIST = [
    {"angka": "1.240", "label": "porsi terselamatkan semester ini"},
    {"angka": "86", "label": "acara kampus ikut berdonasi"},
    {"angka": "480 kg", "label": "sampah makanan dicegah"},
]

BULAN_INDONESIA = (
    "Januari",
    "Februari",
    "Maret",
    "April",
    "Mei",
    "Juni",
    "Juli",
    "Agustus",
    "September",
    "Oktober",
    "November",
    "Desember",
)

# Jumlah kartu donor per halaman di daftar donor (grid 3 kolom di Figma).
DONOR_PER_HALAMAN = 9


def _statistik_donor(user):
    """Angka untuk kartu statistik di halaman profil donor.

    Modul Donasi belum menyediakan API resmi, jadi angkanya dihitung langsung
    dari model Donasi. Ini satu-satunya titik ketergantungan modul Profil ke
    modul Donasi — kalau nama model/field-nya berubah, sesuaikan di sini.
    """
    from donasi.models import Donasi  # impor lokal: aman walau app belum siap

    donasi_donor = Donasi.objects.filter(donor=user)
    return {
        "donasi_dibuat": donasi_donor.count(),
        "porsi_tersedia": donasi_donor.aggregate(total=Sum("jumlah_porsi"))["total"] or 0,
        "donasi_aktif": donasi_donor.filter(
            waktu_akhir_pengambilan__gt=timezone.now()
        ).count(),
    }


def _bulan_tahun(momen):
    """Format tanggal gaya Indonesia, mis. 'Agustus 2026'.

    LANGUAGE_CODE proyek masih 'en-us', jadi nama bulan tidak bisa diambil
    langsung dari filter tanggal Django.
    """
    lokal = timezone.localtime(momen)
    return f"{BULAN_INDONESIA[lokal.month - 1]} {lokal.year}"


def home(request):
    """Halaman utama sementara: design system MBG dari Figma sudah ke-pakai di sini.
    Konten donasi menyusul dari modul Rindu (app donasi)."""
    return render(request, "home.html", {
        "modul_list": MODUL_LIST,
        "dampak": DAMPAK_LIST,
        "makanan": [],
    })


def daftar(request):
    """Daftar akun baru sebagai donor atau penerima (?peran=donor|penerima)."""
    peran = request.GET.get("peran", "donor")
    if request.method == "POST":
        peran = request.POST.get("peran", "donor")

    if peran == "penerima":
        form_class = DaftarPenerimaForm
    else:
        peran = "donor"
        form_class = DaftarDonorForm

    if request.method == "POST":
        form = form_class(request.POST)
        if form.is_valid():
            user = form.save()
            data = form.cleaned_data
            if peran == "penerima":
                ProfilPenerima.objects.create(
                    user=user,
                    nama_lengkap=data["nama_lengkap"],
                    nim=data["nim"],
                    fakultas=data["fakultas"],
                    kontak=data["kontak"],
                )
            else:
                ProfilDonor.objects.create(
                    user=user,
                    nama_unit=data["nama_unit"],
                    jenis=data["jenis"],
                    kontak=data["kontak"],
                    deskripsi=data["deskripsi"],
                )
            login(request, user)
            messages.success(request, "Akun dibuat. Selamat datang di MBG!")
            return redirect("profil:profil_saya")
    else:
        form = form_class()

    return render(request, "profil/daftar.html", {"form": form, "peran": peran})


@login_required
def profil_saya(request):
    """Lihat profil sendiri. Pengguna tanpa profil (mis. admin) diarahkan ke daftar donor."""
    donor = ProfilDonor.objects.filter(user=request.user).first()
    penerima = ProfilPenerima.objects.filter(user=request.user).first()
    if donor is None and penerima is None:
        messages.info(request, "Akunmu belum punya profil donor atau penerima.")
        return redirect("profil:daftar_donor")
    konteks = {
        "donor": donor,
        "penerima": penerima,
        "profil": donor or penerima,
        "bergabung": _bulan_tahun((donor or penerima).dibuat_pada),
    }
    if donor is not None:
        konteks["statistik"] = _statistik_donor(request.user)
    return render(request, "profil/profil_saya.html", konteks)


@login_required
def edit_profil(request):
    """Edit profil sendiri. NIM penerima dikunci (lihat ProfilPenerimaForm)."""
    donor = ProfilDonor.objects.filter(user=request.user).first()
    penerima = ProfilPenerima.objects.filter(user=request.user).first()
    if donor is not None:
        instance, form_class = donor, ProfilDonorForm
        peran = "Donor"
    elif penerima is not None:
        instance, form_class = penerima, ProfilPenerimaForm
        peran = "Penerima"
    else:
        messages.info(request, "Akunmu belum punya profil untuk diedit.")
        return redirect("profil:daftar_donor")

    if request.method == "POST":
        form = form_class(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil berhasil diperbarui.")
            return redirect("profil:profil_saya")
    else:
        form = form_class(instance=instance)
    return render(
        request,
        "profil/edit_profil.html",
        {"form": form, "peran": peran, "profil": instance},
    )


def daftar_donor(request):
    """Daftar donor + filter jenis (?jenis=) dan pencarian nama unit (?q=).

    Permintaan dari HTMX (header HX-Request) hanya dibalas panel hasilnya, supaya
    filter dan pencarian berjalan tanpa memuat ulang halaman.
    """
    jenis = request.GET.get("jenis", "")
    kata_kunci = request.GET.get("q", "").strip()
    donor_qs = ProfilDonor.objects.annotate(jumlah_donasi=Count("user__donasi")).order_by("nama_unit")
    if jenis in JenisDonor.values:
        donor_qs = donor_qs.filter(jenis=jenis)
    else:
        jenis = ""
    if kata_kunci:
        donor_qs = donor_qs.filter(nama_unit__icontains=kata_kunci)

    # Angka di chip filter dihitung dari seluruh donor (bukan hasil filter),
    # supaya angkanya tidak berubah-ubah saat pengguna memilih kategori.
    chips_jenis = [{"nilai": "", "label": "Semua", "jumlah": ProfilDonor.objects.count()}]
    for nilai, label in JenisDonor.choices:
        chips_jenis.append(
            {
                "nilai": nilai,
                "label": label,
                "jumlah": ProfilDonor.objects.filter(jenis=nilai).count(),
            }
        )

    halaman = Paginator(donor_qs, DONOR_PER_HALAMAN).get_page(request.GET.get("page"))

    context = {
        "donor_list": halaman,
        "halaman": halaman,
        "jenis_aktif": jenis,
        "jenis_choices": JenisDonor.choices,
        "chips_jenis": chips_jenis,
        "kata_kunci": kata_kunci,
        "jumlah": donor_qs.count(),
    }
    if request.headers.get("HX-Request") == "true":
        return render(request, "profil/partials/daftar_donor_panel.html", context)
    return render(request, "profil/daftar_donor.html", context)


def detail_donor(request, pk):
    """Detail donor. Kontak hanya tampil untuk pengguna yang sudah login."""
    donor = get_object_or_404(ProfilDonor, pk=pk)
    return render(request, "profil/detail_donor.html", {"donor": donor})
