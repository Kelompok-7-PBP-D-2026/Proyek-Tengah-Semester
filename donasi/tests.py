from datetime import timedelta
from io import BytesIO
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from klaim.models import Claim, ClaimStatus
from profil.models import Fakultas, JenisDonor, ProfilDonor, ProfilPenerima
from venue.models import UnitVenue, Venue

from .forms import DonasiForm
from .models import Donasi


class DonasiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="donor",
            password="password123",
        )
        self.other_donor = User.objects.create_user(
            username="donor_lain",
            password="password123",
        )
        self.recipient = User.objects.create_user(
            username="penerima",
            password="password123",
        )
        ProfilDonor.objects.create(
            user=self.owner,
            nama_unit="Donor Uji",
            jenis=JenisDonor.PANITIA,
            kontak="donor@test.com",
        )
        ProfilDonor.objects.create(
            user=self.other_donor,
            nama_unit="Donor Lain",
            jenis=JenisDonor.KANTIN,
            kontak="lain@test.com",
        )
        ProfilPenerima.objects.create(
            user=self.recipient,
            nama_lengkap="Penerima Uji",
            nim="2600000001",
            fakultas=Fakultas.FASILKOM,
            kontak="penerima@test.com",
        )
        self.venue_fasilkom = Venue.objects.create(
            nama="Fasilkom UI",
            fakultas=UnitVenue.FASILKOM,
            latitude="-6.364100",
            longitude="106.827200",
        )
        self.venue_balairung = Venue.objects.create(
            nama="Balairung UI",
            fakultas=UnitVenue.KAMPUS,
            latitude="-6.368200",
            longitude="106.826600",
        )
        self.start = timezone.now().replace(second=0, microsecond=0) + timedelta(hours=1)
        self.item = self.create_donation()

    def create_donation(self, **changes):
        """Membuat Donasi uji dengan nilai default yang dapat dioverride."""
        data = {
            "donor": self.owner,
            "nama": "Nasi ayam",
            "jumlah_porsi": 20,
            "lokasi": "Fasilkom UI",
            "waktu_tersedia": self.start,
            "waktu_akhir_pengambilan": self.start + timedelta(hours=3),
        }
        data.update(changes)
        return Donasi.objects.create(**data)

    def form_data(self, **changes):
        """Membuat data POST valid untuk pengujian form Donasi."""
        wib = ZoneInfo("Asia/Jakarta")
        data = {
            "nama": "Roti seminar",
            "jumlah_porsi": 12,
            "lokasi": "Balairung UI",
            "waktu_tersedia": timezone.localtime(self.start, wib).strftime("%Y-%m-%dT%H:%M"),
            "waktu_akhir_pengambilan": timezone.localtime(
                self.start + timedelta(hours=2), wib
            ).strftime("%Y-%m-%dT%H:%M"),
            "catatan": "Bawa wadah sendiri.",
        }
        data.update(changes)
        return data

    def create_claim(self, status, portions):
        """Membuat Klaim uji yang terhubung ke Donasi utama."""
        return Claim.objects.create(
            recipient=self.recipient,
            donor=self.owner,
            donation_id=self.item.pk,
            food_name=self.item.nama,
            donor_name="Donor Uji",
            pickup_location=self.item.lokasi,
            pickup_deadline=self.item.waktu_akhir_pengambilan,
            portions=portions,
            pickup_time=self.start + timedelta(hours=1),
            expires_at=self.start + timedelta(hours=2),
            status=status,
        )

    def image_upload(self, image_format, filename="foto.png"):
        """Membuat file gambar kecil di memori tanpa menulis file uji ke media."""
        buffer = BytesIO()
        Image.new("RGB", (2, 2), "green").save(buffer, format=image_format)
        return SimpleUploadedFile(
            filename,
            buffer.getvalue(),
            content_type="image/png",
        )

    # ===== CRUD dan validasi form =====

    def test_list_and_detail_pages_can_be_opened(self):
        list_response = self.client.get(reverse("donasi:daftar"))
        detail_response = self.client.get(self.item.get_absolute_url())

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(list_response, self.item.nama)
        self.assertContains(detail_response, self.item.nama)

    def test_ajax_crud_uses_logged_in_donor(self):
        self.client.force_login(self.owner)

        create_response = self.client.post(
            reverse("donasi:buat"),
            self.form_data(),
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        donation = Donasi.objects.get(nama="Roti seminar")
        self.assertEqual(donation.donor, self.owner)

        edit_response = self.client.post(
            reverse("donasi:edit", args=[donation.pk]),
            self.form_data(nama="Roti sudah diedit"),
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(edit_response.status_code, 200)
        donation.refresh_from_db()
        self.assertEqual(donation.nama, "Roti sudah diedit")

        delete_response = self.client.post(
            reverse("donasi:hapus", args=[donation.pk]),
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(Donasi.objects.filter(pk=donation.pk).exists())

    def test_normal_form_submission_still_works_without_javascript(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("donasi:buat"), self.form_data())

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Donasi.objects.filter(nama="Roti seminar").exists())

    def test_only_donor_can_manage_donations(self):
        self.assertEqual(self.client.get(reverse("donasi:buat")).status_code, 302)

        self.client.force_login(self.recipient)
        self.assertEqual(self.client.get(reverse("donasi:buat")).status_code, 403)

        admin = get_user_model().objects.create_superuser(
            username="admin",
            password="password123",
        )
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("donasi:buat")).status_code, 403)

        self.client.force_login(self.other_donor)
        edit_url = reverse("donasi:edit", args=[self.item.pk])
        delete_url = reverse("donasi:hapus", args=[self.item.pk])
        self.assertEqual(self.client.get(edit_url).status_code, 404)
        self.assertEqual(self.client.post(delete_url).status_code, 404)

    def test_post_requests_need_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)

        response = client.post(reverse("donasi:buat"), self.form_data())
        self.assertEqual(response.status_code, 403)

    def test_form_rejects_invalid_stock_and_time(self):
        self.client.force_login(self.owner)
        create_url = reverse("donasi:buat")

        invalid_stock = self.client.post(
            create_url,
            self.form_data(jumlah_porsi=0),
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(invalid_stock.status_code, 400)
        self.assertIn("jumlah_porsi", invalid_stock.json()["errors"])

        same_time = self.form_data()
        same_time["waktu_akhir_pengambilan"] = same_time["waktu_tersedia"]
        invalid_time = self.client.post(
            create_url,
            same_time,
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(invalid_time.status_code, 400)
        self.assertIn("waktu_akhir_pengambilan", invalid_time.json()["errors"])

        past_time = self.form_data(
            waktu_tersedia="2020-01-01T10:00",
            waktu_akhir_pengambilan="2020-01-01T11:00",
        )
        invalid_past_time = self.client.post(
            create_url,
            past_time,
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(invalid_past_time.status_code, 400)
        self.assertIn(
            "waktu_akhir_pengambilan",
            invalid_past_time.json()["errors"],
        )

    def test_form_uses_registered_venue(self):
        self.client.force_login(self.owner)
        create_url = reverse("donasi:buat")

        response = self.client.get(create_url)
        self.assertContains(response, str(self.venue_fasilkom))
        self.assertContains(response, reverse("venue:daftar"))

        invalid_location = self.client.post(
            create_url,
            self.form_data(lokasi="Lokasi tidak terdaftar"),
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(invalid_location.status_code, 400)
        self.assertIn("lokasi", invalid_location.json()["errors"])

    def test_form_checks_the_real_image_format(self):
        """Foto PNG diterima, sedangkan isi GIF yang diberi nama PNG ditolak."""
        valid_form = DonasiForm(
            data=self.form_data(),
            files={"foto": self.image_upload("PNG")},
        )
        self.assertTrue(valid_form.is_valid())
        self.assertEqual(valid_form.cleaned_data["foto"].name, "foto.png")

        invalid_form = DonasiForm(
            data=self.form_data(),
            files={"foto": self.image_upload("GIF")},
        )
        self.assertFalse(invalid_form.is_valid())
        self.assertIn("Gunakan foto berformat JPG atau PNG.", invalid_form.errors["foto"])

    # ===== Daftar, filter, dan pagination =====

    def test_search_location_and_status_filters(self):
        self.create_donation(
            donor=self.other_donor,
            nama="Roti",
            jumlah_porsi=0,
            lokasi="Balairung UI",
        )
        api_url = reverse("donasi:api_list")

        self.assertEqual(self.client.get(api_url, {"q": "nasi"}).json()["count"], 1)
        self.assertEqual(
            self.client.get(api_url, {"lokasi": "Balairung UI"}).json()["count"],
            1,
        )
        self.assertEqual(
            self.client.get(api_url, {"status": "habis"}).json()["count"],
            1,
        )

    def test_donasi_saya_only_shows_the_logged_in_owner(self):
        self.create_donation(donor=self.other_donor, nama="Milik donor lain")
        self.client.force_login(self.owner)

        response = self.client.get(reverse("donasi:api_list"), {"mine": "1"})
        names = [item["nama"] for item in response.json()["results"]]

        self.assertIn(self.item.nama, names)
        self.assertNotIn("Milik donor lain", names)

    def test_list_uses_pagination(self):
        for number in range(7):
            self.create_donation(nama=f"Donasi {number}")

        response = self.client.get(reverse("donasi:daftar"), {"page": 2})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertEqual(len(response.context["page_obj"]), 2)

    # ===== Interaktivitas HTMX pada daftar Donasi =====

    def test_htmx_filter_returns_only_results_partial(self):
        """Request HTMX cukup menerima kartu hasil, bukan seluruh halaman daftar."""
        response = self.client.get(
            reverse("donasi:daftar"),
            {"q": "Nasi"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "donasi/partials/results.html")
        self.assertTemplateNotUsed(response, "donasi/daftar.html")
        self.assertContains(response, self.item.nama)

    def test_list_has_htmx_filter_and_pagination_controls(self):
        """Form filter dan link halaman harus memperbarui wadah hasil yang sama."""
        for number in range(7):
            self.create_donation(nama=f"Donasi HTMX {number}")

        response = self.client.get(reverse("donasi:daftar"))

        self.assertContains(response, 'hx-target="#donation-results"', count=4)
        self.assertContains(response, 'hx-push-url="true"', count=4)

    # ===== Hak akses dan keamanan respons =====

    def test_json_access_errors_have_clear_status_codes(self):
        """AJAX menerima 401 untuk anonim dan 403 untuk user yang bukan donor."""
        anonymous_response = self.client.get(
            reverse("donasi:buat"),
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(anonymous_response.status_code, 401)

        self.client.force_login(self.recipient)
        recipient_response = self.client.get(
            reverse("donasi:buat"),
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(recipient_response.status_code, 403)

    def test_private_list_requires_login_for_html_and_api(self):
        """Daftar milik sendiri tidak boleh dibaca oleh pengunjung anonim."""
        html_response = self.client.get(reverse("donasi:daftar"), {"mine": "1"})
        api_response = self.client.get(reverse("donasi:api_list"), {"mine": "1"})

        self.assertEqual(html_response.status_code, 302)
        self.assertTrue(html_response.url.startswith(f"{reverse('login')}?next="))
        self.assertEqual(api_response.status_code, 401)

    def test_manage_donation_uses_shared_login_page(self):
        """Pengunjung anonim diarahkan ke login bersama, bukan login khusus Donasi."""
        response = self.client.get(reverse("donasi:buat"))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('donasi:buat')}",
        )

    def test_delete_confirmation_and_missing_photo_are_handled(self):
        """GET hapus menampilkan konfirmasi dan foto yang tidak ada menghasilkan 404."""
        self.client.force_login(self.owner)
        delete_response = self.client.get(
            reverse("donasi:hapus", args=[self.item.pk])
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertContains(delete_response, "Hapus donasi ini?")

        photo_url = reverse("donasi:foto", args=[self.item.pk])
        self.assertEqual(self.client.get(photo_url).status_code, 404)

        self.item.foto.name = "donasi/foto-tidak-ada.png"
        self.item.save(update_fields=["foto"])
        self.assertEqual(self.client.get(photo_url).status_code, 404)

    def test_json_hides_donor_from_anonymous_users(self):
        response = self.client.get(
            self.item.get_absolute_url(),
            HTTP_ACCEPT="application/json",
        )
        self.assertNotIn("donor", response.json())

        self.client.force_login(self.owner)
        response = self.client.get(
            self.item.get_absolute_url(),
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.json()["donor"]["id"], self.owner.pk)

    def test_stock_and_end_time_determine_the_status(self):
        self.item.jumlah_porsi = 0
        self.item.save()
        self.assertEqual(self.item.status_tampilan, "Habis")

        self.item.waktu_tersedia = timezone.now() - timedelta(hours=2)
        self.item.waktu_akhir_pengambilan = timezone.now() - timedelta(hours=1)
        self.item.save()
        self.assertEqual(self.item.status_tampilan, "Pengambilan selesai")

    # ===== Integrasi role, Klaim, dan Venue =====

    def test_navigation_is_different_for_donor_and_recipient(self):
        guest_html = self.client.get(reverse("donasi:daftar")).content.decode()
        self.assertNotIn(">Dampak</a>", guest_html)

        self.client.force_login(self.owner)
        donor_response = self.client.get(reverse("donasi:daftar"))
        donor_html = donor_response.content.decode()
        self.assertTemplateUsed(donor_response, "header.html")
        self.assertTemplateUsed(donor_response, "footer.html")
        self.assertIn("Donasi saya", donor_html)
        self.assertIn("Klaim masuk", donor_html)
        self.assertIn(reverse("klaim:incoming_claim_list"), donor_html)
        self.assertNotIn(">Dampak</a>", donor_html)

        self.client.force_login(self.recipient)
        recipient_response = self.client.get(reverse("donasi:daftar"))
        recipient_html = recipient_response.content.decode()
        self.assertTemplateUsed(recipient_response, "header.html")
        self.assertIn("Cari makanan", recipient_html)
        self.assertIn("Klaim saya", recipient_html)
        self.assertIn(reverse("klaim:claim_list"), recipient_html)
        self.assertNotIn(">Dampak</a>", recipient_html)

    def test_claim_button_only_appears_for_available_recipient(self):
        claim_url = reverse("klaim:claim_create", args=[self.item.pk])

        self.client.force_login(self.recipient)
        response = self.client.get(reverse("donasi:daftar"))
        self.assertContains(response, claim_url)
        self.assertContains(response, "Klaim")
        self.assertEqual(self.client.get(claim_url).status_code, 200)

        self.item.jumlah_porsi = 0
        self.item.save()
        response = self.client.get(self.item.get_absolute_url())
        self.assertNotContains(response, "Klaim makanan")

        self.client.force_login(self.owner)
        response = self.client.get(reverse("donasi:daftar"))
        self.assertNotContains(response, claim_url)

    def test_only_owner_sees_the_edit_button(self):
        self.client.force_login(self.owner)
        self.create_donation(donor=self.other_donor, nama="Donasi donor lain")
        html = self.client.get(
            reverse("donasi:daftar"),
            HTTP_ACCEPT="application/json",
        ).json()["html"]

        self.assertIn(f"Edit donasi {self.item.nama}", html)
        self.assertNotIn("Edit donasi Donasi donor lain", html)
        self.assertEqual(html.count("donation-detail-link"), 2)

    def test_card_stock_badges_and_expired_status(self):
        self.client.force_login(self.owner)
        self.create_donation(nama="Stok habis", jumlah_porsi=0)
        self.create_donation(nama="Stok satu", jumlah_porsi=1)
        self.create_donation(nama="Stok lima", jumlah_porsi=5)
        self.create_donation(nama="Stok enam", jumlah_porsi=6)
        ended_at = timezone.now() - timedelta(hours=1)
        self.create_donation(
            nama="Donasi berakhir",
            jumlah_porsi=73,
            waktu_tersedia=ended_at - timedelta(hours=2),
            waktu_akhir_pengambilan=ended_at,
        )

        html = self.client.get(
            reverse("donasi:daftar"),
            {"mine": "1"},
            HTTP_ACCEPT="application/json",
        ).json()["html"]

        self.assertEqual(html.count("stock-empty"), 1)
        self.assertEqual(html.count("stock-low"), 2)
        self.assertEqual(html.count("stock-ended"), 1)
        self.assertIn("Habis", html)
        self.assertIn("Telah berakhir", html)
        self.assertNotIn(">73 porsi</span>", html)

    def test_detail_shows_portion_information(self):
        response = self.client.get(self.item.get_absolute_url())
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("Informasi porsi", html)
        self.assertIn("porsi diklaim", html)
        self.assertIn("porsi diambil", html)
        self.assertIn("porsi tersisa", html)
        self.assertIn(f"<strong>{self.item.jumlah_porsi}</strong>", html)
        self.assertContains(response, self.venue_fasilkom.get_absolute_url())

    def test_detail_uses_claim_data_for_portion_information(self):
        self.create_claim(ClaimStatus.PENDING, 2)
        self.create_claim(ClaimStatus.PICKED_UP, 3)
        self.create_claim(ClaimStatus.CANCELLED, 1)
        self.create_claim(ClaimStatus.EXPIRED, 1)

        response = self.client.get(self.item.get_absolute_url())

        self.assertEqual(response.context["jumlah_diklaim"], 5)
        self.assertEqual(response.context["jumlah_diambil"], 3)

    def test_expired_claim_returns_stock_when_donations_are_opened(self):
        self.item.jumlah_porsi = 18
        self.item.save()
        claim = self.create_claim(ClaimStatus.PENDING, 2)
        claim.expires_at = timezone.now() - timedelta(minutes=1)
        claim.save()

        self.client.get(reverse("donasi:daftar"))
        claim.refresh_from_db()
        self.item.refresh_from_db()

        self.assertEqual(claim.status, ClaimStatus.EXPIRED)
        self.assertEqual(self.item.jumlah_porsi, 20)
