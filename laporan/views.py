import logging
from datetime import date

from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from .exports import PDFDependencyMissing, buat_csv, buat_pdf
from .forms import AdminLoginForm, FilterLaporanForm, LaporanForm, PeriodeLaporanForm
from .klaim_adapter import REPORT_TIME_ZONE
from .models import Laporan
from .permissions import admin_required
from .services import (
    SumberDataBelumTersedia,
    hitung_laporan,
    ringkasan_periode,
    sumber_terhubung,
)

logger = logging.getLogger(__name__)
AGGREGATION_ERRORS = (
    SumberDataBelumTersedia,
    ImportError,
    ValueError,
    TypeError,
    ValidationError,
    DatabaseError,
)


class AdminLoginView(LoginView):
    template_name = "laporan/login.html"
    authentication_form = AdminLoginForm
    next_page = reverse_lazy("laporan:dashboard")


class AdminLogoutView(LogoutView):
    next_page = reverse_lazy("laporan:login")


def _detail_context(laporan):
    return {"laporan": laporan, "sumber_terhubung": sumber_terhubung()}


@admin_required
@require_http_methods(["GET"])
def dashboard_laporan(request):
    year = timezone.localdate(timezone=REPORT_TIME_ZONE).year
    annual_impact = None
    if sumber_terhubung():
        try:
            annual_impact = ringkasan_periode(date(year, 1, 1), date(year, 12, 31))
        except AGGREGATION_ERRORS:
            logger.warning("Ringkasan dampak tahunan belum tersedia", exc_info=True)
    laporan = Laporan.objects.select_related("dibuat_oleh")
    stats = laporan.aggregate(
        total=Count("pk"),
        draf=Count("pk", filter=Q(status=Laporan.Status.DRAF)),
        siap=Count("pk", filter=Q(status=Laporan.Status.SIAP)),
    )
    form = FilterLaporanForm(request.GET)
    if form.is_valid():
        if form.cleaned_data["q"]:
            laporan = laporan.filter(judul__icontains=form.cleaned_data["q"])
        if form.cleaned_data["status"]:
            laporan = laporan.filter(status=form.cleaned_data["status"])
    else:
        laporan = laporan.none()
    page = Paginator(laporan, 10).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(
        request,
        "laporan/dashboard.html",
        {
            "page_obj": page,
            "filter_form": form,
            "stats": stats,
            "filter_query": query.urlencode(),
            "sumber_terhubung": sumber_terhubung(),
            "annual_impact": annual_impact,
            "year": year,
        },
    )


@admin_required
@require_http_methods(["GET", "POST"])
def buat_laporan(request):
    today = timezone.localdate(timezone=REPORT_TIME_ZONE)
    form = LaporanForm(
        request.POST if request.method == "POST" else None,
        initial={
            "periode_mulai": date(today.year, today.month, 1),
            "periode_selesai": today,
        },
    )
    if request.method == "POST" and form.is_valid():
        laporan = form.save(commit=False)
        laporan.dibuat_oleh = request.user
        try:
            with transaction.atomic():
                if sumber_terhubung():
                    hitung_laporan(laporan)
                else:
                    laporan.save()
        except AGGREGATION_ERRORS:
            logger.exception("Pembuatan laporan belum berhasil")
            form.add_error(
                None,
                "Data klaim belum dapat dihitung. Laporan belum disimpan; silakan coba lagi.",
            )
        else:
            messages.success(
                request,
                "Laporan berhasil dibuat dan dihitung."
                if sumber_terhubung()
                else "Draf laporan berhasil dibuat. Angka dampak belum dihitung.",
            )
            return redirect(laporan)
    period = PeriodeLaporanForm(
        {
            "periode_mulai": form["periode_mulai"].value(),
            "periode_selesai": form["periode_selesai"].value(),
        }
    )
    preview = None
    if sumber_terhubung() and period.is_valid():
        try:
            preview = ringkasan_periode(**period.cleaned_data)
        except AGGREGATION_ERRORS:
            logger.warning("Pratinjau awal belum tersedia", exc_info=True)
    return render(
        request,
        "laporan/form.html",
        {
            "form": form,
            "editing": False,
            "sumber_terhubung": sumber_terhubung(),
            "preview_impact": preview,
        },
    )


@admin_required
@require_http_methods(["GET"])
@never_cache
def pratinjau_laporan(request):
    form = PeriodeLaporanForm(request.GET)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
    try:
        result = ringkasan_periode(**form.cleaned_data)
    except AGGREGATION_ERRORS:
        logger.warning("Pratinjau laporan belum tersedia", exc_info=True)
        return JsonResponse(
            {"error": "Pratinjau belum tersedia. Silakan coba lagi."}, status=503
        )
    return JsonResponse(
        {
            "total_porsi": result.total_porsi,
            "jumlah_donor": result.jumlah_donor,
            "jumlah_penerima": result.jumlah_penerima,
            "jumlah_klaim": result.jumlah_klaim,
        }
    )


@admin_required
@require_http_methods(["GET"])
def detail_laporan(request, pk):
    laporan = get_object_or_404(Laporan.objects.select_related("dibuat_oleh"), pk=pk)
    return render(request, "laporan/detail.html", _detail_context(laporan))


@admin_required
@require_http_methods(["GET", "POST"])
def edit_laporan(request, pk):
    with transaction.atomic():
        laporan = get_object_or_404(Laporan.objects.select_for_update(), pk=pk)
        old_period = (laporan.periode_mulai, laporan.periode_selesai)
        form = LaporanForm(
            request.POST if request.method == "POST" else None, instance=laporan
        )
        if request.method == "POST" and form.is_valid():
            laporan = form.save(commit=False)
            changed = old_period != (laporan.periode_mulai, laporan.periode_selesai)
            recalculate = changed or request.POST.get("action") == "recalculate"
            try:
                with transaction.atomic():
                    if recalculate and sumber_terhubung():
                        hitung_laporan(laporan)
                    else:
                        if changed:
                            laporan.reset_hasil()
                        laporan.save()
            except AGGREGATION_ERRORS:
                logger.exception("Pembaruan laporan belum berhasil")
                form.add_error(
                    None,
                    "Perhitungan belum berhasil. Perubahan belum disimpan dan hasil sebelumnya tetap tersimpan.",
                )
            else:
                if recalculate and not sumber_terhubung():
                    messages.warning(
                        request,
                        "Data Klaim belum terhubung. Hasil periode baru belum tersedia.",
                    )
                messages.success(
                    request,
                    "Laporan diperbarui dan dihitung ulang."
                    if recalculate and sumber_terhubung()
                    else "Laporan diperbarui.",
                )
                return redirect(laporan)
    return render(
        request,
        "laporan/form.html",
        {
            "form": form,
            "editing": True,
            "laporan": laporan,
            "sumber_terhubung": sumber_terhubung(),
        },
    )


@admin_required
@require_http_methods(["GET", "POST"])
def hapus_laporan(request, pk):
    laporan = get_object_or_404(Laporan, pk=pk)
    if request.method == "POST":
        laporan.delete()
        messages.success(request, "Laporan berhasil dihapus.")
        return redirect("laporan:dashboard")
    return render(
        request,
        "laporan/hapus.html",
        {"laporan": laporan, "background_reports": Laporan.objects.all()[:2]},
    )


@admin_required
@require_POST
def hitung_ulang_laporan(request, pk):
    try:
        with transaction.atomic():
            laporan = get_object_or_404(Laporan.objects.select_for_update(), pk=pk)
            hitung_laporan(laporan)
    except SumberDataBelumTersedia as exc:
        messages.warning(request, str(exc))
    except AGGREGATION_ERRORS as exc:
        logger.exception("Konfigurasi agregasi laporan tidak valid", exc_info=exc)
        messages.error(
            request, "Perhitungan belum berhasil. Hasil sebelumnya tetap tersimpan."
        )
    else:
        messages.success(request, "Angka dampak berhasil dihitung dan disimpan.")
    return redirect("laporan:detail", pk=pk)


@admin_required
@require_http_methods(["GET"])
def ekspor_laporan_csv(request, pk):
    laporan = get_object_or_404(Laporan.objects.select_related("dibuat_oleh"), pk=pk)
    response = HttpResponse(buat_csv(laporan), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="laporan-{laporan.pk}.csv"'
    return response


@admin_required
@require_http_methods(["GET"])
def ekspor_laporan_pdf(request, pk):
    laporan = get_object_or_404(Laporan.objects.select_related("dibuat_oleh"), pk=pk)
    try:
        content = buat_pdf(laporan)
    except PDFDependencyMissing:
        return render(
            request, "laporan/pdf_unavailable.html", {"laporan": laporan}, status=503
        )
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="laporan-{laporan.pk}.pdf"'
    return response
