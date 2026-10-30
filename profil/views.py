from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from donasi.models import Donasi
from .forms import (
    DaftarDonorForm,
    DaftarPenerimaForm,
    ProfilDonorForm,
    ProfilPenerimaForm,
)
from .models import JenisDonor, ProfilDonor, ProfilPenerima

def home(request):
    """Landing page dengan donasi tersedia dan dampak yang dihitung dari database."""
    # Hanya tampilkan tiga donasi terbaru yang masih bisa diklaim.
    makanan_tersedia = Donasi.objects.filter(
        jumlah_porsi__gt=0,
        waktu_akhir_pengambilan__gt=timezone.now(),
    ).select_related("donor")[:3]

    # Statistik mengikuti seluruh donasi yang pernah dibuat dan donor uniknya.
    dampak = Donasi.objects.aggregate(
        total_porsi=Sum("jumlah_porsi"),
        total_donor=Count("donor_id", distinct=True),
    )
    total_porsi = dampak["total_porsi"] or 0

    context = {
        "makanan_tersedia": makanan_tersedia,
        "total_porsi_donasi": total_porsi,
        "total_porsi_donasi_tampilan": f"{total_porsi:,}".replace(",", "."),
        "total_donor_berdonasi": dampak["total_donor"],
    }
    return render(request, "home.html", context)


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
    """Daftar donor + filter jenis (?jenis=) dan pencarian nama unit (?q=).

    Permintaan dari HTMX (header HX-Request) hanya dibalas panel hasilnya, supaya
    filter dan pencarian berjalan tanpa memuat ulang halaman.
    """
    jenis = request.GET.get("jenis", "")
    kata_kunci = request.GET.get("q", "").strip()
    donor_qs = ProfilDonor.objects.all()
    if jenis in JenisDonor.values:
        donor_qs = donor_qs.filter(jenis=jenis)
    else:
        jenis = ""
    if kata_kunci:
        donor_qs = donor_qs.filter(nama_unit__icontains=kata_kunci)

    context = {
        "donor_list": donor_qs,
        "jenis_aktif": jenis,
        "jenis_choices": JenisDonor.choices,
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
