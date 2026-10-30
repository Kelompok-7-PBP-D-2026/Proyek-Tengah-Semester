import re
from datetime import datetime, timedelta
from decimal import Decimal
from io import StringIO

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import get_messages
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from donasi.models import Donasi
from profil.models import ProfilDonor, ProfilPenerima

from . import integrations, services, utils
from .models import MAX_PORTIONS_PER_CLAIM, PICKUP_GRACE_MINUTES, Claim, ClaimStatus
from .services import WRONG_CODE_MESSAGE, ClaimError

# Plain storages so {% static %} never needs a collectstatic manifest in tests.
PLAIN_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

User = get_user_model()


def at(hour, minute=0, second=0, day=30):
    """Build an aware WIB datetime on a fixed day (for pure utility tests)."""
    return datetime(2026, 10, day, hour, minute, second, tzinfo=utils.WIB)


# ---- utilities --------------------------------------------------------------

class PickupCodeTests(SimpleTestCase):
    """Pickup code generation and normalization."""

    def test_generated_code_has_the_expected_format(self):
        pattern = re.compile(r"^MBG-[%s]{%d}$" % (utils.PICKUP_CODE_ALPHABET, utils.PICKUP_CODE_LENGTH))
        for _ in range(200):
            self.assertRegex(utils.generate_pickup_code(), pattern)

    def test_alphabet_has_no_confusing_characters(self):
        for char in "0O1I":
            self.assertNotIn(char, utils.PICKUP_CODE_ALPHABET)

    def test_normalize_accepts_common_inputs(self):
        for raw in ("7k2q", "mbg7k2q", "MBG-7K2Q", " mbg-7k2q ", "mbg 7k2q"):
            self.assertEqual(utils.normalize_pickup_code(raw), "MBG-7K2Q", raw)

    def test_normalize_empty_returns_empty(self):
        self.assertEqual(utils.normalize_pickup_code(""), "")
        self.assertEqual(utils.normalize_pickup_code(None), "")
        self.assertEqual(utils.normalize_pickup_code("   "), "")


class PickupSlotTests(SimpleTestCase):
    """30-minute pickup slots."""

    def test_next_slot_start_rounds_up(self):
        self.assertEqual(utils.next_slot_start(at(10, 12)), at(10, 30))
        self.assertEqual(utils.next_slot_start(at(10, 45)), at(11, 0))

    def test_next_slot_start_keeps_an_exact_boundary(self):
        self.assertEqual(utils.next_slot_start(at(10, 30)), at(10, 30))

    def test_next_slot_start_moves_on_after_a_boundary_by_seconds(self):
        self.assertEqual(utils.next_slot_start(at(10, 30, 5)), at(11, 0))

    def test_slots_run_until_strictly_before_the_deadline(self):
        slots = utils.build_pickup_slots(at(12), now=at(10, 12))
        self.assertEqual(slots, [at(10, 30), at(11, 0), at(11, 30)])

    def test_slots_start_when_the_food_becomes_available(self):
        slots = utils.build_pickup_slots(at(16), now=at(10, 12), start=at(14, 5))
        self.assertEqual(slots, [at(14, 30), at(15, 0), at(15, 30)])

    def test_slots_are_empty_when_the_deadline_is_too_close(self):
        self.assertEqual(utils.build_pickup_slots(at(12), now=at(11, 50)), [])

    def test_slots_are_capped(self):
        far_deadline = at(10) + timedelta(days=5)
        slots = utils.build_pickup_slots(far_deadline, now=at(10, 12))
        self.assertEqual(len(slots), utils.MAX_SLOTS)

    def test_naive_deadline_is_treated_as_wib(self):
        naive = datetime(2026, 10, 30, 12, 0)
        slots = utils.build_pickup_slots(naive, now=at(10, 12))
        self.assertEqual(slots, [at(10, 30), at(11, 0), at(11, 30)])


class FormattingTests(SimpleTestCase):
    """Indonesian date, time, and distance formatting."""

    def test_time_and_dates(self):
        self.assertEqual(utils.format_time(at(15)), "15.00")
        self.assertEqual(utils.format_date_short(at(15)), "30 Okt")
        self.assertEqual(utils.format_datetime_short(at(15)), "30 Okt, 15.00")
        self.assertEqual(utils.format_datetime(at(15)), "30 Okt 2026, 15.00")

    def test_distance_uses_a_decimal_comma(self):
        self.assertEqual(utils.format_distance(0.84), "0,8 km")
        self.assertEqual(utils.format_distance(2.14), "2,1 km")


# ---- shared fixtures ----------------------------------------------------------

class ClaimTestCase(TestCase):
    """Base class: one donor, two recipients, and one donation with 10 portions."""

    password = "pass12345"

    def setUp(self):
        self.donor = self.make_donor("donor1", "BEM Fasilkom UI")
        self.other_donor = self.make_donor("donor2", "UKM Pecinta Alam")
        self.recipient = self.make_recipient("rina", "Rina Sari", "2506000001")
        self.other = self.make_recipient("dimas", "Dimas Pratama", "2506000002")
        self.donation = self.make_donation(self.donor)

    # -- builders --

    def make_donor(self, username, unit_name):
        user = User.objects.create_user(username, password=self.password)
        ProfilDonor.objects.create(
            user=user, nama_unit=unit_name, jenis="himpunan", kontak="donor@example.com"
        )
        return user

    def make_recipient(self, username, full_name, nim):
        user = User.objects.create_user(username, password=self.password)
        ProfilPenerima.objects.create(
            user=user, nama_lengkap=full_name, nim=nim, fakultas="fasilkom",
            kontak="penerima@example.com",
        )
        return user

    def make_plain_user(self, username):
        """A user without any profile."""
        return User.objects.create_user(username, password=self.password)

    def make_donation(self, donor, **overrides):
        now = timezone.now()
        data = {
            "donor": donor,
            "nama": "Nasi ayam",
            "jumlah_porsi": 10,
            "lokasi": "Lobi Gedung A",
            "waktu_tersedia": now - timedelta(hours=1),
            "waktu_akhir_pengambilan": now + timedelta(hours=3),
        }
        data.update(overrides)
        return Donasi.objects.create(**data)

    def make_claim(self, user=None, donation=None, portions=2):
        donation = donation or self.donation
        return services.create_claim(
            user=user or self.recipient,
            donation_id=donation.pk,
            portions=portions,
            pickup_time=timezone.now() + timedelta(minutes=10),
        )

    def make_overdue(self, claim):
        """Push a claim's expiry into the past without closing it."""
        Claim.objects.filter(pk=claim.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        claim.refresh_from_db()
        return claim

    def raw_claim(self, **overrides):
        """Insert a claim directly, bypassing the services (for constraint tests)."""
        now = timezone.now()
        data = {
            "recipient": self.recipient,
            "donor": self.donor,
            "donation_id": self.donation.pk,
            "food_name": "Nasi ayam",
            "donor_name": "BEM Fasilkom UI",
            "pickup_location": "Lobi Gedung A",
            "pickup_deadline": now + timedelta(hours=3),
            "portions": 1,
            "pickup_time": now + timedelta(minutes=10),
            "expires_at": now + timedelta(minutes=40),
        }
        data.update(overrides)
        return Claim.objects.create(**data)

    @staticmethod
    def wrong_code(claim):
        return "MBG-AAAA" if claim.pickup_code != "MBG-AAAA" else "MBG-BBBB"

    def stock(self, donation=None):
        donation = donation or self.donation
        donation.refresh_from_db()
        return donation.jumlah_porsi


# ---- models --------------------------------------------------------------------

class ClaimModelTests(ClaimTestCase):
    """Claim state helpers, pickup codes, and database constraints."""

    def test_pickup_code_is_assigned_and_unique(self):
        first = self.make_claim(self.recipient)
        second = self.make_claim(self.other)
        self.assertRegex(first.pickup_code, r"^MBG-[A-Z2-9]{4}$")
        self.assertNotEqual(first.pickup_code, second.pickup_code)

    def test_new_claim_is_pending_and_actionable(self):
        claim = self.make_claim()
        self.assertEqual(claim.status, ClaimStatus.PENDING)
        self.assertTrue(claim.can_cancel)
        self.assertTrue(claim.can_verify)
        self.assertTrue(claim.is_code_valid)
        self.assertFalse(claim.is_overdue)
        self.assertEqual(claim.display_status, ClaimStatus.PENDING)

    def test_overdue_pending_claim_is_displayed_as_expired(self):
        claim = self.make_overdue(self.make_claim())
        self.assertEqual(claim.status, ClaimStatus.PENDING)  # not closed yet
        self.assertTrue(claim.is_overdue)
        self.assertTrue(claim.is_expired)
        self.assertEqual(claim.display_status, ClaimStatus.EXPIRED)
        self.assertEqual(claim.display_status_label, "Kedaluwarsa")
        self.assertEqual(claim.badge_modifier, "expired")
        self.assertFalse(claim.can_cancel)
        self.assertFalse(claim.can_verify)

    def test_picked_up_badge_modifier_is_hyphenated(self):
        claim = self.make_claim()
        services.verify_pickup(claim, claim.pickup_code)
        self.assertEqual(claim.badge_modifier, "picked-up")
        self.assertFalse(claim.can_cancel)

    def test_timeline_for_a_pending_claim_has_two_steps(self):
        steps = self.make_claim().get_timeline()
        self.assertEqual([s["label"] for s in steps], ["Klaim dikirim", "Makanan diambil"])
        self.assertEqual([s["state"] for s in steps], ["done", "pending"])

    def test_timeline_after_pickup(self):
        claim = self.make_claim()
        services.verify_pickup(claim, claim.pickup_code)
        steps = claim.get_timeline()
        self.assertEqual([s["state"] for s in steps], ["done", "done"])

    def test_timeline_after_cancel(self):
        claim = self.make_claim()
        services.cancel_claim(claim)
        steps = claim.get_timeline()
        self.assertEqual(steps[-1]["label"], "Klaim dibatalkan pengguna")
        self.assertEqual(steps[-1]["state"], "failed")

    def test_timeline_after_expiry(self):
        claim = self.make_overdue(self.make_claim())
        steps = claim.get_timeline()
        self.assertEqual(steps[-1]["label"], "Klaim kedaluwarsa")
        self.assertEqual(steps[-1]["state"], "failed")

    def test_database_allows_only_one_pending_claim_per_recipient_and_donation(self):
        self.raw_claim()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.raw_claim()

    def test_database_allows_a_new_claim_after_the_old_one_closed(self):
        self.raw_claim(status=ClaimStatus.CANCELLED)
        self.raw_claim()  # does not raise
        self.assertEqual(Claim.objects.count(), 2)

    def test_database_rejects_portions_above_the_maximum(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.raw_claim(portions=MAX_PORTIONS_PER_CLAIM + 1)

    def test_database_rejects_zero_portions(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.raw_claim(portions=0)


# ---- services -------------------------------------------------------------------

class CreateClaimTests(ClaimTestCase):
    """services.create_claim and get_claim_blocker."""

    def test_creates_a_claim_with_a_snapshot_and_reserves_portions(self):
        claim = self.make_claim(portions=2)
        self.assertEqual(claim.recipient, self.recipient)
        self.assertEqual(claim.donor_id, self.donor.pk)
        self.assertEqual(claim.donation_id, self.donation.pk)
        self.assertEqual(claim.food_name, "Nasi ayam")
        self.assertEqual(claim.donor_name, "BEM Fasilkom UI")
        self.assertEqual(claim.pickup_location, "Lobi Gedung A")
        self.assertEqual(claim.portions, 2)
        self.assertEqual(self.stock(), 8)

    def test_expiry_is_the_pickup_time_plus_the_grace_period(self):
        claim = self.make_claim()
        self.assertEqual(
            claim.expires_at, claim.pickup_time + timedelta(minutes=PICKUP_GRACE_MINUTES)
        )

    def test_calculate_expires_at_never_passes_the_donation_deadline(self):
        pickup = at(15)
        self.assertEqual(
            services.calculate_expires_at(pickup, at(18)), pickup + timedelta(minutes=PICKUP_GRACE_MINUTES)
        )
        self.assertEqual(services.calculate_expires_at(pickup, at(15, 10)), at(15, 10))

    def test_donor_cannot_claim_their_own_donation(self):
        with self.assertRaisesMessage(ClaimError, "donasimu sendiri"):
            self.make_claim(user=self.donor)

    def test_rejects_more_than_the_per_claim_maximum(self):
        with self.assertRaisesMessage(ClaimError, "Maksimal 3 porsi per klaim."):
            self.make_claim(portions=MAX_PORTIONS_PER_CLAIM + 1)
        self.assertEqual(self.stock(), 10)

    def test_rejects_more_than_the_remaining_stock(self):
        donation = self.make_donation(self.donor, jumlah_porsi=2)
        with self.assertRaisesMessage(ClaimError, "Porsi yang tersisa hanya 2."):
            self.make_claim(donation=donation, portions=3)
        self.assertEqual(self.stock(donation), 2)

    def test_rejects_a_sold_out_donation(self):
        donation = self.make_donation(self.donor, jumlah_porsi=0)
        with self.assertRaisesMessage(ClaimError, "sudah habis"):
            self.make_claim(donation=donation, portions=1)

    def test_rejects_a_donation_past_its_deadline(self):
        now = timezone.now()
        donation = self.make_donation(
            self.donor,
            waktu_tersedia=now - timedelta(hours=3),
            waktu_akhir_pengambilan=now - timedelta(hours=1),
        )
        with self.assertRaisesMessage(ClaimError, "Batas ambil donasi ini sudah lewat."):
            self.make_claim(donation=donation, portions=1)

    def test_rejects_a_second_active_claim_on_the_same_donation(self):
        self.make_claim()
        with self.assertRaisesMessage(ClaimError, "klaim aktif"):
            self.make_claim()
        self.assertEqual(Claim.objects.count(), 1)
        self.assertEqual(self.stock(), 8)

    def test_allows_a_new_claim_after_cancelling_the_old_one(self):
        claim = self.make_claim()
        services.cancel_claim(claim)
        self.make_claim()  # does not raise
        self.assertEqual(self.stock(), 8)

    def test_two_recipients_cannot_exceed_the_stock(self):
        donation = self.make_donation(self.donor, jumlah_porsi=4)
        self.make_claim(user=self.recipient, donation=donation, portions=3)
        with self.assertRaisesMessage(ClaimError, "Porsi yang tersisa hanya 1."):
            self.make_claim(user=self.other, donation=donation, portions=2)
        self.assertEqual(self.stock(donation), 1)

    def test_rejects_a_pickup_time_in_the_past(self):
        with self.assertRaisesMessage(ClaimError, "Waktu ambil tidak valid."):
            services.create_claim(
                user=self.recipient, donation_id=self.donation.pk, portions=1,
                pickup_time=timezone.now() - timedelta(hours=1),
            )

    def test_rejects_a_pickup_time_after_the_deadline(self):
        with self.assertRaisesMessage(ClaimError, "Waktu ambil tidak valid."):
            services.create_claim(
                user=self.recipient, donation_id=self.donation.pk, portions=1,
                pickup_time=timezone.now() + timedelta(hours=5),
            )

    def test_rejects_a_pickup_time_before_the_food_is_available(self):
        donation = self.make_donation(
            self.donor, waktu_tersedia=timezone.now() + timedelta(hours=1)
        )
        with self.assertRaisesMessage(ClaimError, "Waktu ambil tidak valid."):
            services.create_claim(
                user=self.recipient, donation_id=donation.pk, portions=1,
                pickup_time=timezone.now() + timedelta(minutes=10),
            )

    def test_unknown_donation(self):
        with self.assertRaisesMessage(ClaimError, "Donasi tidak ditemukan."):
            services.create_claim(
                user=self.recipient, donation_id=999999, portions=1,
                pickup_time=timezone.now() + timedelta(minutes=10),
            )

    def test_overdue_claims_free_their_portions_before_a_new_claim(self):
        donation = self.make_donation(self.donor, jumlah_porsi=3)
        old = self.make_claim(user=self.other, donation=donation, portions=3)
        self.assertEqual(self.stock(donation), 0)
        self.make_overdue(old)
        self.make_claim(user=self.recipient, donation=donation, portions=3)  # does not raise
        old.refresh_from_db()
        self.assertEqual(old.status, ClaimStatus.EXPIRED)


class CancelClaimTests(ClaimTestCase):
    """services.cancel_claim."""

    def test_cancel_returns_the_portions(self):
        claim = self.make_claim(portions=2)
        self.assertEqual(self.stock(), 8)
        services.cancel_claim(claim)
        claim.refresh_from_db()
        self.assertEqual(claim.status, ClaimStatus.CANCELLED)
        self.assertIsNotNone(claim.closed_at)
        self.assertEqual(self.stock(), 10)

    def test_cannot_cancel_twice(self):
        claim = self.make_claim()
        services.cancel_claim(claim)
        with self.assertRaisesMessage(ClaimError, "sudah tidak aktif"):
            services.cancel_claim(claim)
        self.assertEqual(self.stock(), 10)

    def test_cannot_cancel_a_picked_up_claim(self):
        claim = self.make_claim()
        services.verify_pickup(claim, claim.pickup_code)
        with self.assertRaisesMessage(ClaimError, "sudah diambil"):
            services.cancel_claim(claim)
        claim.refresh_from_db()
        self.assertEqual(claim.status, ClaimStatus.PICKED_UP)
        self.assertEqual(self.stock(), 8)

    def test_cancelling_an_overdue_claim_expires_it_instead(self):
        claim = self.make_overdue(self.make_claim())
        with self.assertRaisesMessage(ClaimError, "kedaluwarsa"):
            services.cancel_claim(claim)
        claim.refresh_from_db()
        self.assertEqual(claim.status, ClaimStatus.EXPIRED)
        self.assertEqual(self.stock(), 10)


class VerifyPickupTests(ClaimTestCase):
    """services.verify_pickup."""

    def test_correct_code_marks_the_claim_as_picked_up(self):
        claim = self.make_claim(portions=2)
        services.verify_pickup(claim, claim.pickup_code)
        claim.refresh_from_db()
        self.assertEqual(claim.status, ClaimStatus.PICKED_UP)
        self.assertIsNotNone(claim.picked_up_at)

    def test_picked_up_does_not_change_the_stock(self):
        claim = self.make_claim(portions=2)
        services.verify_pickup(claim, claim.pickup_code)
        self.assertEqual(self.stock(), 8)

    def test_code_is_case_and_format_insensitive(self):
        claim = self.make_claim()
        services.verify_pickup(claim, claim.pickup_code.lower().replace("-", ""))
        claim.refresh_from_db()
        self.assertEqual(claim.status, ClaimStatus.PICKED_UP)

    def test_wrong_code_is_rejected_and_the_claim_stays_pending(self):
        claim = self.make_claim()
        with self.assertRaisesMessage(ClaimError, WRONG_CODE_MESSAGE):
            services.verify_pickup(claim, self.wrong_code(claim))
        claim.refresh_from_db()
        self.assertEqual(claim.status, ClaimStatus.PENDING)

    def test_empty_code_is_rejected(self):
        claim = self.make_claim()
        with self.assertRaisesMessage(ClaimError, WRONG_CODE_MESSAGE):
            services.verify_pickup(claim, "")

    def test_a_code_cannot_be_used_twice(self):
        claim = self.make_claim()
        services.verify_pickup(claim, claim.pickup_code)
        with self.assertRaisesMessage(ClaimError, "sudah selesai"):
            services.verify_pickup(claim, claim.pickup_code)

    def test_cancelled_claim_cannot_be_verified(self):
        claim = self.make_claim()
        services.cancel_claim(claim)
        with self.assertRaisesMessage(ClaimError, "dibatalkan"):
            services.verify_pickup(claim, claim.pickup_code)

    def test_expired_claim_cannot_be_verified(self):
        claim = self.make_overdue(self.make_claim())
        services.expire_overdue_claims()
        claim.refresh_from_db()
        with self.assertRaisesMessage(ClaimError, "kedaluwarsa"):
            services.verify_pickup(claim, claim.pickup_code)

    def test_verifying_an_overdue_claim_expires_it(self):
        claim = self.make_overdue(self.make_claim())
        with self.assertRaisesMessage(ClaimError, "kedaluwarsa"):
            services.verify_pickup(claim, claim.pickup_code)
        claim.refresh_from_db()
        self.assertEqual(claim.status, ClaimStatus.EXPIRED)
        self.assertEqual(self.stock(), 10)


class ExpireOverdueClaimsTests(ClaimTestCase):
    """services.expire_overdue_claims and the expire_claims command."""

    def test_expires_overdue_claims_and_returns_the_portions(self):
        claim = self.make_overdue(self.make_claim(portions=3))
        self.assertEqual(self.stock(), 7)
        self.assertEqual(services.expire_overdue_claims(), 1)
        claim.refresh_from_db()
        self.assertEqual(claim.status, ClaimStatus.EXPIRED)
        self.assertEqual(claim.closed_at, claim.expires_at)
        self.assertEqual(self.stock(), 10)

    def test_is_idempotent(self):
        self.make_overdue(self.make_claim(portions=3))
        services.expire_overdue_claims()
        self.assertEqual(services.expire_overdue_claims(), 0)
        self.assertEqual(self.stock(), 10)  # the portions are not returned twice

    def test_leaves_active_and_finished_claims_alone(self):
        active = self.make_claim(user=self.recipient)
        done = self.make_claim(user=self.other, portions=1)
        services.verify_pickup(done, done.pickup_code)
        self.assertEqual(services.expire_overdue_claims(), 0)
        active.refresh_from_db()
        done.refresh_from_db()
        self.assertEqual(active.status, ClaimStatus.PENDING)
        self.assertEqual(done.status, ClaimStatus.PICKED_UP)
        self.assertEqual(self.stock(), 7)

    def test_can_be_limited_to_one_donation(self):
        other_donation = self.make_donation(self.donor)
        first = self.make_overdue(self.make_claim(donation=self.donation))
        second = self.make_overdue(self.make_claim(donation=other_donation))
        self.assertEqual(services.expire_overdue_claims(donation_id=self.donation.pk), 1)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, ClaimStatus.EXPIRED)
        self.assertEqual(second.status, ClaimStatus.PENDING)

    def test_management_command(self):
        self.make_overdue(self.make_claim())
        out = StringIO()
        call_command("expire_claims", stdout=out)
        self.assertIn("1 claim(s) expired.", out.getvalue())


# ---- views: recipient ----------------------------------------------------------

@override_settings(STORAGES=PLAIN_STORAGES)
class ClaimCreateViewTests(ClaimTestCase):
    """The claim form (views.claim_create)."""

    def setUp(self):
        super().setUp()
        self.url = reverse("klaim:claim_create", args=[self.donation.pk])

    def valid_post(self, portions=1, note=""):
        slots = utils.build_pickup_slots(
            self.donation.waktu_akhir_pengambilan, start=self.donation.waktu_tersedia
        )
        # slots[1] still exists if the clock crosses a half-hour boundary mid-test.
        return {"portions": portions, "pickup_time": slots[1].isoformat(), "note": note}

    def test_login_is_required(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.assertEqual(self.client.post(self.url, self.valid_post()).status_code, 302)
        self.assertEqual(Claim.objects.count(), 0)

    def test_recipient_sees_the_form(self):
        self.client.force_login(self.recipient)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nasi ayam")
        self.assertContains(response, "tersisa 10")
        self.assertEqual(response.context["form"].max_portions, MAX_PORTIONS_PER_CLAIM)

    def test_unknown_donation_is_404(self):
        self.client.force_login(self.recipient)
        response = self.client.get(reverse("klaim:claim_create", args=[999999]))
        self.assertEqual(response.status_code, 404)

    def test_donor_is_turned_away(self):
        self.client.force_login(self.donor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Claim.objects.count(), 0)

    def test_user_without_a_profile_is_turned_away(self):
        self.client.force_login(self.make_plain_user("nobody"))
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        texts = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("profil penerima" in text for text in texts))

    def test_valid_submission_creates_a_claim(self):
        self.client.force_login(self.recipient)
        response = self.client.post(self.url, self.valid_post(portions=2, note="Bersama teman"))
        claim = Claim.objects.get()
        self.assertRedirects(
            response, reverse("klaim:claim_detail", args=[claim.pk]), fetch_redirect_response=False
        )
        self.assertEqual(claim.recipient, self.recipient)
        self.assertEqual(claim.donor, self.donor)
        self.assertEqual(claim.donor_name, "BEM Fasilkom UI")
        self.assertEqual(claim.portions, 2)
        self.assertEqual(claim.note, "Bersama teman")
        self.assertEqual(self.stock(), 8)

    def test_too_many_portions_is_rejected(self):
        self.client.force_login(self.recipient)
        response = self.client.post(self.url, self.valid_post(portions=4))
        self.assertEqual(response.status_code, 200)
        self.assertIn("portions", response.context["form"].errors)
        self.assertEqual(Claim.objects.count(), 0)
        self.assertEqual(self.stock(), 10)

    def test_zero_portions_is_rejected(self):
        self.client.force_login(self.recipient)
        response = self.client.post(self.url, self.valid_post(portions=0))
        self.assertIn("portions", response.context["form"].errors)
        self.assertEqual(Claim.objects.count(), 0)

    def test_a_slot_that_was_never_offered_is_rejected(self):
        self.client.force_login(self.recipient)
        data = self.valid_post()
        data["pickup_time"] = "2020-01-01T00:00:00+07:00"
        response = self.client.post(self.url, data)
        self.assertIn("pickup_time", response.context["form"].errors)
        self.assertEqual(Claim.objects.count(), 0)

    def test_a_note_over_the_limit_is_rejected(self):
        self.client.force_login(self.recipient)
        response = self.client.post(self.url, self.valid_post(note="x" * 141))
        self.assertIn("note", response.context["form"].errors)
        self.assertEqual(Claim.objects.count(), 0)

    def test_second_claim_on_the_same_donation_is_blocked(self):
        self.client.force_login(self.recipient)
        self.client.post(self.url, self.valid_post())
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("klaim:claim_list"), fetch_redirect_response=False)
        texts = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("klaim aktif" in text for text in texts))
        self.assertEqual(Claim.objects.count(), 1)


@override_settings(STORAGES=PLAIN_STORAGES)
class ClaimListViewTests(ClaimTestCase):
    """Klaim Saya (views.claim_list)."""

    def setUp(self):
        super().setUp()
        self.url = reverse("klaim:claim_list")

    def test_login_is_required(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_shows_only_the_users_own_claims(self):
        self.make_claim(user=self.recipient)
        self.make_claim(user=self.other)
        self.client.force_login(self.recipient)
        response = self.client.get(self.url)
        claims = list(response.context["page_obj"].object_list)
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].recipient, self.recipient)

    def test_empty_state(self):
        self.client.force_login(self.recipient)
        response = self.client.get(self.url)
        self.assertContains(response, "Belum ada klaim")

    def test_status_filters_have_counts(self):
        second = self.make_donation(self.donor)
        self.make_claim(donation=self.donation)
        cancelled = self.make_claim(donation=second)
        services.cancel_claim(cancelled)
        self.client.force_login(self.recipient)
        filters = {f["key"]: f["count"] for f in self.client.get(self.url).context["status_filters"]}
        self.assertEqual(filters[""], 2)
        self.assertEqual(filters["pending"], 1)
        self.assertEqual(filters["cancelled"], 1)
        self.assertEqual(filters["picked_up"], 0)
        self.assertEqual(filters["expired"], 0)
        self.assertNotIn("approved", filters)

    def test_status_filter_narrows_the_table(self):
        second = self.make_donation(self.donor)
        self.make_claim(donation=self.donation)
        services.cancel_claim(self.make_claim(donation=second))
        self.client.force_login(self.recipient)
        response = self.client.get(self.url, {"status": "cancelled"})
        claims = list(response.context["page_obj"].object_list)
        self.assertEqual([c.status for c in claims], [ClaimStatus.CANCELLED])

    def test_unknown_status_filter_is_ignored(self):
        self.make_claim()
        self.client.force_login(self.recipient)
        response = self.client.get(self.url, {"status": "approved"})
        self.assertEqual(response.context["selected_status"], "")
        self.assertEqual(len(response.context["page_obj"].object_list), 1)

    def test_pagination_has_five_rows_per_page(self):
        for _ in range(6):
            self.make_claim(donation=self.make_donation(self.donor), portions=1)
        self.client.force_login(self.recipient)
        first = self.client.get(self.url)
        second = self.client.get(self.url, {"page": 2})
        self.assertEqual(len(first.context["page_obj"].object_list), 5)
        self.assertEqual(len(second.context["page_obj"].object_list), 1)

    def test_opening_the_page_expires_overdue_claims(self):
        claim = self.make_overdue(self.make_claim(portions=3))
        self.client.force_login(self.recipient)
        response = self.client.get(self.url)
        claim.refresh_from_db()
        self.assertEqual(claim.status, ClaimStatus.EXPIRED)
        self.assertEqual(self.stock(), 10)
        self.assertContains(response, "Klaim kedaluwarsa")


@override_settings(STORAGES=PLAIN_STORAGES)
class ClaimDetailViewTests(ClaimTestCase):
    """Detail Klaim (views.claim_detail)."""

    def test_owner_sees_the_pickup_code_and_the_cancel_button(self):
        claim = self.make_claim()
        self.client.force_login(self.recipient)
        response = self.client.get(reverse("klaim:claim_detail", args=[claim.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, claim.pickup_code)
        self.assertContains(response, "Batalkan klaim")
        self.assertEqual(len(response.context["timeline"]), 2)

    def test_picked_up_claim_has_no_cancel_button(self):
        claim = self.make_claim()
        services.verify_pickup(claim, claim.pickup_code)
        self.client.force_login(self.recipient)
        response = self.client.get(reverse("klaim:claim_detail", args=[claim.pk]))
        self.assertContains(response, "Makanan sudah diambil")
        self.assertNotContains(response, "Batalkan klaim")

    def test_cancelled_claim_has_no_cancel_button(self):
        claim = self.make_claim()
        services.cancel_claim(claim)
        self.client.force_login(self.recipient)
        response = self.client.get(reverse("klaim:claim_detail", args=[claim.pk]))
        self.assertNotContains(response, "Batalkan klaim")

    def test_other_recipients_get_404(self):
        claim = self.make_claim()
        self.client.force_login(self.other)
        response = self.client.get(reverse("klaim:claim_detail", args=[claim.pk]))
        self.assertEqual(response.status_code, 404)

    def test_the_donor_cannot_open_the_recipient_page(self):
        claim = self.make_claim()
        self.client.force_login(self.donor)
        response = self.client.get(reverse("klaim:claim_detail", args=[claim.pk]))
        self.assertEqual(response.status_code, 404)

    def test_login_is_required(self):
        claim = self.make_claim()
        response = self.client.get(reverse("klaim:claim_detail", args=[claim.pk]))
        self.assertEqual(response.status_code, 302)


@override_settings(STORAGES=PLAIN_STORAGES)
class ClaimCancelViewTests(ClaimTestCase):
    """views.claim_cancel."""

    def url(self, claim):
        return reverse("klaim:claim_cancel", args=[claim.pk])

    def test_get_is_not_allowed(self):
        claim = self.make_claim()
        self.client.force_login(self.recipient)
        self.assertEqual(self.client.get(self.url(claim)).status_code, 405)

    def test_owner_can_cancel_and_the_portions_return(self):
        claim = self.make_claim(portions=2)
        self.client.force_login(self.recipient)
        response = self.client.post(self.url(claim))
        self.assertRedirects(response, reverse("klaim:claim_list"), fetch_redirect_response=False)
        claim.refresh_from_db()
        self.assertEqual(claim.status, ClaimStatus.CANCELLED)
        self.assertEqual(self.stock(), 10)

    def test_redirects_back_to_a_safe_next_url(self):
        claim = self.make_claim()
        self.client.force_login(self.recipient)
        detail = reverse("klaim:claim_detail", args=[claim.pk])
        response = self.client.post(self.url(claim), {"next": detail})
        self.assertRedirects(response, detail, fetch_redirect_response=False)

    def test_ignores_an_external_next_url(self):
        claim = self.make_claim()
        self.client.force_login(self.recipient)
        response = self.client.post(self.url(claim), {"next": "https://evil.example.com/"})
        self.assertRedirects(response, reverse("klaim:claim_list"), fetch_redirect_response=False)

    def test_another_recipient_cannot_cancel(self):
        claim = self.make_claim()
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url(claim)).status_code, 404)
        claim.refresh_from_db()
        self.assertEqual(claim.status, ClaimStatus.PENDING)

    def test_a_picked_up_claim_cannot_be_cancelled(self):
        claim = self.make_claim()
        services.verify_pickup(claim, claim.pickup_code)
        self.client.force_login(self.recipient)
        response = self.client.post(self.url(claim))
        claim.refresh_from_db()
        self.assertEqual(claim.status, ClaimStatus.PICKED_UP)
        texts = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("sudah diambil" in text for text in texts))

    def test_login_is_required(self):
        claim = self.make_claim()
        self.assertEqual(self.client.post(self.url(claim)).status_code, 302)
        claim.refresh_from_db()
        self.assertEqual(claim.status, ClaimStatus.PENDING)


# ---- views: donor ---------------------------------------------------------------

@override_settings(STORAGES=PLAIN_STORAGES)
class IncomingClaimViewTests(ClaimTestCase):
    """Klaim Masuk (views.incoming_claim_list)."""

    def setUp(self):
        super().setUp()
        self.url = reverse("klaim:incoming_claim_list")

    def test_login_is_required(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_recipients_are_forbidden(self):
        self.client.force_login(self.recipient)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_user_without_a_role_is_forbidden(self):
        self.client.force_login(self.make_plain_user("nobody"))
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_donor_sees_claims_with_a_masked_nim(self):
        self.make_claim()
        self.client.force_login(self.donor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rina Sari (2506 xxxx)")
        self.assertNotContains(response, "2506000001")
        self.assertContains(response, "Setujui")

    def test_donor_sees_only_claims_on_their_own_donations(self):
        self.make_claim()
        self.client.force_login(self.other_donor)
        response = self.client.get(self.url)
        self.assertEqual(len(response.context["page_obj"].object_list), 0)

    def test_summary_cards(self):
        second = self.make_donation(self.donor)
        third = self.make_donation(self.donor)
        self.make_claim(user=self.recipient, donation=self.donation)
        picked = self.make_claim(user=self.recipient, donation=second)
        services.verify_pickup(picked, picked.pickup_code)
        services.cancel_claim(self.make_claim(user=self.recipient, donation=third))
        self.client.force_login(self.donor)
        stats = [s["value"] for s in self.client.get(self.url).context["stats"]]
        self.assertEqual(stats, [1, 1, 1])  # waiting, picked up, not picked up

    def test_finished_claims_have_no_verify_button(self):
        claim = self.make_claim()
        services.verify_pickup(claim, claim.pickup_code)
        self.client.force_login(self.donor)
        response = self.client.get(self.url)
        self.assertContains(response, "Selesai")
        self.assertNotContains(response, "data-verify-open")


@override_settings(STORAGES=PLAIN_STORAGES)
class VerifyCodeViewTests(ClaimTestCase):
    """The verification modal endpoint (views.claim_verify_code)."""

    ajax = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}

    def url(self, claim):
        return reverse("klaim:claim_verify_code", args=[claim.pk])

    def test_get_is_not_allowed(self):
        claim = self.make_claim()
        self.client.force_login(self.donor)
        self.assertEqual(self.client.get(self.url(claim)).status_code, 405)

    def test_correct_code_completes_the_claim(self):
        claim = self.make_claim()
        self.client.force_login(self.donor)
        response = self.client.post(self.url(claim), {"pickup_code": claim.pickup_code}, **self.ajax)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        claim.refresh_from_db()
        self.assertEqual(claim.status, ClaimStatus.PICKED_UP)

    def test_wrong_code_answers_400_with_the_message(self):
        claim = self.make_claim()
        self.client.force_login(self.donor)
        response = self.client.post(self.url(claim), {"pickup_code": self.wrong_code(claim)}, **self.ajax)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.assertEqual(response.json()["message"], WRONG_CODE_MESSAGE)
        claim.refresh_from_db()
        self.assertEqual(claim.status, ClaimStatus.PENDING)

    def test_plain_post_redirects_back_to_the_list(self):
        claim = self.make_claim()
        self.client.force_login(self.donor)
        response = self.client.post(self.url(claim), {"pickup_code": self.wrong_code(claim)})
        self.assertRedirects(
            response, reverse("klaim:incoming_claim_list"), fetch_redirect_response=False
        )

    def test_another_donor_cannot_verify(self):
        claim = self.make_claim()
        self.client.force_login(self.other_donor)
        response = self.client.post(self.url(claim), {"pickup_code": claim.pickup_code}, **self.ajax)
        self.assertEqual(response.status_code, 404)
        claim.refresh_from_db()
        self.assertEqual(claim.status, ClaimStatus.PENDING)

    def test_recipients_cannot_verify_their_own_claim(self):
        claim = self.make_claim()
        self.client.force_login(self.recipient)
        response = self.client.post(self.url(claim), {"pickup_code": claim.pickup_code}, **self.ajax)
        self.assertEqual(response.status_code, 403)
        claim.refresh_from_db()
        self.assertEqual(claim.status, ClaimStatus.PENDING)

    def test_login_is_required(self):
        claim = self.make_claim()
        response = self.client.post(self.url(claim), {"pickup_code": claim.pickup_code})
        self.assertEqual(response.status_code, 302)
        claim.refresh_from_db()
        self.assertEqual(claim.status, ClaimStatus.PENDING)

    def test_cancelled_claims_cannot_be_verified(self):
        claim = self.make_claim()
        services.cancel_claim(claim)
        self.client.force_login(self.donor)
        response = self.client.post(self.url(claim), {"pickup_code": claim.pickup_code}, **self.ajax)
        self.assertEqual(response.status_code, 400)

    def test_the_recipient_sees_the_result(self):
        claim = self.make_claim()
        self.client.force_login(self.donor)
        self.client.post(self.url(claim), {"pickup_code": claim.pickup_code}, **self.ajax)
        self.client.force_login(self.recipient)
        response = self.client.get(reverse("klaim:claim_detail", args=[claim.pk]))
        self.assertContains(response, "Makanan sudah diambil")
        self.assertNotContains(response, "Batalkan klaim")


# ---- integrations -----------------------------------------------------------------

class RoleTests(ClaimTestCase):
    """Roles come from the profil module."""

    def test_recipient_role(self):
        self.assertTrue(integrations.is_recipient(self.recipient))
        self.assertFalse(integrations.is_donor(self.recipient))
        self.assertIsNone(integrations.recipient_block_reason(self.recipient))

    def test_donor_role(self):
        self.assertTrue(integrations.is_donor(self.donor))
        self.assertFalse(integrations.is_recipient(self.donor))
        self.assertIn("donor", integrations.recipient_block_reason(self.donor))

    def test_user_without_a_profile_has_no_role(self):
        user = self.make_plain_user("nobody")
        self.assertFalse(integrations.is_recipient(user))
        self.assertFalse(integrations.is_donor(user))
        self.assertIn("Lengkapi profil", integrations.recipient_block_reason(user))

    def test_anonymous_user_has_no_role(self):
        anonymous = AnonymousUser()
        self.assertFalse(integrations.is_recipient(anonymous))
        self.assertFalse(integrations.is_donor(anonymous))
        self.assertIn("Masuk dulu", integrations.recipient_block_reason(anonymous))

    def test_inactive_user_has_no_role(self):
        self.recipient.is_active = False
        self.recipient.save()
        self.assertFalse(integrations.is_recipient(self.recipient))

    def test_display_names(self):
        self.assertEqual(integrations.get_user_display_name(self.recipient), "Rina Sari")
        self.assertEqual(integrations.get_user_display_name(self.donor), "BEM Fasilkom UI")
        self.assertEqual(integrations.get_user_display_name(self.make_plain_user("nobody")), "nobody")

    def test_nim_is_masked_for_donors(self):
        self.assertEqual(integrations.mask_nim("2506000001"), "2506 xxxx")
        self.assertEqual(integrations.get_recipient_label(self.recipient), "Rina Sari (2506 xxxx)")
        self.assertEqual(integrations.get_recipient_label(self.donor), "BEM Fasilkom UI")


class DonationAdapterTests(ClaimTestCase):
    """The adapter to the donasi module."""

    def test_get_donation_maps_the_fields(self):
        info = integrations.get_donation(self.donation.pk)
        self.assertEqual(info.id, self.donation.pk)
        self.assertEqual(info.food_name, "Nasi ayam")
        self.assertEqual(info.donor_name, "BEM Fasilkom UI")
        self.assertEqual(info.pickup_location, "Lobi Gedung A")
        self.assertEqual(info.available_portions, 10)
        self.assertEqual(info.owner_id, self.donor.pk)
        self.assertIsNotNone(info.pickup_start)
        self.assertIsNone(info.distance_km)

    def test_get_donation_returns_none_for_an_unknown_id(self):
        self.assertIsNone(integrations.get_donation(999999))

    def test_get_donation_with_a_lock(self):
        with transaction.atomic():
            info = integrations.get_donation(self.donation.pk, lock=True)
        self.assertEqual(info.id, self.donation.pk)

    def test_adjust_portions(self):
        with transaction.atomic():
            integrations.adjust_portions(self.donation.pk, -3)
        self.assertEqual(self.stock(), 7)
        with transaction.atomic():
            integrations.adjust_portions(self.donation.pk, 3)
        self.assertEqual(self.stock(), 10)

    def test_adjust_portions_ignores_a_deleted_donation(self):
        with transaction.atomic():
            integrations.adjust_portions(999999, 3)  # does not raise

    def test_donation_detail_url(self):
        self.assertEqual(
            integrations.get_donation_detail_url(self.donation.pk),
            reverse("donasi:detail", args=[self.donation.pk]),
        )
        self.assertIsNone(integrations.get_donation_detail_url(999999))
        self.assertEqual(integrations.get_donation_list_url(), reverse("donasi:daftar"))


@override_settings(STORAGES=PLAIN_STORAGES)
class ClaimButtonTagTests(ClaimTestCase):
    """The {% claim_button %} tag used by the donation pages."""

    def render(self, user):
        request = RequestFactory().get("/donasi/")
        request.user = user
        template = Template("{% load claim_extras %}{% claim_button item %}")
        return template.render(Context({"request": request, "item": self.donation})).strip()

@override_settings(STORAGES=PLAIN_STORAGES)
class VenueIntegrationTests(ClaimTestCase):
    """Distance and map link through the venue module (skipped if venue is not installed)."""

    def setUp(self):
        super().setUp()
        if not apps.is_installed("venue"):
            self.skipTest("venue app is not installed")
        from venue.models import Venue

        self.venue = Venue.objects.create(
            nama="Lobi Gedung A", fakultas="fasilkom",
            latitude=Decimal("-6.364500"), longitude=Decimal("106.828700"),
        )

    def render_card(self, show_route=True):
        template = Template(
            "{% load claim_extras %}{% claim_location_card name show_route %}"
        )
        return template.render(Context({"name": "Lobi Gedung A", "show_route": show_route}))

    def test_location_point_matches_the_venue_name_ignoring_case(self):
        point = integrations.get_location_point("lobi gedung a")
        self.assertEqual(point["lat"], "-6.364500")
        self.assertEqual(point["lng"], "106.828700")
        self.assertEqual(point["url"], reverse("venue:detail", args=[self.venue.pk]))

    def test_unknown_location_has_no_point(self):
        self.assertIsNone(integrations.get_location_point("Gedung Tidak Ada"))
        self.assertIsNone(integrations.get_location_point(""))
        self.assertIsNone(integrations.get_location_point(None))

    def test_campus_center_is_available(self):
        center = integrations.get_campus_center()
        self.assertIn("lat", center)
        self.assertIn("lng", center)

    def test_location_card_without_route_has_no_dropdown(self):
        html = self.render_card(show_route=False)
        self.assertIn("Lobi Gedung A", html)
        self.assertNotIn("data-distance-select", html)

    def test_location_card_for_an_unknown_venue_shows_a_dash(self):
        template = Template("{% load claim_extras %}{% claim_location_card name True %}")
        html = template.render(Context({"name": "Gedung Tidak Ada"}))
        self.assertNotIn("data-distance-select", html)
        self.assertIn("<dd>-</dd>", html)

 