from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from donasi.models import Donasi
from profil.models import ProfilDonor, ProfilPenerima

from . import osm
from .forms import VenueForm
from .models import UnitVenue, Venue
from .utils import CAMPUS_CENTER, format_km, haversine_km

User = get_user_model()


def buat_venue(nama="Lobi Gedung A", fakultas=UnitVenue.FASILKOM, lat="-6.364100", lng="106.827200", **extra):
    return Venue.objects.create(nama=nama, fakultas=fakultas, latitude=lat, longitude=lng, **extra)


def buat_donasi(donor, lokasi, porsi=40, selesai_dalam=timedelta(hours=3), nama="Nasi ayam bakar box"):
    sekarang = timezone.now()
    return Donasi.objects.create(
        donor=donor,
        nama=nama,
        jumlah_porsi=porsi,
        lokasi=lokasi,
        waktu_tersedia=sekarang - timedelta(hours=1),
        waktu_akhir_pengambilan=sekarang + selesai_dalam,
    )


class AkunMixin:
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("admin1", password="x", is_staff=True)
        cls.donor = User.objects.create_user("donor1", password="x")
        ProfilDonor.objects.create(user=cls.donor, nama_unit="BEM Fasilkom", kontak="a@b.c")
        cls.penerima = User.objects.create_user("penerima1", password="x")
        ProfilPenerima.objects.create(
            user=cls.penerima, nama_lengkap="Budi", nim="2506000001", fakultas="fasilkom", kontak="a@b.c"
        )


class UtilsTests(TestCase):
    def test_haversine_nol_dan_perkiraan(self):
        self.assertAlmostEqual(haversine_km(-6.36, 106.82, -6.36, 106.82), 0, places=6)
        # 0,01 derajat lintang kira-kira 1,11 km
        self.assertAlmostEqual(haversine_km(-6.36, 106.82, -6.35, 106.82), 1.11, places=2)

    def test_format_km_koma(self):
        self.assertEqual(format_km(0.84), "0,8")
        self.assertEqual(format_km(2.06), "2,1")


class ModelTests(TestCase):
    def test_nama_dua_warna(self):
        v = buat_venue()
        self.assertEqual((v.nama_awal, v.nama_sisa), ("Lobi", "Gedung A"))
        self.assertEqual(buat_venue(nama="Balairung", fakultas=UnitVenue.KAMPUS).nama_sisa, "")

    def test_nama_unik_per_fakultas_tanpa_beda_huruf(self):
        buat_venue()
        form = VenueForm(data={
            "nama": "lobi gedung a", "fakultas": "fasilkom", "latitude": "-6.3641", "longitude": "106.8272",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("nama", form.errors)

    def test_nama_sama_di_fakultas_lain_boleh(self):
        buat_venue()
        form = VenueForm(data={"nama": "Lobi Gedung A", "fakultas": "ft", "latitude": "-6.3", "longitude": "106.8"})
        self.assertTrue(form.is_valid(), form.errors)

    def test_koordinat_di_luar_rentang_ditolak(self):
        v = Venue(nama="X", fakultas="ft", latitude=Decimal("91"), longitude=Decimal("106"))
        with self.assertRaises(ValidationError):
            v.full_clean()


class FormTests(TestCase):
    def data(self, **kw):
        base = {"nama": "Aula FEB", "fakultas": "feb", "latitude": "-6,3588", "longitude": "106,8264"}
        base.update(kw)
        return base

    def test_koma_desimal_diterima_dan_dibulatkan(self):
        form = VenueForm(data=self.data(latitude="-6,36410049"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["latitude"], Decimal("-6.364100"))

    def test_koordinat_bukan_angka(self):
        form = VenueForm(data=self.data(latitude="abc"))
        self.assertFalse(form.is_valid())
        self.assertIn("latitude", form.errors)

    def test_fakultas_wajib(self):
        form = VenueForm(data=self.data(fakultas=""))
        self.assertFalse(form.is_valid())
        self.assertIn("fakultas", form.errors)


class DaftarTests(TestCase):
    def setUp(self):
        buat_venue()
        buat_venue("Kantin Teknik", UnitVenue.FT, "-6.3615", "106.8248")
        buat_venue("Aula FEB", UnitVenue.FEB, "-6.3588", "106.8264")
        buat_venue("Balairung", UnitVenue.KAMPUS, "-6.3682", "106.8266")
        buat_venue("Gedung B", UnitVenue.FASILKOM, "-6.3643", "106.8275")

    def test_publik_bisa_melihat_tanpa_tombol_kelola(self):
        r = self.client.get(reverse("venue:daftar"))
        self.assertContains(r, "TITIK")
        self.assertContains(r, "Lobi Gedung A")
        self.assertNotContains(r, "Tambah venue")
        self.assertEqual(len(r.context["venues"]), 5)

    def test_chip_dengan_jumlah(self):
        r = self.client.get(reverse("venue:daftar"))
        self.assertContains(r, "Semua (5)")
        self.assertContains(r, "Fasilkom (2)")
        self.assertContains(r, "Teknik (1)")
        self.assertContains(r, "FEB (1)")
        self.assertContains(r, "Kampus (1)")

    def test_filter_fakultas(self):
        r = self.client.get(reverse("venue:daftar"), {"fakultas": "fasilkom"})
        self.assertEqual({v.nama for v in r.context["venues"]}, {"Lobi Gedung A", "Gedung B"})

    def test_fakultas_tidak_valid_diabaikan(self):
        r = self.client.get(reverse("venue:daftar"), {"fakultas": "ngawur"})
        self.assertEqual(len(r.context["venues"]), 5)

    def test_cari_nama_dan_nama_fakultas(self):
        r = self.client.get(reverse("venue:daftar"), {"q": "balai"})
        self.assertEqual([v.nama for v in r.context["venues"]], ["Balairung"])
        r = self.client.get(reverse("venue:daftar"), {"q": "fasilkom"})
        self.assertEqual({v.nama for v in r.context["venues"]}, {"Lobi Gedung A", "Gedung B"})

    def test_tidak_ditemukan_tampilkan_keadaan_kosong(self):
        r = self.client.get(reverse("venue:daftar"), {"q": "Gedung Z"})
        self.assertContains(r, "Venue tidak ditemukan")
        self.assertContains(r, "Semua fakultas")
        self.assertNotContains(r, "Tambah venue")  # publik tidak melihat CTA

    def test_jarak_default_dari_pusat_kampus_dan_dari_lokasi_pengguna(self):
        r = self.client.get(reverse("venue:daftar"))
        self.assertFalse(r.context["dari_pengguna"])
        self.assertContains(r, "dari pusat kampus")
        r = self.client.get(reverse("venue:daftar"), {"lat": "-6.3641", "lng": "106.8272"})
        self.assertTrue(r.context["dari_pengguna"])
        lobi = next(v for v in r.context["venues"] if v.nama == "Lobi Gedung A")
        self.assertAlmostEqual(lobi.jarak_km, 0, places=3)

    def test_lat_lng_ngawur_kembali_ke_pusat_kampus(self):
        r = self.client.get(reverse("venue:daftar"), {"lat": "999", "lng": "abc"})
        self.assertFalse(r.context["dari_pengguna"])
        self.assertEqual(CAMPUS_CENTER, (-6.3650, 106.8280))

    def test_donor_dan_admin_melihat_tombol_kelola(self):
        admin = User.objects.create_user("adm", password="x", is_staff=True)
        self.client.force_login(admin)
        r = self.client.get(reverse("venue:daftar"))
        self.assertContains(r, "Tambah venue")
        self.assertContains(r, "Edit</a>")


class IzinTests(AkunMixin, TestCase):
    def setUp(self):
        self.venue = buat_venue()

    def test_anonim_dialihkan_ke_login(self):
        for url in (reverse("venue:buat"), reverse("venue:edit", args=[self.venue.pk])):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302)
            self.assertIn("/akun/login/", r["Location"])
        r = self.client.post(reverse("venue:hapus", args=[self.venue.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Venue.objects.filter(pk=self.venue.pk).exists())

    def test_penerima_ditolak(self):
        self.client.force_login(self.penerima)
        self.assertEqual(self.client.get(reverse("venue:buat")).status_code, 403)
        self.assertEqual(self.client.post(reverse("venue:hapus", args=[self.venue.pk])).status_code, 403)
        self.assertTrue(Venue.objects.filter(pk=self.venue.pk).exists())

    def test_donor_dan_admin_boleh(self):
        for user in (self.donor, self.admin):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("venue:buat")).status_code, 200)

    def test_hapus_hanya_post(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("venue:hapus", args=[self.venue.pk])).status_code, 405)

    def test_detail_publik_tapi_aksi_tersembunyi(self):
        r = self.client.get(reverse("venue:detail", args=[self.venue.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Edit venue")
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("venue:detail", args=[self.venue.pk])), "Edit venue")


class CrudTests(AkunMixin, TestCase):
    def test_tambah_mencatat_pembuat(self):
        self.client.force_login(self.donor)
        r = self.client.post(reverse("venue:buat"), {
            "nama": "  Lobi Gedung A ", "fakultas": "fasilkom", "latitude": "-6,3641",
            "longitude": "106,8272", "deskripsi_akses": "Dekat lift.", "alamat": "Gedung A, Fasilkom UI",
        })
        venue = Venue.objects.get()
        self.assertRedirects(r, venue.get_absolute_url())
        self.assertEqual(venue.nama, "Lobi Gedung A")
        self.assertEqual(venue.dibuat_oleh, self.donor)
        self.assertEqual(venue.latitude, Decimal("-6.364100"))

    def test_tambah_tidak_valid_menampilkan_galat(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse("venue:buat"), {"nama": "", "fakultas": "", "latitude": "", "longitude": ""})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Nama gedung wajib diisi.")
        self.assertContains(r, "Latitude wajib diisi.")
        self.assertEqual(Venue.objects.count(), 0)

    def test_edit_mempertahankan_pembuat(self):
        venue = buat_venue(dibuat_oleh=self.donor)
        self.client.force_login(self.admin)
        r = self.client.post(reverse("venue:edit", args=[venue.pk]), {
            "nama": "Lobi Gedung A Baru", "fakultas": "fasilkom", "latitude": "-6.3641", "longitude": "106.8272",
        })
        self.assertRedirects(r, venue.get_absolute_url())
        venue.refresh_from_db()
        self.assertEqual(venue.nama, "Lobi Gedung A Baru")
        self.assertEqual(venue.dibuat_oleh, self.donor)

    def test_edit_boleh_menyimpan_tanpa_mengubah_nama(self):
        venue = buat_venue()
        self.client.force_login(self.admin)
        r = self.client.post(reverse("venue:edit", args=[venue.pk]), {
            "nama": venue.nama, "fakultas": "fasilkom", "latitude": "-6.3641", "longitude": "106.8272",
        })
        self.assertEqual(r.status_code, 302)

    def test_hapus_tanpa_donasi_aktif(self):
        venue = buat_venue()
        self.client.force_login(self.admin)
        r = self.client.post(reverse("venue:hapus", args=[venue.pk]))
        self.assertRedirects(r, reverse("venue:daftar"))
        self.assertFalse(Venue.objects.exists())


class DonasiIntegrasiTests(AkunMixin, TestCase):
    def setUp(self):
        self.venue = buat_venue()

    def test_hapus_diblokir_bila_ada_donasi_aktif(self):
        buat_donasi(self.donor, "Lobi Gedung A")
        buat_donasi(self.donor, "lobi gedung a", nama="Kue basah seminar", porsi=30)
        self.client.force_login(self.admin)
        r = self.client.post(reverse("venue:hapus", args=[self.venue.pk]), follow=True)
        self.assertTrue(Venue.objects.filter(pk=self.venue.pk).exists())
        self.assertContains(r, "Ada 2 donasi aktif di venue ini. Pindahkan lokasinya dulu.")

    def test_donasi_selesai_atau_habis_tidak_menghalangi(self):
        buat_donasi(self.donor, "Lobi Gedung A", selesai_dalam=timedelta(minutes=-5))
        buat_donasi(self.donor, "Lobi Gedung A", porsi=0)
        self.client.force_login(self.admin)
        self.client.post(reverse("venue:hapus", args=[self.venue.pk]))
        self.assertFalse(Venue.objects.exists())

    def test_donasi_di_lokasi_lain_tidak_dihitung(self):
        buat_donasi(self.donor, "Aula FEB")
        r = self.client.get(reverse("venue:detail", args=[self.venue.pk]))
        self.assertContains(r, "Belum ada donasi aktif di venue ini.")

    def test_detail_menampilkan_donasi_dan_modal_peringatan(self):
        buat_donasi(self.donor, "Lobi Gedung A")
        self.client.force_login(self.admin)
        r = self.client.get(reverse("venue:detail", args=[self.venue.pk]))
        self.assertContains(r, "Donasi di venue ini")
        self.assertContains(r, "Nasi ayam bakar box")
        self.assertContains(r, "40 porsi")
        self.assertContains(r, "Ada 1 donasi aktif di venue ini. Pindahkan lokasinya dulu.")
        self.assertContains(r, "disabled")


class CariAlamatTests(AkunMixin, TestCase):
    NOMINATIM = [{
        "name": "Gedung A",
        "display_name": "Gedung A, Fasilkom UI, Kampus UI Depok, Beji, Depok, Jawa Barat, Indonesia",
        "lat": "-6.36412345", "lon": "106.82719876",
    }]

    def setUp(self):
        cache.clear()

    def test_wajib_login_dan_hak_kelola(self):
        url = reverse("venue:cari_alamat")
        self.assertEqual(self.client.get(url, {"q": "gedung"}).status_code, 401)
        self.client.force_login(self.penerima)
        self.assertEqual(self.client.get(url, {"q": "gedung"}).status_code, 403)

    def test_query_pendek_tanpa_panggilan_jaringan(self):
        self.client.force_login(self.admin)
        with mock.patch("venue.osm.requests.get") as get:
            r = self.client.get(reverse("venue:cari_alamat"), {"q": "ab"})
        self.assertEqual(r.json(), {"hasil": []})
        get.assert_not_called()

    def test_hasil_diparse_dan_di_cache(self):
        self.client.force_login(self.admin)
        respons = mock.Mock()
        respons.json.return_value = self.NOMINATIM
        respons.raise_for_status.return_value = None
        with mock.patch("venue.osm.requests.get", return_value=respons) as get:
            r1 = self.client.get(reverse("venue:cari_alamat"), {"q": "Gedung A Fasilkom"})
            r2 = self.client.get(reverse("venue:cari_alamat"), {"q": "gedung a fasilkom"})
        item = r1.json()["hasil"][0]
        self.assertEqual(item["judul"], "Gedung A")
        self.assertEqual(item["subjudul"], "Fasilkom UI, Kampus UI Depok, Beji")
        self.assertEqual((item["lat"], item["lng"]), (-6.364123, 106.827199))
        self.assertEqual(r2.json(), r1.json())
        self.assertEqual(get.call_count, 1)
        self.assertIn("User-Agent", get.call_args.kwargs["headers"])

    def test_gangguan_osm_dibalas_502(self):
        import requests
        self.client.force_login(self.admin)
        with mock.patch("venue.osm.requests.get", side_effect=requests.ConnectionError("down")):
            r = self.client.get(reverse("venue:cari_alamat"), {"q": "gedung a"})
        self.assertEqual(r.status_code, 502)
        self.assertIn("koordinat", r.json()["message"])


class SeedTests(TestCase):
    def test_seed_idempoten(self):
        from django.core.management import call_command
        call_command("seed_venue")
        call_command("seed_venue")
        self.assertEqual(Venue.objects.count(), 4)
