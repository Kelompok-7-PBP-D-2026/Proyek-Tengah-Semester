from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import JenisDonor, ProfilDonor, ProfilPenerima


class HomeViewTest(TestCase):
    def test_home_status_200(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_home_uses_base_template(self):
        response = self.client.get("/")
        self.assertTemplateUsed(response, "base.html")


class ProfilModelTest(TestCase):
    def test_profil_donor_str_menyertakan_jenis(self):
        user = User.objects.create_user("panitia1", password="rahasia-123")
        donor = ProfilDonor.objects.create(
            user=user,
            nama_unit="BEM Fasilkom",
            jenis=JenisDonor.HIMPUNAN,
            kontak="bem@cs.ui.ac.id",
        )
        self.assertEqual(str(donor), "BEM Fasilkom (Himpunan / UKM)")

    def test_nim_penerima_unik(self):
        from django.db import IntegrityError, transaction

        u1 = User.objects.create_user("mhs1", password="rahasia-123")
        u2 = User.objects.create_user("mhs2", password="rahasia-123")
        ProfilPenerima.objects.create(
            user=u1, nama_lengkap="A", nim="2506000001", fakultas="fasilkom", kontak="a@x"
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProfilPenerima.objects.create(
                user=u2, nama_lengkap="B", nim="2506000001", fakultas="fasilkom", kontak="b@x"
            )


class DaftarDonorViewTest(TestCase):
    def setUp(self):
        self.url = reverse("profil:daftar")

    def test_daftar_donor_membuat_user_dan_profil(self):
        response = self.client.post(self.url, {
            "peran": "donor",
            "username": "kantin_fk",
            "email": "kantin@ui.ac.id",
            "password1": "sandi-kuat-789",
            "password2": "sandi-kuat-789",
            "nama_unit": "Kantin FK",
            "jenis": JenisDonor.KANTIN,
            "kontak": "0812-0000-0000",
            "deskripsi": "Kantin fakultas kedokteran.",
        })
        self.assertRedirects(response, reverse("profil:profil_saya"))
        self.assertTrue(ProfilDonor.objects.filter(user__username="kantin_fk").exists())

    def test_daftar_penerima_membuat_profil_penerima(self):
        self.client.post(self.url, {
            "peran": "penerima",
            "username": "mhs_fasilkom",
            "email": "mhs@ui.ac.id",
            "password1": "sandi-kuat-789",
            "password2": "sandi-kuat-789",
            "nama_lengkap": "Fikri",
            "nim": "2506621655",
            "fakultas": "fasilkom",
            "kontak": "fikri@ui.ac.id",
        })
        self.assertTrue(ProfilPenerima.objects.filter(nim="2506621655").exists())


class DaftarDonorListTest(TestCase):
    def setUp(self):
        u1 = User.objects.create_user("u1", password="rahasia-123")
        u2 = User.objects.create_user("u2", password="rahasia-123")
        ProfilDonor.objects.create(
            user=u1, nama_unit="Kantin Fasilkom",
            jenis=JenisDonor.KANTIN, kontak="k@x",
        )
        ProfilDonor.objects.create(
            user=u2, nama_unit="Panitia Wisuda",
            jenis=JenisDonor.PANITIA, kontak="p@x",
        )

    def test_daftar_menampilkan_semua_donor(self):
        response = self.client.get(reverse("profil:daftar_donor"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kantin Fasilkom")
        self.assertContains(response, "Panitia Wisuda")

    def test_filter_jenis(self):
        response = self.client.get(reverse("profil:daftar_donor"), {"jenis": "kantin"})
        self.assertContains(response, "Kantin Fasilkom")
        self.assertNotContains(response, "Panitia Wisuda")

    def test_empty_state_untuk_jenis_tanpa_donor(self):
        response = self.client.get(reverse("profil:daftar_donor"), {"jenis": "katering"})
        self.assertContains(response, "Belum ada donor terdaftar")


class DaftarDonorHtmxTest(TestCase):
    """Filter dan pencarian daftar donor lewat HTMX (tanpa memuat ulang halaman)."""

    def setUp(self):
        u1 = User.objects.create_user("u1", password="rahasia-123")
        u2 = User.objects.create_user("u2", password="rahasia-123")
        ProfilDonor.objects.create(
            user=u1, nama_unit="Kantin Fasilkom",
            jenis=JenisDonor.KANTIN, kontak="k@x",
        )
        ProfilDonor.objects.create(
            user=u2, nama_unit="Panitia Wisuda",
            jenis=JenisDonor.PANITIA, kontak="p@x",
        )

    def test_permintaan_htmx_hanya_membalas_panel(self):
        response = self.client.get(reverse("profil:daftar_donor"), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "profil/partials/daftar_donor_panel.html")
        self.assertTemplateNotUsed(response, "base.html")
        self.assertNotContains(response, "<html")

    def test_permintaan_biasa_mengembalikan_halaman_penuh(self):
        response = self.client.get(reverse("profil:daftar_donor"))
        self.assertTemplateUsed(response, "base.html")
        self.assertContains(response, "<html")

    def test_filter_jenis_lewat_htmx(self):
        response = self.client.get(
            reverse("profil:daftar_donor"), {"jenis": "kantin"}, HTTP_HX_REQUEST="true"
        )
        self.assertContains(response, "Kantin Fasilkom")
        self.assertNotContains(response, "Panitia Wisuda")

    def test_pencarian_nama_unit(self):
        response = self.client.get(
            reverse("profil:daftar_donor"), {"q": "wisuda"}, HTTP_HX_REQUEST="true"
        )
        self.assertContains(response, "Panitia Wisuda")
        self.assertNotContains(response, "Kantin Fasilkom")

    def test_filter_dan_pencarian_bersamaan(self):
        response = self.client.get(
            reverse("profil:daftar_donor"), {"jenis": "kantin", "q": "wisuda"},
            HTTP_HX_REQUEST="true",
        )
        self.assertNotContains(response, "Kantin Fasilkom")
        self.assertContains(response, "Belum ada donor terdaftar")

    def test_panel_memuat_atribut_dan_jenis_aktif(self):
        response = self.client.get(reverse("profil:daftar_donor"), {"jenis": "kantin"})
        self.assertContains(response, 'id="daftar-donor-panel"')
        self.assertContains(response, 'hx-target="#daftar-donor-panel"')
        self.assertContains(response, 'name="jenis" value="kantin"')


class HtmxAssetTest(TestCase):
    def test_htmx_dimuat_di_base_template(self):
        response = self.client.get("/")
        self.assertContains(response, "htmx.min.js")


class DetailDonorAuthTest(TestCase):
    def setUp(self):
        user = User.objects.create_user("kontakku", password="rahasia-123")
        self.donor = ProfilDonor.objects.create(
            user=user, nama_unit="Katering X",
            jenis=JenisDonor.KATERING, kontak="NOMOR-RAHASIA-123",
        )
        self.url = reverse("profil:detail_donor", args=[self.donor.pk])

    def test_kontak_disembunyikan_untuk_tamu(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "NOMOR-RAHASIA-123")

    def test_kontak_tampil_untuk_user_login(self):
        self.client.login(username="kontakku", password="rahasia-123")
        response = self.client.get(self.url)
        self.assertContains(response, "NOMOR-RAHASIA-123")

    def test_detail_404_untuk_id_tidak_ada(self):
        response = self.client.get(reverse("profil:detail_donor", args=[9999]))
        self.assertEqual(response.status_code, 404)


class ProfilSayaAuthTest(TestCase):
    def test_profil_saya_wajib_login(self):
        response = self.client.get(reverse("profil:profil_saya"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/akun/login/", response.url)

    def test_edit_profil_donor_memperbarui_data(self):
        user = User.objects.create_user("edit1", password="rahasia-123")
        ProfilDonor.objects.create(
            user=user, nama_unit="Lama", jenis=JenisDonor.PANITIA, kontak="lama@x",
        )
        self.client.login(username="edit1", password="rahasia-123")
        self.client.post(reverse("profil:edit_profil"), {
            "nama_unit": "Baru",
            "jenis": JenisDonor.HIMPUNAN,
            "kontak": "baru@x",
            "deskripsi": "",
        })
        self.assertEqual(ProfilDonor.objects.get(user=user).nama_unit, "Baru")


class InisialProfilTest(TestCase):
    """Properti inisial dipakai avatar bulat di kartu profil dan kartu donor."""

    def test_inisial_mengambil_huruf_awal_dua_kata(self):
        self.assertEqual(ProfilDonor(nama_unit="Kantin Fasilkom").inisial, "KF")

    def test_inisial_satu_kata_memakai_dua_huruf_pertama(self):
        self.assertEqual(ProfilDonor(nama_unit="Katering").inisial, "KA")

    def test_inisial_nama_kosong_diberi_tanda_tanya(self):
        self.assertEqual(ProfilDonor(nama_unit="   ").inisial, "?")


class KomponenDesainModul1Test(TestCase):
    """Komponen desain Modul 1: chip berjumlah, pagination, kartu statistik."""

    def setUp(self):
        self.user = User.objects.create_user("donor_utama", password="rahasia-123")
        ProfilDonor.objects.create(
            user=self.user, nama_unit="Kantin Fasilkom",
            jenis=JenisDonor.KANTIN, kontak="kantin@x", deskripsi="Kantin fasilkom.",
        )
        for nomor in range(11):
            akun = User.objects.create_user(f"panitia{nomor}", password="rahasia-123")
            ProfilDonor.objects.create(
                user=akun, nama_unit=f"Panitia Acara {nomor:02d}",
                jenis=JenisDonor.PANITIA, kontak="panitia@x",
            )

    def test_chip_jenis_menyertakan_jumlah_donor(self):
        response = self.client.get(reverse("profil:daftar_donor"))
        chips = {chip["nilai"]: chip["jumlah"] for chip in response.context["chips_jenis"]}
        self.assertEqual(chips[""], 12)
        self.assertEqual(chips[JenisDonor.KANTIN], 1)
        self.assertEqual(chips[JenisDonor.PANITIA], 11)

    def test_pagination_membagi_daftar_sembilan_per_halaman(self):
        halaman_satu = self.client.get(reverse("profil:daftar_donor"))
        self.assertEqual(len(halaman_satu.context["halaman"].object_list), 9)
        self.assertEqual(halaman_satu.context["halaman"].paginator.num_pages, 2)
        halaman_dua = self.client.get(reverse("profil:daftar_donor"), {"page": 2})
        self.assertEqual(len(halaman_dua.context["halaman"].object_list), 3)

    def test_pagination_ikut_terkirim_di_panel_htmx(self):
        response = self.client.get(reverse("profil:daftar_donor"), HTTP_HX_REQUEST="true")
        self.assertContains(response, "mbg-pagination")

    def test_kartu_donor_menampilkan_jumlah_donasi(self):
        response = self.client.get(reverse("profil:daftar_donor"))
        self.assertContains(response, "0 donasi tersedia")

    def test_profil_donor_menampilkan_kartu_statistik(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("profil:profil_saya"))
        self.assertContains(response, "donasi dibuat")
        self.assertContains(response, "porsi tersedia")
        self.assertContains(response, "Belum diverifikasi")


class KomponenDesainHalamanMasukTest(TestCase):
    """Halaman masuk dan daftar memakai komponen Figma (kartu, chip, tombol)."""

    def test_halaman_masuk_pakai_kartu_dan_tombol_desain(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "mbg-card")
        self.assertContains(response, "btn-mbg-carrot")

    def test_halaman_daftar_menandai_kartu_peran_terpilih(self):
        response = self.client.get(reverse("profil:daftar"))
        self.assertContains(response, "mbg-role--active")
        self.assertContains(response, "Data donor")

    def test_kartu_peran_terpilih_mengikuti_parameter_peran(self):
        response = self.client.get(reverse("profil:daftar"), {"peran": "penerima"})
        self.assertContains(response, "Data penerima")
