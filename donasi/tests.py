from datetime import datetime, timedelta
from io import BytesIO, StringIO
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .forms import DonasiForm
from .models import Donasi
from .permissions import is_donor

from profil.models import JenisDonor, ProfilDonor


class DonasiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.owner = users.objects.create_user("donor", password="test-only-Password789")
        cls.other = users.objects.create_user("other", password="test-only-Password789")
        cls.recipient = users.objects.create_user("recipient", password="test-only-Password789")
        # Role donor datang dari modul Profil Pengguna (ProfilDonor), bukan grup Django.
        ProfilDonor.objects.create(user=cls.owner, nama_unit="Donor Uji",
                                   jenis=JenisDonor.PANITIA, kontak="donor@test")
        ProfilDonor.objects.create(user=cls.other, nama_unit="Donor Lain",
                                   jenis=JenisDonor.KANTIN, kontak="other@test")

    def setUp(self):
        self.temp_media = TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.media_override.enable()
        self.addCleanup(self.temp_media.cleanup)
        self.addCleanup(self.media_override.disable)
        self.start = timezone.now().replace(second=0, microsecond=0) + timedelta(hours=1)
        self.item = self.make_item()

    def make_item(self, **changes):
        values = dict(donor=self.owner, nama="Nasi ayam", jumlah_porsi=20,
                      lokasi="Fasilkom UI", waktu_tersedia=self.start,
                      waktu_akhir_pengambilan=self.start + timedelta(hours=3))
        values.update(changes)
        return Donasi.objects.create(**values)

    def payload(self, **changes):
        tz = ZoneInfo("Asia/Jakarta")
        values = dict(nama="Roti seminar", jumlah_porsi=12, lokasi="Balairung",
                      waktu_tersedia=timezone.localtime(self.start, tz).strftime("%Y-%m-%dT%H:%M"),
                      waktu_akhir_pengambilan=timezone.localtime(self.start + timedelta(hours=2), tz).strftime("%Y-%m-%dT%H:%M"),
                      catatan="Bawa wadah sendiri.")
        values.update(changes)
        return values

    def photo(self, fmt="PNG"):
        image = BytesIO()
        Image.new("RGB", (20, 20), "green").save(image, format=fmt)
        return SimpleUploadedFile(f"foto.{fmt.lower()}", image.getvalue(), content_type=f"image/{fmt.lower()}")

    def test_public_pages_and_authenticated_donor_information(self):
        for url in [reverse("donasi:daftar"), self.item.get_absolute_url(), reverse("donasi:login")]:
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertNotContains(self.client.get(self.item.get_absolute_url()), "Edit donasi")
        response = self.client.get(self.item.get_absolute_url(), HTTP_ACCEPT="application/json")
        self.assertNotIn("donor", response.json())
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.item.get_absolute_url()), "Edit donasi")
        self.assertEqual(self.client.get(self.item.get_absolute_url(), HTTP_ACCEPT="application/json").json()["donor"]["id"], self.owner.pk)

    def test_create_edit_delete_via_ajax_assigns_authenticated_owner(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("donasi:buat"), self.payload(donor=self.other.pk), HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 201)
        item = Donasi.objects.get(nama="Roti seminar")
        self.assertEqual(item.donor, self.owner)
        self.assertEqual(item.waktu_tersedia, self.start)
        response = self.client.post(reverse("donasi:edit", args=[item.pk]), self.payload(nama="Roti baru"), HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.nama, "Roti baru")
        self.assertEqual(self.client.get(reverse("donasi:hapus", args=[item.pk])).status_code, 200)
        self.assertTrue(Donasi.objects.filter(pk=item.pk).exists())
        self.assertEqual(self.client.post(reverse("donasi:hapus", args=[item.pk]), HTTP_ACCEPT="application/json").status_code, 200)
        self.assertFalse(Donasi.objects.filter(pk=item.pk).exists())

    def test_normal_form_fallback_and_validation_errors(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("donasi:buat")).status_code, 200)
        self.assertEqual(self.client.get(reverse("donasi:edit", args=[self.item.pk])).status_code, 200)
        response = self.client.post(reverse("donasi:buat"), self.payload())
        self.assertEqual(response.status_code, 302)
        response = self.client.post(reverse("donasi:buat"), self.payload(jumlah_porsi=-1))
        self.assertEqual(response.status_code, 400)
        response = self.client.post(reverse("donasi:buat"), {})
        self.assertEqual(response.status_code, 400)
        self.assertIn("nama", response.context["form"].errors)
        response = self.client.post(reverse("donasi:hapus", args=[self.item.pk]))
        self.assertRedirects(response, reverse("donasi:daftar"))

    def test_authentication_roles_and_ownership(self):
        for name, args in [("buat", []), ("edit", [self.item.pk]), ("hapus", [self.item.pk])]:
            self.assertEqual(self.client.get(reverse(f"donasi:{name}", args=args)).status_code, 302)
        self.client.force_login(self.recipient)
        self.assertEqual(self.client.get(reverse("donasi:buat")).status_code, 403)
        self.assertEqual(self.client.post(reverse("donasi:buat"), self.payload(), HTTP_ACCEPT="application/json").status_code, 403)
        self.client.force_login(self.other)
        for name in ["edit", "hapus"]:
            self.assertEqual(self.client.get(reverse(f"donasi:{name}", args=[self.item.pk])).status_code, 404)
            self.assertEqual(self.client.post(reverse(f"donasi:{name}", args=[self.item.pk]), self.payload()).status_code, 404)
        self.item.refresh_from_db()
        self.assertEqual(self.item.nama, "Nasi ayam")
        self.owner.is_active = False
        self.assertFalse(is_donor(self.owner))

    def test_csrf_required_for_mutations_and_logout(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        for name, args in [("buat", []), ("edit", [self.item.pk]), ("hapus", [self.item.pk])]:
            self.assertEqual(client.post(reverse(f"donasi:{name}", args=args), self.payload()).status_code, 403)
        self.assertEqual(client.get(reverse("donasi:logout")).status_code, 405)

    def test_portion_status_time_and_database_validation(self):
        self.client.force_login(self.owner)
        for changes, field in [({"jumlah_porsi": -1}, "jumlah_porsi"),
                               ({"jumlah_porsi": 0}, "jumlah_porsi"),
                               ({"waktu_akhir_pengambilan": self.payload()["waktu_tersedia"]}, "waktu_akhir_pengambilan"),
                               ({"waktu_akhir_pengambilan": "2020-01-01T12:00"}, "waktu_akhir_pengambilan"),
                               ({"nama": "a" * 141}, "nama")]:
            response = self.client.post(reverse("donasi:buat"), self.payload(**changes), HTTP_ACCEPT="application/json")
            self.assertEqual(response.status_code, 400)
            self.assertIn(field, response.json()["errors"])
        self.item.waktu_akhir_pengambilan = self.item.waktu_tersedia
        with self.assertRaises(ValidationError):
            self.item.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_item(jumlah_porsi=-1)
        self.assertEqual(str(self.item), "Nasi ayam")

    def test_search_location_status_and_private_mine_filters(self):
        self.make_item(donor=self.other, nama="Roti", lokasi="Balairung", jumlah_porsi=0)
        self.make_item(nama="Sudah kedaluwarsa", waktu_tersedia=self.start - timedelta(days=2), waktu_akhir_pengambilan=self.start - timedelta(days=1))
        endpoint = reverse("donasi:api_list")
        self.assertEqual(self.client.get(endpoint).json()["count"], 2)
        for params in [{"q": "nasi"}, {"lokasi": "Balairung"}, {"status": "habis"}]:
            self.assertEqual(self.client.get(endpoint, params).json()["count"], 1)
        self.assertEqual(self.client.get(endpoint, {"mine": "1"}).status_code, 401)
        self.assertEqual(self.client.get(reverse("donasi:daftar"), {"mine": "1"}).status_code, 302)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(endpoint, {"mine": "1"}).json()["count"], 2)
        response = self.client.get(reverse("donasi:daftar"), {"q": "unknown"}, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Belum ada donasi", response.json()["html"])
        self.assertEqual(response.json()["count"], 0)

    def test_time_filters_overlap_periods_in_wib(self):
        fixed_now = datetime(2026, 10, 23, 2, tzinfo=ZoneInfo("UTC"))
        Donasi.objects.all().delete()
        self.make_item(waktu_tersedia=datetime(2026, 10, 22, 23, tzinfo=ZoneInfo("Asia/Jakarta")), waktu_akhir_pengambilan=datetime(2026, 10, 23, 19, tzinfo=ZoneInfo("Asia/Jakarta")))
        self.make_item(nama="Besok", waktu_tersedia=datetime(2026, 10, 24, 9, tzinfo=ZoneInfo("Asia/Jakarta")), waktu_akhir_pengambilan=datetime(2026, 10, 24, 15, tzinfo=ZoneInfo("Asia/Jakarta")))
        with patch("donasi.views.timezone.now", return_value=fixed_now):
            for period, count in [("hari_ini", 1), ("besok", 1), ("pekan_ini", 2)]:
                response = self.client.get(reverse("donasi:api_list"), {"waktu": period})
                self.assertEqual(response.json()["count"], count)

    def test_pagination_and_filter_links(self):
        for index in range(7):
            self.make_item(nama=f"Nasi {index}")
        response = self.client.get(reverse("donasi:daftar"), {"q": "Nasi", "page": "2"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["page_obj"]), 2)
        self.assertContains(response, "q=Nasi")
        self.assertNotContains(response, 'href="??')
        self.assertEqual(self.client.get(reverse("donasi:api_list"), {"page": "invalid"}).json()["page"], 1)

    def test_upload_photo_serve_replace_clear_and_reject_invalid(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("donasi:edit", args=[self.item.pk]), self.payload(foto=self.photo()), HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        photo_url = reverse("donasi:foto", args=[self.item.pk])
        response = self.client.get(photo_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        response.close()
        self.assertContains(self.client.get(self.item.get_absolute_url()), photo_url)
        self.assertContains(self.client.get(reverse("donasi:edit", args=[self.item.pk])), "Lihat foto saat ini")
        response = self.client.post(reverse("donasi:edit", args=[self.item.pk]), self.payload(**{"foto-clear": "on"}), HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(photo_url).status_code, 404)
        oversized = self.photo()
        oversized = SimpleUploadedFile("large.png", oversized.read() + b"\0" * (5 * 1024 * 1024), content_type="image/png")
        for photo in [self.photo("GIF"), oversized, SimpleUploadedFile("bad.png", b"not an image", content_type="image/png")]:
            response = self.client.post(reverse("donasi:buat"), self.payload(foto=photo), HTTP_ACCEPT="application/json")
            self.assertEqual(response.status_code, 400)
            self.assertIn("foto", response.json()["errors"])
        self.item.refresh_from_db()
        self.item.foto.save("missing.png", self.photo(), save=True)
        self.item.foto.storage.delete(self.item.foto.name)
        self.assertEqual(self.client.get(photo_url).status_code, 404)

    def test_expired_status_and_edit_keeps_wib_values(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.item.get_absolute_url()), self.item.waktu_tersedia_wib.strftime("%H.%M"))
        self.assertContains(self.client.get(reverse("donasi:daftar")), self.item.waktu_akhir_pengambilan_wib.strftime("%H.%M"))
        self.assertEqual(self.client.get(reverse("donasi:edit", args=[self.item.pk])).context["form"]["waktu_tersedia"].value().hour, self.item.waktu_tersedia_wib.hour)
        self.item.waktu_tersedia = timezone.now().replace(second=0, microsecond=0) - timedelta(hours=3)
        self.item.waktu_akhir_pengambilan = self.item.waktu_tersedia + timedelta(hours=1, seconds=27)
        self.item.save()
        self.assertEqual(self.item.status_tampilan, "Pengambilan selesai")
        with timezone.override(ZoneInfo("Asia/Jakarta")):
            data = self.payload(jumlah_porsi=0,
                                waktu_tersedia=self.item.waktu_tersedia_wib.strftime("%Y-%m-%dT%H:%M"),
                                waktu_akhir_pengambilan=self.item.waktu_akhir_pengambilan_wib.strftime("%Y-%m-%dT%H:%M"))
            self.assertTrue(DonasiForm(data, instance=self.item).is_valid())

    def test_protected_relations_prevent_deletion(self):
        self.client.force_login(self.owner)
        with patch.object(Donasi, "delete", side_effect=ProtectedError("protected", [])):
            for accept in ["application/json", "text/html"]:
                self.assertEqual(self.client.post(reverse("donasi:hapus", args=[self.item.pk]), HTTP_ACCEPT=accept).status_code, 409)
        self.assertTrue(Donasi.objects.filter(pk=self.item.pk).exists())

    def test_login_safe_redirect_and_logout(self):
        response = self.client.post(reverse("donasi:login"), {"username": "donor", "password": "test-only-Password789", "next": "https://example.com"})
        self.assertRedirects(response, reverse("donasi:daftar"))
        self.assertRedirects(self.client.post(reverse("donasi:logout")), reverse("donasi:daftar"))

    def test_management_commands_are_explicit_and_idempotent(self):
        output = StringIO()
        call_command("grant_donor", "recipient", stdout=output)
        self.assertTrue(is_donor(self.recipient))
        for _ in range(2):
            call_command("seed_donasi", donor="donor", count=50, stdout=output)
        self.assertEqual(Donasi.objects.filter(nama__startswith="[Contoh").count(), 50)
        for item in Donasi.objects.filter(nama__startswith="[Contoh"):
            item.full_clean()
        for kwargs in [{"donor": "missing"}, {"donor": "donor", "count": 0}]:
            with self.assertRaises(CommandError):
                call_command("seed_donasi", stdout=output, **kwargs)
        with self.assertRaises(CommandError):
            call_command("grant_donor", "missing", stdout=output)

    def test_audit_invalid_fields_return_specific_errors_without_saving(self):
        self.client.force_login(self.owner)
        cases = [
            ({"nama": "   "}, "nama", "Nama makanan wajib diisi."),
            ({"lokasi": "\t "}, "lokasi", "Lokasi pengambilan wajib diisi."),
            ({"lokasi": "x" * 201}, "lokasi", "maksimal 200"),
            ({"catatan": "x" * 201}, "catatan", "maksimal 200"),
            ({"jumlah_porsi": "1.5"}, "jumlah_porsi", "angka bulat"),
            ({"jumlah_porsi": "NaN"}, "jumlah_porsi", "angka bulat"),
            ({"jumlah_porsi": 2_147_483_648}, "jumlah_porsi", "terlalu besar"),
            ({"jumlah_porsi": ""}, "jumlah_porsi", "wajib diisi"),
            ({"waktu_tersedia": "invalid"}, "waktu_tersedia", "tanggal dan jam"),
            ({"waktu_akhir_pengambilan": "invalid"}, "waktu_akhir_pengambilan", "tanggal dan jam"),
            ({"waktu_tersedia": ""}, "waktu_tersedia", "wajib diisi"),
            ({"waktu_akhir_pengambilan": ""}, "waktu_akhir_pengambilan", "wajib diisi"),
        ]
        initial_count = Donasi.objects.count()
        for changes, field, expected in cases:
            with self.subTest(changes=changes):
                response = self.client.post(reverse("donasi:buat"), self.payload(**changes), HTTP_ACCEPT="application/json")
                self.assertEqual(response.status_code, 400)
                self.assertIn(expected, " ".join(error["message"] for error in response.json()["errors"][field]))
        self.assertEqual(Donasi.objects.count(), initial_count)

    def test_audit_time_order_strictly_rejects_equal_and_reversed_times(self):
        self.client.force_login(self.owner)
        for end in [self.payload()["waktu_tersedia"], timezone.localtime(self.start - timedelta(minutes=1), ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%dT%H:%M")]:
            for url in [reverse("donasi:buat"), reverse("donasi:edit", args=[self.item.pk])]:
                response = self.client.post(url, self.payload(waktu_akhir_pengambilan=end), HTTP_ACCEPT="application/json")
                self.assertEqual(response.status_code, 400)
                self.assertIn("harus setelah waktu mulai", response.json()["errors"]["waktu_akhir_pengambilan"][0]["message"])
        self.item.refresh_from_db()
        self.assertEqual(self.item.nama, "Nasi ayam")
        self.assertEqual(self.item.waktu_tersedia, self.start)

    def test_audit_expiry_now_rejected_and_expired_edits_must_close(self):
        self.client.force_login(self.owner)
        fixed = self.start + timedelta(hours=2)
        with patch("donasi.forms.timezone.now", return_value=fixed):
            response = self.client.post(reverse("donasi:buat"), self.payload(), HTTP_ACCEPT="application/json")
            self.assertEqual(response.status_code, 400)
            self.assertIn("masa depan", response.json()["errors"]["waktu_akhir_pengambilan"][0]["message"])
        self.item.waktu_tersedia = self.start - timedelta(days=2)
        self.item.waktu_akhir_pengambilan = self.start - timedelta(days=1)
        self.item.save()
        data = self.payload(waktu_tersedia=self.item.waktu_tersedia_wib.strftime("%Y-%m-%dT%H:%M"), waktu_akhir_pengambilan=self.item.waktu_akhir_pengambilan_wib.strftime("%Y-%m-%dT%H:%M"))
        self.assertFalse(DonasiForm(data, instance=self.item).is_valid())
        self.item.refresh_from_db()
        data.update(jumlah_porsi=0)
        self.assertTrue(DonasiForm(data, instance=self.item).is_valid())

    def test_audit_wib_parsing_independent_of_project_timezone(self):
        with timezone.override(ZoneInfo("UTC")):
            form = DonasiForm(self.payload())
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["waktu_tersedia"], self.start)
            self.assertEqual(form.cleaned_data["waktu_akhir_pengambilan"], self.start + timedelta(hours=2))

    def test_audit_max_portions_and_text_normalization(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("donasi:buat"), self.payload(jumlah_porsi=2_147_483_647, nama="  Nasi kotak  ", lokasi="  Lobi UI  "), HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 201)
        item = Donasi.objects.get(nama="Nasi kotak")
        self.assertEqual(item.lokasi, "Lobi UI")
        self.item.nama = "   "
        with self.assertRaises(ValidationError):
            self.item.full_clean()

    def test_audit_json_session_and_revoked_role_errors(self):
        for name, args in [("buat", []), ("edit", [self.item.pk]), ("hapus", [self.item.pk])]:
            response = self.client.post(reverse(f"donasi:{name}", args=args), self.payload(), HTTP_ACCEPT="application/json")
            self.assertEqual(response.status_code, 401)
            self.assertIn("login_url", response.json())
        self.client.force_login(self.owner)
        self.owner.profil_donor.delete()
        response = self.client.post(reverse("donasi:edit", args=[self.item.pk]), self.payload(), HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 403)
        self.item.refresh_from_db()
        self.assertEqual(self.item.nama, "Nasi ayam")

    def test_audit_photo_clear_upload_conflict_and_decoded_extension(self):
        self.client.force_login(self.owner)
        photo = self.photo()
        photo.name = "renamed.jpg"  # Valid PNG bytes with a misleading extension.
        response = self.client.post(reverse("donasi:edit", args=[self.item.pk]), self.payload(foto=photo), HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertTrue(self.item.foto.name.endswith(".png"))
        response = self.client.post(reverse("donasi:edit", args=[self.item.pk]), self.payload(foto=self.photo(), **{"foto-clear": "on"}), HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Pilih salah satu", response.json()["errors"]["foto"][0]["message"])
        self.item.refresh_from_db()
        self.assertTrue(self.item.foto)

    def test_audit_midnight_filter_boundaries(self):
        Donasi.objects.all().delete()
        tz = ZoneInfo("Asia/Jakarta")
        now = datetime(2026, 10, 23, 12, tzinfo=tz)
        self.make_item(nama="Berakhir tengah malam", waktu_tersedia=now, waktu_akhir_pengambilan=datetime(2026, 10, 24, 0, tzinfo=tz))
        self.make_item(nama="Mulai tengah malam", waktu_tersedia=datetime(2026, 10, 24, 0, tzinfo=tz), waktu_akhir_pengambilan=datetime(2026, 10, 24, 4, tzinfo=tz))
        with patch("donasi.views.timezone.now", return_value=now):
            today = self.client.get(reverse("donasi:api_list"), {"waktu": "hari_ini"}).json()["results"]
            tomorrow = self.client.get(reverse("donasi:api_list"), {"waktu": "besok"}).json()["results"]
        self.assertEqual([item["nama"] for item in today], ["Berakhir tengah malam"])
        self.assertEqual([item["nama"] for item in tomorrow], ["Mulai tengah malam"])

    def test_audit_errors_and_user_content_are_escaped_in_html(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("donasi:buat"), self.payload(nama="<script>alert(1)</script>", jumlah_porsi=-1))
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'id="donation-initial-errors"', status_code=400)
        self.assertNotContains(response, "<script>alert(1)</script>", status_code=400)
        self.assertContains(response, "&lt;script&gt;", status_code=400)
        self.assertContains(response, 'id="donation-toast-area"', status_code=400)

    def test_audit_success_message_survives_ajax_redirect(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("donasi:buat"), self.payload(), HTTP_ACCEPT="application/json")
        page = self.client.get(response.json()["url"])
        self.assertContains(page, "Donasi berhasil disimpan.")
        self.assertContains(page, "data-donation-notice")

    def test_audit_model_invalid_types_produce_validation_errors(self):
        self.item.jumlah_porsi = "bukan angka"
        self.item.waktu_tersedia = "bukan tanggal"
        with self.assertRaises(ValidationError) as raised:
            self.item.full_clean()
        self.assertIn("jumlah_porsi", raised.exception.message_dict)
        self.assertIn("waktu_tersedia", raised.exception.message_dict)

    def test_audit_admin_uses_same_validation_and_wib_fields(self):
        admin = get_user_model().objects.create_superuser("audit-admin", password="test-only-Password789")
        self.client.force_login(admin)
        url = reverse("admin:donasi_donasi_change", args=[self.item.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context["adminform"].form, DonasiForm)
        data = self.payload(donor=self.owner.pk, _save="Simpan")
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.waktu_tersedia, self.start)
        response = self.client.post(url, self.payload(donor=self.owner.pk, jumlah_porsi="1.5", _save="Simpan"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("jumlah_porsi", response.context["adminform"].form.errors)

    def test_stock_only_form_and_automatic_availability(self):
        self.client.force_login(self.owner)
        page = self.client.get(reverse("donasi:buat"))
        self.assertContains(page, "Akhir pengambilan")
        self.assertContains(page, "Jumlah stok (porsi)")
        self.assertNotContains(page, 'name="status"')
        self.assertNotContains(page, "Kedaluwarsa")
        self.assertNotIn("status", DonasiForm().fields)
        # An old or tampered status input cannot override the current stock.
        response = self.client.post(reverse("donasi:buat"), self.payload(jumlah_porsi=6, status="habis"), HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 201)
        item = Donasi.objects.get(nama="Roti seminar")
        self.assertEqual(item.status, "tersedia")
        response = self.client.post(reverse("donasi:edit", args=[item.pk]), self.payload(jumlah_porsi=0), HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.status, "habis")
        data = self.client.get(item.get_absolute_url(), HTTP_ACCEPT="application/json").json()
        self.assertIn("waktu_akhir_pengambilan", data)
        self.assertNotIn("waktu_kedaluwarsa", data)
        self.assertEqual(data["status_tampilan"], "Habis")
        # Bulk stock updates (e.g. future claims) cannot leave a stored status stale.
        Donasi.objects.filter(pk=item.pk).update(jumlah_porsi=3)
        item.refresh_from_db()
        self.assertEqual(item.status, "tersedia")

    def test_new_donation_requires_stock_and_finished_pickup_is_not_available(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("donasi:buat"), self.payload(jumlah_porsi=0), HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("minimal 1", response.json()["errors"]["jumlah_porsi"][0]["message"])
        self.item.waktu_tersedia = self.start - timedelta(days=2)
        self.item.waktu_akhir_pengambilan = self.start - timedelta(days=1)
        self.item.save()
        self.assertEqual(self.item.status_tampilan, "Pengambilan selesai")
        response = self.client.get(reverse("donasi:api_list"), {"mine": "1", "status": "tersedia"})
        self.assertEqual(response.json()["count"], 0)

    def test_navigation_labels_follow_role_and_unresolved_claims_are_disabled(self):
        for user, expected, excluded in [
            (self.owner, ["Klaim masuk", "Donasi saya"], ["Cari makanan", "Klaim saya"]),
            (self.recipient, ["Cari makanan", "Klaim saya"], ["Klaim masuk", "Donasi saya"]),
        ]:
            self.client.force_login(user)
            for url in [reverse("donasi:daftar"), reverse("donasi:login"), self.item.get_absolute_url()]:
                html = self.client.get(url).content.decode().split("</nav>", 1)[0]
                for text in expected:
                    self.assertIn(text, html)
                for text in excluded:
                    self.assertNotIn(text, html)
                self.assertIn('aria-disabled="true"', html)
                self.assertNotIn('href="#"', html)
                self.assertLess(html.index(expected[0]), html.index(expected[1]))
        from .navigation import claims_url
        with patch.dict("donasi.navigation.CLAIMS_VIEW_NAMES", {"donor": "profil:home", "penerima": "donasi:daftar"}):
            self.assertEqual(claims_url(donor=True), reverse("profil:home"))
            self.assertEqual(claims_url(donor=False), reverse("donasi:daftar"))
            self.client.force_login(self.owner)
            html = self.client.get(reverse("donasi:daftar")).content.decode().split("</nav>", 1)[0]
            self.assertNotIn('aria-disabled="true"', html)
        with patch.dict("donasi.navigation.CLAIMS_VIEW_NAMES", {"donor": "nonexistent_for_test"}):
            self.assertIsNone(claims_url(donor=True))

    def test_cards_always_offer_details_and_only_owner_gets_edit_icon(self):
        self.client.force_login(self.owner)
        self.make_item(donor=self.other, nama="Donasi donor lain")
        response = self.client.get(reverse("donasi:daftar"), HTTP_ACCEPT="application/json")
        html = response.json()["html"]
        self.assertEqual(html.count('class="btn btn-mbg-green donation-detail-link"'), 2)
        self.assertIn(f'aria-label="Lihat detail {self.item.nama}"', html)
        self.assertIn(f'aria-label="Edit donasi {self.item.nama}"', html)
        self.assertIn('title="Edit donasi"', html)
        self.assertNotIn('aria-label="Edit donasi Donasi donor lain"', html)
        self.assertEqual(html.count('class="btn btn-mbg-sunshine donation-edit-link"'), 1)
        self.client.force_login(self.recipient)
        html = self.client.get(reverse("donasi:daftar"), HTTP_ACCEPT="application/json").json()["html"]
        self.assertEqual(html.count('class="btn btn-mbg-green donation-detail-link"'), 2)
        self.assertNotIn('class="btn btn-mbg-sunshine donation-edit-link"', html)
