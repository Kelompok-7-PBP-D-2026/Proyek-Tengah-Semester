import csv
from io import BytesIO, StringIO
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from django.utils import timezone


class PDFDependencyMissing(Exception):
    pass


def safe_csv(value):
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(
        ("\t", "\r", "\n")
    ):
        return "'" + text
    return text


def export_rows(laporan):
    return [
        ("Judul", laporan.judul),
        ("Periode mulai", laporan.periode_mulai.isoformat()),
        ("Periode selesai", laporan.periode_selesai.isoformat()),
        ("Status", laporan.get_status_display()),
        (
            "Total makanan tersalurkan (porsi)",
            laporan.total_porsi
            if laporan.total_porsi is not None
            else "Belum tersedia",
        ),
        (
            "Jumlah donor unik",
            laporan.jumlah_donor
            if laporan.jumlah_donor is not None
            else "Belum tersedia",
        ),
        (
            "Jumlah penerima unik",
            laporan.jumlah_penerima
            if laporan.jumlah_penerima is not None
            else "Belum tersedia",
        ),
        ("Dibuat oleh", laporan.dibuat_oleh.get_username()),
        (
            "Dihitung pada",
            timezone.localtime(
                laporan.dihitung_pada, ZoneInfo("Asia/Jakarta")
            ).isoformat()
            if laporan.dihitung_pada
            else "Belum dihitung",
        ),
        ("Catatan", laporan.catatan or "Tidak ada catatan"),
        (
            "Klaim yang sudah diambil",
            laporan.jumlah_klaim
            if laporan.jumlah_klaim is not None
            else "Belum tersedia",
        ),
        (
            "Dasar periode",
            "Waktu pengambilan aktual (WIB), termasuk tanggal mulai dan selesai.",
        ),
    ]


def buat_csv(laporan):
    output = StringIO(newline="")
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["Keterangan", "Nilai"])
    for label, value in export_rows(laporan):
        writer.writerow([label, safe_csv(value)])
    if laporan.rincian_donor is not None:
        writer.writerow([])
        writer.writerow(["Donor", "Jenis donor", "Porsi", "Penerima unik"])
        for donor in laporan.rincian_donor:
            writer.writerow(
                [
                    safe_csv(donor[key])
                    for key in ("nama", "jenis", "total_porsi", "jumlah_penerima")
                ]
            )
        writer.writerow([])
        writer.writerow(
            [
                "Catatan penerima",
                "Penerima yang sama pada beberapa donor dihitung sekali dalam total laporan.",
            ]
        )
        if laporan.memiliki_donor_dihapus:
            writer.writerow(
                [
                    "Catatan donor",
                    "Akun donor yang dihapus tidak dihitung sebagai donor unik; porsi dan penerimanya tetap dihitung.",
                ]
            )
    return output.getvalue()


def buat_pdf(laporan):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            LongTable,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            TableStyle,
        )
    except ImportError as exc:
        raise PDFDependencyMissing from exc

    stream = BytesIO()
    doc = SimpleDocTemplate(
        stream,
        pagesize=A4,
        rightMargin=22 * mm,
        leftMargin=22 * mm,
        topMargin=22 * mm,
        bottomMargin=22 * mm,
        title=laporan.judul,
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "Brand",
            parent=styles["Title"],
            textColor=colors.HexColor("#19532B"),
            alignment=0,
        )
    )
    styles.add(
        ParagraphStyle(
            "Label",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            spaceBefore=12,
            spaceAfter=4,
        )
    )
    story = [Paragraph("MBG | Laporan Dampak", styles["Brand"]), Spacer(1, 5 * mm)]
    if laporan.status == laporan.Status.DRAF:
        story.extend(
            [
                Paragraph("DRAF - BELUM ADA HASIL PERHITUNGAN", styles["Heading2"]),
                Paragraph(
                    "Angka dampak belum tersedia. Dokumen ini bukan bukti penyaluran makanan.",
                    styles["BodyText"],
                ),
            ]
        )
    story.append(Paragraph(escape(laporan.judul), styles["Heading2"]))
    summary_rows = [
        [
            Paragraph(escape(label), styles["Normal"]),
            Paragraph(escape(str(value)), styles["Normal"]),
        ]
        for label, value in export_rows(laporan)
        if label not in ("Judul", "Catatan")
    ]
    summary = LongTable(
        summary_rows, colWidths=[doc.width * 0.43, doc.width * 0.57], hAlign="LEFT"
    )
    summary.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                (
                    "ROWBACKGROUNDS",
                    (0, 0),
                    (-1, -1),
                    [colors.HexColor("#FBF6E8"), colors.white],
                ),
            ]
        )
    )
    story.append(summary)

    if laporan.rincian_donor is not None:
        story.append(Paragraph("Rincian per donor", styles["Heading2"]))
        if laporan.rincian_donor:
            rows = [
                [
                    Paragraph(label, styles["Normal"])
                    for label in ("Donor", "Jenis donor", "Porsi", "Penerima")
                ]
            ]
            for donor in laporan.rincian_donor:
                rows.append(
                    [
                        Paragraph(escape(str(donor[key])), styles["Normal"])
                        for key in ("nama", "jenis", "total_porsi", "jumlah_penerima")
                    ]
                )
            table = LongTable(
                rows,
                colWidths=[doc.width * ratio for ratio in (0.4, 0.3, 0.15, 0.15)],
                repeatRows=1,
                hAlign="LEFT",
            )
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3E8CC")),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.white, colors.HexColor("#FBF6E8")],
                        ),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING", (0, 0), (-1, -1), 9),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#19532B")),
                    ]
                )
            )
            story.append(table)
            story.append(
                Paragraph(
                    "Penerima yang sama pada beberapa donor dihitung sekali dalam total laporan.",
                    styles["BodyText"],
                )
            )
        else:
            story.append(
                Paragraph(
                    "Belum ada klaim yang sudah diambil pada periode ini.",
                    styles["BodyText"],
                )
            )
        if laporan.memiliki_donor_dihapus:
            story.append(
                Paragraph(
                    "Akun donor yang dihapus tidak dihitung sebagai donor unik; porsi dan penerimanya tetap dihitung.",
                    styles["BodyText"],
                )
            )
    else:
        story.append(
            Paragraph(
                "Rincian per donor belum tersedia. Hitung dampak untuk mengambil data terbaru.",
                styles["BodyText"],
            )
        )
    story.append(Paragraph("Catatan", styles["Label"]))
    story.append(
        Paragraph(
            escape(laporan.catatan or "Tidak ada catatan").replace("\n", "<br/>"),
            styles["BodyText"],
        )
    )

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        canvas.drawString(22 * mm, 12 * mm, "Makan Berlebih Gratis | Laporan Dampak")
        canvas.drawRightString(A4[0] - 22 * mm, 12 * mm, f"Halaman {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()
