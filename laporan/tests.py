import csv
from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .exports import PDFDependencyMissing, buat_csv, buat_pdf
from .forms import LaporanForm
from .models import Laporan
from .services import (
    HasilAgregasiTidakValid,
    RingkasanDampak,
    SumberDataBelumTersedia,
    hitung_laporan,
)


def successful_provider(start, end):
    return RingkasanDampak(total_porsi=25, jumlah_donor=2, jumlah_penerima=7)


def zero_provider(start, end):
    return RingkasanDampak(total_porsi=0, jumlah_donor=0, jumlah_penerima=0)


def invalid_provider(start, end):
    return RingkasanDampak(total_porsi=-1, jumlah_donor=2, jumlah_penerima=7)


@override_settings(ROOT_URLCONF="pts_project.urls", LAPORAN_AGGREGATOR="")
class LaporanTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user(
            username="pengelola", password="test-pass-785", is_staff=True
        )
        cls.other_staff = User.objects.create_user(
            username="pengelola2", password="test-pass-785", is_staff=True
        )
        cls.regular = User.objects.create_user(
            username="donor", password="test-pass-785"
        )
        cls.laporan = Laporan.objects.create(
            judul="Laporan Oktober",
            periode_mulai=date(2026, 10, 1),
            periode_selesai=date(2026, 10, 31),
            dibuat_oleh=cls.staff,
        )

    def setUp(self):
        self.client.force_login(self.staff)

    def url(self, name, pk=None):
        return reverse("laporan:" + name, args=[pk or self.laporan.pk])

    def form_data(self, **overrides):
        return {
            "judul": "Laporan Oktober",
            "periode_mulai": "2026-10-01",
            "periode_selesai": "2026-10-31",
            "catatan": "Catatan kegiatan",
            **overrides,
        }

    def ready(self):
        with override_settings(LAPORAN_AGGREGATOR="laporan.tests.successful_provider"):
            hitung_laporan(self.laporan)

    def test_draft_has_unknown_metrics_not_zero(self):
        self.assertEqual(self.laporan.status, Laporan.Status.DRAF)
        self.assertIsNone(self.laporan.total_porsi)
        self.assertIsNone(self.laporan.jumlah_donor)
        self.assertIsNone(self.laporan.jumlah_penerima)
        self.assertIsNone(self.laporan.dihitung_pada)

    def test_invalid_period_form_and_model_rejected(self):
        form = LaporanForm(self.form_data(periode_selesai="2026-09-30"))
        self.assertFalse(form.is_valid())
        self.assertIn("periode_selesai", form.errors)
        self.laporan.periode_selesai = date(2026, 9, 30)
        with self.assertRaises(ValidationError):
            self.laporan.full_clean()

    def test_same_day_period_is_valid(self):
        self.assertTrue(
            LaporanForm(self.form_data(periode_selesai="2026-10-01")).is_valid()
        )

    def test_database_rejects_invalid_period(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Laporan.objects.filter(pk=self.laporan.pk).update(
                periode_selesai=date(2026, 9, 30)
            )

    def test_database_rejects_fake_ready_or_draft_metrics(self):
        for update in ({"status": "siap"}, {"total_porsi": 0}, {"status": "unknown"}):
            with (
                self.subTest(update=update),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
            ):
                Laporan.objects.filter(pk=self.laporan.pk).update(**update)

    def test_blank_title_uses_period_as_in_figma(self):
        form = LaporanForm(self.form_data(judul="   "))
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["judul"], "Laporan Dampak Oktober 2026")

    def test_create_cannot_forge_creator_status_or_metrics(self):
        response = self.client.post(
            reverse("laporan:buat"),
            self.form_data(
                dibuat_oleh=self.regular.pk,
                status="siap",
                total_porsi=999,
            ),
        )
        created = Laporan.objects.latest("pk")
        self.assertRedirects(response, created.get_absolute_url())
        self.assertEqual(created.dibuat_oleh, self.staff)
        self.assertEqual(created.status, "draf")
        self.assertIsNone(created.total_porsi)

    def test_invalid_creation_does_not_save(self):
        response = self.client.post(
            reverse("laporan:buat"), self.form_data(periode_mulai="not-a-date")
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Laporan.objects.count(), 1)

    def test_dashboard_uses_report_counts_not_fake_impact(self):
        response = self.client.get(reverse("laporan:dashboard"))
        self.assertContains(response, "Laporan Oktober")
        self.assertContains(response, "Data Klaim belum terhubung")
        self.assertEqual(response.context["stats"], {"total": 1, "draf": 1, "siap": 0})
        self.assertNotContains(response, "480 kg")

    def test_filters_and_invalid_filter(self):
        for query in ({"q": "November"}, {"status": "siap"}, {"status": "bad"}):
            with self.subTest(query=query):
                response = self.client.get(reverse("laporan:dashboard"), query)
                self.assertEqual(response.context["page_obj"].paginator.count, 0)
        self.assertEqual(
            self.client.get(reverse("laporan:dashboard"), {"q": "Oktober"})
            .context["page_obj"]
            .paginator.count,
            1,
        )

    def test_pagination_preserves_filter(self):
        for i in range(11):
            Laporan.objects.create(
                judul=f"Draf {i}",
                periode_mulai=date(2026, 1, 1),
                periode_selesai=date(2026, 1, 1),
                dibuat_oleh=self.staff,
            )
        response = self.client.get(
            reverse("laporan:dashboard"), {"q": "Draf", "page": 2}
        )
        self.assertEqual(len(response.context["page_obj"]), 1)
        self.assertEqual(response.context["filter_query"], "q=Draf")

    def test_draft_detail_marks_unknown_and_disabled_generate(self):
        response = self.client.get(self.url("detail"))
        self.assertContains(response, "Angka dampak belum tersedia")
        self.assertContains(response, "disabled")
        self.assertContains(response, "Rincian per donor belum tersedia")

    def test_html_escapes_title_and_notes(self):
        self.laporan.judul = "<script>alert(1)</script>"
        self.laporan.catatan = '<img src=x onerror="alert(1)">'
        self.laporan.save()
        response = self.client.get(self.url("detail"))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<img src=x")

    def test_all_report_endpoints_require_login(self):
        self.client.logout()
        urls = [reverse("laporan:dashboard"), reverse("laporan:buat")]
        urls += [
            self.url(name)
            for name in (
                "detail",
                "edit",
                "hapus",
                "generate",
                "ekspor_csv",
                "ekspor_pdf",
            )
        ]
        for url in urls:
            for method in ("get", "post"):
                with self.subTest(url=url, method=method):
                    response = getattr(self.client, method)(url)
                    self.assertEqual(response.status_code, 302)
                    self.assertTrue(response.url.startswith(reverse("laporan:login")))

    def test_regular_user_cannot_read_mutate_or_export_any_report(self):
        self.client.force_login(self.regular)
        urls = [reverse("laporan:dashboard"), reverse("laporan:buat")]
        urls += [
            self.url(name)
            for name in (
                "detail",
                "edit",
                "hapus",
                "generate",
                "ekspor_csv",
                "ekspor_pdf",
            )
        ]
        for url in urls:
            for method in ("get", "post"):
                with self.subTest(url=url, method=method):
                    self.assertEqual(getattr(self.client, method)(url).status_code, 403)
        self.assertEqual(Laporan.objects.count(), 1)

    def test_inactive_staff_cannot_access_reports(self):
        self.staff.is_active = False
        self.staff.save()
        self.assertEqual(self.client.get(self.url("detail")).status_code, 302)

    def test_another_staff_can_manage_campus_report_preserving_creator(self):
        self.client.force_login(self.other_staff)
        self.client.post(self.url("edit"), self.form_data(judul="Diperbarui"))
        self.laporan.refresh_from_db()
        self.assertEqual(self.laporan.judul, "Diperbarui")
        self.assertEqual(self.laporan.dibuat_oleh, self.staff)

    def test_login_rejects_regular_and_accepts_staff(self):
        self.client.logout()
        response = self.client.post(
            reverse("laporan:login"), {"username": "donor", "password": "test-pass-785"}
        )
        self.assertContains(response, "tidak memiliki akses")
        response = self.client.post(
            reverse("laporan:login"),
            {"username": "pengelola", "password": "test-pass-785"},
        )
        self.assertRedirects(response, reverse("laporan:dashboard"))

    def test_login_rejects_external_next_redirect(self):
        self.client.logout()
        response = self.client.post(
            reverse("laporan:login"),
            {
                "username": "pengelola",
                "password": "test-pass-785",
                "next": "https://untrusted.example/",
            },
        )
        self.assertRedirects(response, reverse("laporan:dashboard"))

    def test_logout_requires_post(self):
        self.assertEqual(self.client.get(reverse("laporan:logout")).status_code, 405)
        self.assertRedirects(
            self.client.post(reverse("laporan:logout")), reverse("laporan:login")
        )

    def test_csrf_is_required_for_mutations(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        for url in [
            reverse("laporan:buat"),
            self.url("edit"),
            self.url("hapus"),
            self.url("generate"),
            reverse("laporan:logout"),
        ]:
            with self.subTest(url=url):
                self.assertEqual(client.post(url, self.form_data()).status_code, 403)

    def test_get_delete_only_confirms_and_post_deletes(self):
        self.assertContains(self.client.get(self.url("hapus")), "Hapus laporan ini?")
        self.assertTrue(Laporan.objects.filter(pk=self.laporan.pk).exists())
        self.assertRedirects(
            self.client.post(self.url("hapus")), reverse("laporan:dashboard")
        )
        self.assertFalse(Laporan.objects.filter(pk=self.laporan.pk).exists())

    def test_generate_requires_post(self):
        self.assertEqual(self.client.get(self.url("generate")).status_code, 405)

    def test_unavailable_source_leaves_draft_unknown(self):
        with self.assertRaises(SumberDataBelumTersedia):
            hitung_laporan(self.laporan)
        response = self.client.post(self.url("generate"), follow=True)
        self.assertContains(response, "Data Klaim belum terhubung")
        self.laporan.refresh_from_db()
        self.assertIsNone(self.laporan.total_porsi)
        self.assertEqual(self.laporan.status, "draf")

    @override_settings(LAPORAN_AGGREGATOR="laporan.tests.successful_provider")
    def test_adapter_receives_period_and_saves_snapshot(self):
        with patch(
            "laporan.tests.successful_provider", return_value=RingkasanDampak(25, 2, 7)
        ) as provider:
            self.client.post(self.url("generate"))
        provider.assert_called_once_with(date(2026, 10, 1), date(2026, 10, 31))
        self.laporan.refresh_from_db()
        self.assertEqual(
            (
                self.laporan.total_porsi,
                self.laporan.jumlah_donor,
                self.laporan.jumlah_penerima,
            ),
            (25, 2, 7),
        )
        self.assertEqual(self.laporan.status, "siap")
        self.assertIsNotNone(self.laporan.dihitung_pada)

    @override_settings(LAPORAN_AGGREGATOR="laporan.tests.zero_provider")
    def test_real_zero_differs_from_unknown(self):
        self.client.post(self.url("generate"))
        self.laporan.refresh_from_db()
        self.assertEqual(self.laporan.total_porsi, 0)
        self.assertEqual(self.laporan.status, "siap")
        self.assertNotContains(self.client.get(self.url("detail")), "Belum tersedia")

    def test_invalid_adapter_result_does_not_replace_saved_snapshot(self):
        self.ready()
        with (
            override_settings(LAPORAN_AGGREGATOR="laporan.tests.invalid_provider"),
            self.assertLogs("laporan.views", level="ERROR"),
        ):
            response = self.client.post(self.url("generate"), follow=True)
        self.assertContains(response, "Perhitungan belum berhasil")
        self.laporan.refresh_from_db()
        self.assertEqual(self.laporan.total_porsi, 25)

    def test_snapshot_validation_rejects_bad_numbers(self):
        for value in (-1, True, 2.5, "3", 2**63):
            with self.subTest(value=value), self.assertRaises(HasilAgregasiTidakValid):
                RingkasanDampak(value, 0, 0).validate()

    def test_period_edit_invalidates_old_metrics(self):
        self.ready()
        self.client.post(self.url("edit"), self.form_data(periode_selesai="2026-10-20"))
        self.laporan.refresh_from_db()
        self.assertEqual(self.laporan.status, "draf")
        self.assertIsNone(self.laporan.total_porsi)
        self.assertIsNone(self.laporan.dihitung_pada)

    def test_note_edit_keeps_snapshot(self):
        self.ready()
        self.client.post(self.url("edit"), self.form_data(catatan="Catatan baru"))
        self.laporan.refresh_from_db()
        self.assertEqual(self.laporan.total_porsi, 25)
        self.assertEqual(self.laporan.status, "siap")

    def test_unknown_pk_returns_404(self):
        for name in ("detail", "edit", "hapus", "ekspor_csv", "ekspor_pdf"):
            with self.subTest(name=name):
                self.assertEqual(
                    self.client.get(self.url(name, pk=999999)).status_code, 404
                )

    def test_csv_marks_unknown_and_prevents_formula_injection(self):
        self.laporan.judul = '=HYPERLINK("https://untrusted.example")'
        self.laporan.catatan = "  +SUM(1,2)\nbaris kedua"
        self.laporan.save()
        response = self.client.get(self.url("ekspor_csv"))
        self.assertEqual(response.status_code, 200)
        rows = dict(
            list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))[1:]
        )
        self.assertEqual(rows["Total makanan tersalurkan (porsi)"], "Belum tersedia")
        self.assertTrue(rows["Judul"].startswith("'="))
        self.assertTrue(rows["Catatan"].startswith("'  +"))
        self.assertIn("attachment", response["Content-Disposition"])

    def test_csv_exports_saved_values(self):
        self.ready()
        rows = dict(
            list(csv.reader(StringIO(buat_csv(self.laporan).lstrip("\ufeff"))))[1:]
        )
        self.assertEqual(rows["Total makanan tersalurkan (porsi)"], "25")
        self.assertEqual(rows["Jumlah donor unik"], "2")

    def test_pdf_download_is_pdf(self):
        response = self.client.get(self.url("ekspor_pdf"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertTrue(response.content.rstrip().endswith(b"%%EOF"))

    def test_pdf_handles_long_notes_and_markup_as_text(self):
        self.laporan.catatan = "<b>Catatan & teks</b> " * 140
        self.assertTrue(buat_pdf(self.laporan).startswith(b"%PDF-"))

    def test_missing_pdf_dependency_shows_csv_fallback(self):
        with patch("laporan.views.buat_pdf", side_effect=PDFDependencyMissing):
            response = self.client.get(self.url("ekspor_pdf"))
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, "Unduh tabel CSV", status_code=503)

    @override_settings(LAPORAN_AGGREGATOR="laporan.tests.successful_provider")
    def test_dashboard_annual_counts_come_from_source_not_overlapping_reports(self):
        self.ready()
        with patch(
            "laporan.views.ringkasan_periode", return_value=RingkasanDampak(90, 3, 12)
        ) as provider:
            response = self.client.get(reverse("laporan:dashboard"))
        year = timezone.localdate().year
        provider.assert_called_once_with(date(year, 1, 1), date(year, 12, 31))
        self.assertEqual(response.context["annual_impact"].total_porsi, 90)

    @override_settings(LAPORAN_AGGREGATOR="laporan.tests.successful_provider")
    def test_edit_recalculate_uses_new_validated_period(self):
        with patch(
            "laporan.tests.successful_provider", return_value=RingkasanDampak(15, 2, 4)
        ) as provider:
            self.client.post(
                self.url("edit"),
                self.form_data(periode_selesai="2026-10-15", action="recalculate"),
            )
        provider.assert_called_once_with(date(2026, 10, 1), date(2026, 10, 15))
        self.laporan.refresh_from_db()
        self.assertEqual(self.laporan.total_porsi, 15)
        self.assertEqual(self.laporan.status, "siap")

    def test_crafted_recalculate_without_source_still_saves_honest_draft(self):
        response = self.client.post(
            self.url("edit"), self.form_data(action="recalculate"), follow=True
        )
        self.assertContains(response, "Data Klaim belum terhubung")
        self.laporan.refresh_from_db()
        self.assertIsNone(self.laporan.total_porsi)

    def test_indonesian_number_format_preserves_unknown_and_zero(self):
        from .templatetags.laporan_format import angka_dampak, periode_laporan

        self.assertEqual(angka_dampak(None), "—")
        self.assertEqual(angka_dampak(0), "0")
        self.assertEqual(angka_dampak(1240), "1.240")
        self.assertEqual(periode_laporan(self.laporan), "Oktober 2026")
