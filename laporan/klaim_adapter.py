from datetime import datetime, time
from zoneinfo import ZoneInfo

from klaim.models import Claim, ClaimStatus
from profil.models import ProfilDonor

from .services import RingkasanDampak

REPORT_TIME_ZONE = ZoneInfo("Asia/Jakarta")


def agregasi(periode_mulai, periode_selesai):
    if periode_selesai < periode_mulai:
        raise ValueError("Tanggal akhir tidak boleh sebelum tanggal mulai.")
    start = datetime.combine(periode_mulai, time.min, tzinfo=REPORT_TIME_ZONE)
    end = datetime.combine(periode_selesai, time.max, tzinfo=REPORT_TIME_ZONE)
    claims = (
        Claim.objects.filter(
            status=ClaimStatus.PICKED_UP,
            picked_up_at__gte=start,
            picked_up_at__lte=end,
        )
        .order_by("pk")
        .values(
            "portions",
            "recipient_id",
            "donor_id",
            "donor_name",
            "donor__username",
            "donor__profil_donor__nama_unit",
            "donor__profil_donor__jenis",
        )
    )
    donor_types = dict(ProfilDonor._meta.get_field("jenis").choices)
    donors = {}
    recipients = set()
    total_portions = 0
    claim_count = 0
    for claim in claims.iterator():
        donor_id = claim["donor_id"]
        if donor_id not in donors:
            donors[donor_id] = {
                "donor_id": donor_id,
                "nama": (
                    claim["donor__profil_donor__nama_unit"]
                    or claim["donor_name"]
                    or claim["donor__username"]
                )
                if donor_id is not None
                else "Donor dihapus",
                "jenis": donor_types.get(
                    claim["donor__profil_donor__jenis"], "Belum diklasifikasikan"
                )
                if donor_id is not None
                else "Tidak tersedia",
                "total_porsi": 0,
                "penerima": set(),
            }
        donors[donor_id]["total_porsi"] += claim["portions"]
        donors[donor_id]["penerima"].add(claim["recipient_id"])
        recipients.add(claim["recipient_id"])
        total_portions += claim["portions"]
        claim_count += 1
    details = []
    for donor in donors.values():
        donor["jumlah_penerima"] = len(donor.pop("penerima"))
        details.append(donor)
    details.sort(key=lambda donor: (-donor["total_porsi"], donor["nama"].casefold()))
    return RingkasanDampak(
        total_porsi=total_portions,
        jumlah_donor=sum(donor_id is not None for donor_id in donors),
        jumlah_penerima=len(recipients),
        jumlah_klaim=claim_count,
        rincian_donor=details,
    )
