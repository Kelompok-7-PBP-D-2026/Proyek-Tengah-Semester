import csv
from io import BytesIO, StringIO
from xml.sax.saxutils import escape

from django.utils import timezone


class PDFDependencyMissing(Exception):
    pass


def safe_csv(value):
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def export_rows(laporan):
    return [
        ("Judul", laporan.judul),
        ("Periode mulai", laporan.periode_mulai.isoformat()),
        ("Periode selesai", laporan.periode_selesai.isoformat()),
        ("Status", laporan.get_status_display()),
        ("Total makanan tersalurkan (porsi)", laporan.total_porsi if laporan.total_porsi is not None else "Belum tersedia"),
        ("Jumlah donor unik", laporan.jumlah_donor if laporan.jumlah_donor is not None else "Belum tersedia"),
        ("Jumlah penerima unik", laporan.jumlah_penerima if laporan.jumlah_penerima is not None else "Belum tersedia"),
        ("Dibuat oleh", laporan.dibuat_oleh.get_username()),
        ("Dihitung pada", timezone.localtime(laporan.dihitung_pada).isoformat() if laporan.dihitung_pada else "Belum dihitung"),
        ("Catatan", laporan.catatan or "Tidak ada catatan"),
    ]


def buat_csv(laporan):
    output = StringIO(newline="")
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["Keterangan", "Nilai"])
    for label, value in export_rows(laporan):
        writer.writerow([label, safe_csv(value)])
    return output.getvalue()


def buat_pdf(laporan):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    except ImportError as exc:
        raise PDFDependencyMissing from exc

    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=A4, rightMargin=22*mm, leftMargin=22*mm,
                            topMargin=22*mm, bottomMargin=22*mm, title=laporan.judul)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("Brand", parent=styles["Title"], textColor=colors.HexColor("#19532B"), alignment=0))
    styles.add(ParagraphStyle("Label", parent=styles["Normal"], fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=4))
    story = [Paragraph("MBG | Laporan Dampak", styles["Brand"]), Spacer(1, 5*mm)]
    if laporan.status == laporan.Status.DRAF:
        story.extend([Paragraph("DRAF - BELUM ADA HASIL PERHITUNGAN", styles["Heading2"]),
                      Paragraph("Angka dampak belum tersedia. Dokumen ini bukan bukti penyaluran makanan.", styles["BodyText"])])
    for label, value in export_rows(laporan):
        story.append(Paragraph(escape(label), styles["Label"]))
        story.append(Paragraph(escape(str(value)).replace("\n", "<br/>"), styles["BodyText"]))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        canvas.drawString(22*mm, 12*mm, "Makan Berlebih Gratis | Laporan Dampak")
        canvas.drawRightString(A4[0]-22*mm, 12*mm, f"Halaman {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()
