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
