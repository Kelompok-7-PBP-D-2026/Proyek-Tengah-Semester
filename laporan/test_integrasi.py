import csv
from datetime import date, datetime, timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from klaim.models import Claim, ClaimStatus
from profil.models import ProfilDonor

from .exports import buat_csv, buat_pdf
from .klaim_adapter import REPORT_TIME_ZONE, agregasi
from .models import Laporan
from .services import hitung_laporan


@override_settings(
    ROOT_URLCONF="pts_project.urls", LAPORAN_AGGREGATOR="laporan.klaim_adapter.agregasi"
)
class IntegrasiLaporanTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user(username="admin-report", is_staff=True)
        cls.donor = User.objects.create_user(username="donor-a")
        cls.donor_b = User.objects.create_user(username="donor-b")
        cls.recipient = User.objects.create_user(username="recipient-a")
        cls.recipient_b = User.objects.create_user(username="recipient-b")
        cls.profile = ProfilDonor.objects.create(
            user=cls.donor,
            nama_unit="Kantin A",
            jenis="kantin",
            kontak="kantin@example.test",
        )
        cls.start = date(2026, 10, 1)
        cls.end = date(2026, 10, 31)
        cls.picked_up = datetime(2026, 10, 15, 12, tzinfo=REPORT_TIME_ZONE)
        cls.report = Laporan.objects.create(
            judul="Laporan Oktober",
            periode_mulai=cls.start,
            periode_selesai=cls.end,
            dibuat_oleh=cls.staff,
        )

    def setUp(self):
        self.client.force_login(self.staff)

    def claim(self, **overrides):
        return Claim.objects.create(
            **{
                "recipient": self.recipient,
                "donor": self.donor,
                "donation_id": 1,
                "food_name": "Nasi",
                "donor_name": "Nama saat klaim",
                "pickup_location": "Kampus",
                "pickup_deadline": self.picked_up + timedelta(hours=1),
                "pickup_time": self.picked_up,
                "expires_at": self.picked_up + timedelta(hours=1),
                "portions": 2,
                "status": ClaimStatus.PICKED_UP,
                "picked_up_at": self.picked_up,
                **overrides,
            }
        )

    def form_data(self, **overrides):
        return {
            "judul": "Laporan Oktober",
            "periode_mulai": "2026-10-01",
            "periode_selesai": "2026-10-31",
            "catatan": "",
            **overrides,
        }

    def test_unique_people_across_claims_and_donors(self):
        self.claim()
        self.claim()
        self.claim(donor=self.donor_b, portions=3)
        self.claim(recipient=self.recipient_b, portions=1)
        with self.assertNumQueries(1):
            result = agregasi(self.start, self.end)
        result.validate()
        self.assertEqual(
            (
                result.total_porsi,
                result.jumlah_donor,
                result.jumlah_penerima,
                result.jumlah_klaim,
            ),
            (8, 2, 2, 4),
        )
        self.assertEqual(
            result.rincian_donor[0],
            {
                "donor_id": self.donor.pk,
                "nama": "Kantin A",
                "jenis": "Kantin Kampus",
                "total_porsi": 5,
                "jumlah_penerima": 2,
            },
        )
        self.assertEqual(result.rincian_donor[1]["jenis"], "Belum diklasifikasikan")

    def test_uses_actual_pickup_time_and_inclusive_wib_boundaries(self):
        start = datetime(2026, 10, 1, tzinfo=REPORT_TIME_ZONE)
        end = datetime(2026, 10, 31, 23, 59, 59, 999999, tzinfo=REPORT_TIME_ZONE)
        for moment in (
            start,
            end,
            start - timedelta(microseconds=1),
            end + timedelta(microseconds=1),
        ):
            self.claim(picked_up_at=moment, pickup_time=moment - timedelta(days=40))
        with timezone.override("America/New_York"):
            result = agregasi(self.start, self.end)
        self.assertEqual((result.total_porsi, result.jumlah_klaim), (4, 2))

    def test_only_picked_up_with_actual_timestamp_counts(self):
        self.claim()
        for status in (ClaimStatus.PENDING, ClaimStatus.CANCELLED, ClaimStatus.EXPIRED):
            self.claim(status=status)
        self.claim(picked_up_at=None)
        result = agregasi(self.start, self.end)
        self.assertEqual((result.total_porsi, result.jumlah_klaim), (2, 1))

    def test_empty_period_is_ready_zero_snapshot(self):
        hitung_laporan(self.report)
        self.assertEqual(self.report.status, "siap")
        self.assertEqual(self.report.rincian_donor, [])
        self.assertEqual(self.report.jumlah_klaim, 0)
        response = self.client.get(self.report.get_absolute_url())
        self.assertContains(response, "Belum ada klaim yang sudah diambil")
        self.assertNotContains(response, "Rincian per donor belum tersedia")

    def test_deleted_donors_keep_portions_without_inventing_identity(self):
        self.claim()
        self.claim(
            donor=self.donor_b, donor_name="Kantin B", recipient=self.recipient_b
        )
        self.donor.delete()
        self.donor_b.delete()
        hitung_laporan(self.report)
        self.assertEqual(
            (
                self.report.total_porsi,
                self.report.jumlah_donor,
                self.report.jumlah_penerima,
            ),
            (4, 0, 2),
        )
        self.assertEqual(len(self.report.rincian_donor), 1)
        self.assertTrue(self.report.memiliki_donor_dihapus)
        self.assertContains(
            self.client.get(self.report.get_absolute_url()),
            "tidak dihitung sebagai donor unik",
        )

    def test_distinct_donors_with_identical_names_remain_distinct(self):
        ProfilDonor.objects.create(
            user=self.donor_b,
            nama_unit="Kantin A",
            jenis="kantin",
            kontak="b@example.test",
        )
        self.claim()
        self.claim(donor=self.donor_b)
        self.assertEqual(agregasi(self.start, self.end).jumlah_donor, 2)

    def test_missing_profile_and_name_fall_back_to_username(self):
        self.claim(donor=self.donor_b, donor_name="")
        self.assertEqual(
            agregasi(self.start, self.end).rincian_donor[0]["nama"],
            self.donor_b.username,
        )

    def test_snapshot_survives_source_edits_until_explicit_recalculation(self):
        claim = self.claim()
        hitung_laporan(self.report)
        self.profile.nama_unit = "Nama baru"
        self.profile.save()
        claim.portions = 3
        claim.save()
        response = self.client.get(self.report.get_absolute_url())
        self.assertContains(response, "Kantin A")
        self.assertNotContains(response, "Nama baru")
        self.assertIn("Kantin A", buat_csv(self.report))
        self.client.post(reverse("laporan:generate", args=[self.report.pk]))
        self.report.refresh_from_db()
        self.assertEqual(self.report.total_porsi, 3)
        self.assertEqual(self.report.rincian_donor[0]["nama"], "Nama baru")

    def test_create_calculates_server_values_and_ignores_forged_fields(self):
        self.claim()
        response = self.client.post(
            reverse("laporan:buat"),
            self.form_data(
                total_porsi=999,
                jumlah_donor=888,
                rincian_donor="[]",
                dibuat_oleh=self.donor.pk,
                status="draf",
            ),
        )
        report = Laporan.objects.latest("pk")
        self.assertRedirects(response, report.get_absolute_url())
        self.assertEqual(
            (report.status, report.total_porsi, report.jumlah_donor), ("siap", 2, 1)
        )
        self.assertEqual(report.dibuat_oleh, self.staff)
        self.assertEqual(report.rincian_donor[0]["nama"], "Kantin A")

    def test_preview_is_get_only_uncached_and_does_not_save(self):
        self.claim()
        response = self.client.get(reverse("laporan:pratinjau"), self.form_data())
        self.assertEqual(
            response.json(),
            {
                "total_porsi": 2,
                "jumlah_donor": 1,
                "jumlah_penerima": 1,
                "jumlah_klaim": 1,
            },
        )
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(Laporan.objects.count(), 1)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "draf")
        self.assertEqual(
            self.client.post(reverse("laporan:pratinjau")).status_code, 405
        )

    def test_preview_rejects_bad_or_reversed_dates(self):
        for query in (
            {},
            self.form_data(periode_mulai="bad"),
            self.form_data(periode_selesai="2026-09-30"),
        ):
            with self.subTest(query=query):
                response = self.client.get(reverse("laporan:pratinjau"), query)
                self.assertEqual(response.status_code, 400)
                self.assertIn("errors", response.json())

    def test_preview_requires_admin(self):
        self.client.logout()
        self.assertEqual(
            self.client.get(reverse("laporan:pratinjau"), self.form_data()).status_code,
            302,
        )
        self.client.force_login(self.recipient)
        self.assertEqual(
            self.client.get(reverse("laporan:pratinjau"), self.form_data()).status_code,
            403,
        )

    def test_source_failure_returns_unavailable_instead_of_zero(self):
        with (
            patch("laporan.views.ringkasan_periode", side_effect=ValueError),
            self.assertLogs("laporan.views", level="WARNING"),
        ):
            response = self.client.get(reverse("laporan:pratinjau"), self.form_data())
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("total_porsi", response.json())

    def test_source_failure_does_not_create_report(self):
        with (
            patch("laporan.klaim_adapter.agregasi", side_effect=ValueError),
            self.assertLogs("laporan.views"),
        ):
            response = self.client.post(reverse("laporan:buat"), self.form_data())
        self.assertContains(response, "Laporan belum disimpan")
        self.assertEqual(Laporan.objects.count(), 1)

    def test_period_change_recalculates_without_extra_button(self):
        self.claim()
        hitung_laporan(self.report)
        response = self.client.post(
            reverse("laporan:edit", args=[self.report.pk]),
            self.form_data(periode_selesai="2026-10-10"),
        )
        self.assertRedirects(response, self.report.get_absolute_url())
        self.report.refresh_from_db()
        self.assertEqual(
            (self.report.status, self.report.total_porsi, self.report.rincian_donor),
            ("siap", 0, []),
        )

    def test_failed_period_edit_preserves_previous_period_and_snapshot(self):
        self.claim()
        hitung_laporan(self.report)
        with (
            patch("laporan.klaim_adapter.agregasi", side_effect=ValueError),
            self.assertLogs("laporan.views", level="ERROR"),
        ):
            response = self.client.post(
                reverse("laporan:edit", args=[self.report.pk]),
                self.form_data(periode_selesai="2026-10-10", judul="Judul baru"),
            )
        self.assertContains(response, "Perubahan belum disimpan")
        self.report.refresh_from_db()
        self.assertEqual(
            (self.report.periode_selesai, self.report.total_porsi, self.report.judul),
            (self.end, 2, "Laporan Oktober"),
        )
        self.assertEqual(self.report.rincian_donor[0]["nama"], "Kantin A")

    def test_note_edit_keeps_donor_snapshot_without_reading_claims(self):
        self.claim()
        hitung_laporan(self.report)
        with patch("laporan.klaim_adapter.agregasi") as provider:
            self.client.post(
                reverse("laporan:edit", args=[self.report.pk]),
                self.form_data(catatan="Catatan baru"),
            )
        provider.assert_not_called()
        self.report.refresh_from_db()
        self.assertEqual(self.report.total_porsi, 2)
        self.assertEqual(self.report.catatan, "Catatan baru")

    def test_donor_html_and_csv_escape_untrusted_names(self):
        self.profile.nama_unit = '<img src=x onerror="alert(1)">'
        self.profile.save()
        self.claim()
        hitung_laporan(self.report)
        response = self.client.get(self.report.get_absolute_url())
        self.assertNotContains(response, "<img src=x")
        self.assertContains(response, "&lt;img")
        self.report.rincian_donor[0]["nama"] = '=HYPERLINK("https://example.test")'
        rows = list(csv.reader(StringIO(buat_csv(self.report).lstrip("\ufeff"))))
        self.assertIn(["Donor", "Jenis donor", "Porsi", "Penerima unik"], rows)
        self.assertTrue(any(row and row[0].startswith("'=") for row in rows))
        self.assertTrue(buat_pdf(self.report).startswith(b"%PDF-"))

    def test_pdf_supports_multiple_pages_of_donor_rows(self):
        self.report.rincian_donor = [
            {
                "donor_id": index,
                "nama": "Nama donor panjang & <teks> " * 4,
                "jenis": "Panitia Acara",
                "total_porsi": 3,
                "jumlah_penerima": 1,
            }
            for index in range(1, 80)
        ]
        self.assertTrue(buat_pdf(self.report).rstrip().endswith(b"%%EOF"))

    def test_legacy_report_renders_unavailable_detail_until_recalculated(self):
        self.assertContains(
            self.client.get(self.report.get_absolute_url()),
            "Rincian per donor belum tersedia",
        )
        hitung_laporan(self.report)
        self.assertNotContains(
            self.client.get(self.report.get_absolute_url()),
            "Rincian per donor belum tersedia",
        )

    def test_main_navigation_links_to_reports_and_back(self):
        self.assertEqual(reverse("laporan:dashboard"), "/laporan/")
        self.assertContains(self.client.get(reverse("profil:home")), 'href="/laporan/"')
        response = self.client.get(reverse("laporan:dashboard"))
        self.assertContains(response, f'href="{reverse("venue:daftar")}"')
        self.assertContains(response, f'href="{reverse("profil:daftar")}"')

    def test_initial_create_preview_is_available_without_javascript(self):
        with patch("laporan.views.timezone.localdate", return_value=date(2026, 10, 31)):
            self.claim()
            response = self.client.get(reverse("laporan:buat"))
        self.assertEqual(response.context["preview_impact"].total_porsi, 2)
        self.assertContains(response, "1 klaim berstatus sudah diambil")
