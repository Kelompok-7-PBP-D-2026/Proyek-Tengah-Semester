from django.shortcuts import render

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
