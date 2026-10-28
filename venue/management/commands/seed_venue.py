from django.core.management.base import BaseCommand

from venue.models import UnitVenue, Venue

# Contoh data sesuai desain Figma. Koordinat Lobi Gedung A diambil dari desain; sisanya
# perkiraan kasar, jadi cek dan perbaiki lewat form edit venue (pencarian alamat).
CONTOH = [
    ("Lobi Gedung A", UnitVenue.FASILKOM, "Gedung A, Fasilkom UI", "-6.364100", "106.827200",
     "Masuk dari pintu utama, makanan diambil di meja panitia dekat lift. Parkir motor di sisi timur."),
    ("Kantin Teknik", UnitVenue.FT, "Kantin Teknik, Fakultas Teknik UI", "-6.361500", "106.824800",
     "Ambil di konter kantin sisi barat."),
    ("Aula FEB", UnitVenue.FEB, "Aula FEB, Fakultas Ekonomi UI", "-6.358800", "106.826400",
     "Masuk lewat lobi utama, ambil di meja registrasi."),
    ("Balairung", UnitVenue.KAMPUS, "Balairung, Gedung Pusat UI", "-6.368200", "106.826600",
     "Ambil di selasar depan Balairung."),
]


class Command(BaseCommand):
    help = "Isi contoh venue (idempoten: yang sudah ada dilewati)."

    def handle(self, *args, **options):
        dibuat = 0
        for nama, fakultas, alamat, lat, lng, akses in CONTOH:
            _, baru = Venue.objects.get_or_create(
                nama=nama,
                fakultas=fakultas,
                defaults={"alamat": alamat, "latitude": lat, "longitude": lng, "deskripsi_akses": akses},
            )
            dibuat += baru
        self.stdout.write(self.style.SUCCESS(f"{dibuat} venue baru, {len(CONTOH) - dibuat} sudah ada."))
