from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

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
    return render(request, "profil/profil_saya.html", {"donor": donor, "penerima": penerima})


@login_required
def edit_profil(request):
    """Edit profil sendiri. NIM penerima dikunci (lihat ProfilPenerimaForm)."""
    donor = ProfilDonor.objects.filter(user=request.user).first()
    penerima = ProfilPenerima.objects.filter(user=request.user).first()
    if donor is not None:
        instance, form_class = donor, ProfilDonorForm
    elif penerima is not None:
        instance, form_class = penerima, ProfilPenerimaForm
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
    return render(request, "profil/edit_profil.html", {"form": form})


def daftar_donor(request):
    """Daftar donor + filter jenis (?jenis=...)."""
    jenis = request.GET.get("jenis", "")
    donor_qs = ProfilDonor.objects.all()
    if jenis in JenisDonor.values:
        donor_qs = donor_qs.filter(jenis=jenis)
    else:
        jenis = ""
    return render(request, "profil/daftar_donor.html", {
        "donor_list": donor_qs,
        "jenis_aktif": jenis,
        "jenis_choices": JenisDonor.choices,
        "jumlah": donor_qs.count(),
    })


def detail_donor(request, pk):
    """Detail donor. Kontak hanya tampil untuk pengguna yang sudah login."""
    donor = get_object_or_404(ProfilDonor, pk=pk)
    return render(request, "profil/detail_donor.html", {"donor": donor})
