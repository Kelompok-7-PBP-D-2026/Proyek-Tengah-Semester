from django.shortcuts import render

# Create your views here.

import logging
from datetime import date

from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .exports import buat_csv, buat_pdf, PDFDependencyMissing
from .forms import AdminLoginForm, FilterForm, LaporanForm
from .models import Laporan
from .permissions import admin_required
from .services import hitung_laporan, ringkasan_periode, sumber_terhubung, SumberDataBelumTersedia

logger = logging.getLogger(__name__)


class AdminLoginView(LoginView):
    template_name = "laporan/login.html"
    authentication_form = AdminLoginForm
    next_page = reverse_lazy("laporan:dashboard")


class AdminLogoutView(LogoutView):
    next_page = reverse_lazy("laporan:login")


def detail_context(laporan):
    return {"laporan": laporan, "sumber_terhubung": sumber_terhubung()}


@admin_required
@require_http_methods(["GET"])
def dashboard(request):
    year = timezone.localdate().year
    annual_impact = None
    if sumber_terhubung():
        try:
            annual_impact = ringkasan_periode(date(year, 1, 1), date(year, 12, 31))
        except (SumberDataBelumTersedia, ImportError, ValueError, TypeError):
            logger.warning("Ringkasan dampak tahunan belum tersedia", exc_info=True)
    laporan = Laporan.objects.select_related("dibuat_oleh")
    stats = laporan.aggregate(
        total=Count("pk"), draf=Count("pk", filter=Q(status=Laporan.Status.DRAF)),
        siap=Count("pk", filter=Q(status=Laporan.Status.SIAP)),
    )
    form = FilterForm(request.GET)
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
    return render(request, "laporan/dashboard.html", {
        "page_obj": page, "filter_form": form, "stats": stats,
        "filter_query": query.urlencode(), "sumber_terhubung": sumber_terhubung(),
        "annual_impact": annual_impact, "year": year,
    })


@admin_required
@require_http_methods(["GET", "POST"])
def buat(request):
    today = timezone.localdate()
    form = LaporanForm(request.POST if request.method == "POST" else None, initial={
        "periode_mulai": date(today.year, today.month, 1), "periode_selesai": today,
    })
    if request.method == "POST" and form.is_valid():
        laporan = form.save(commit=False)
        laporan.dibuat_oleh = request.user
        laporan.save()
        messages.success(request, "Draf laporan berhasil dibuat. Angka dampak belum dihitung.")
        return redirect(laporan)
    return render(request, "laporan/form.html", {"form": form, "editing": False, "sumber_terhubung": sumber_terhubung()})


@admin_required
@require_http_methods(["GET"])
def detail(request, pk):
    laporan = get_object_or_404(Laporan.objects.select_related("dibuat_oleh"), pk=pk)
    return render(request, "laporan/detail.html", detail_context(laporan))


@admin_required
@require_http_methods(["GET", "POST"])
def edit(request, pk):
    with transaction.atomic():
        laporan = get_object_or_404(Laporan.objects.select_for_update(), pk=pk)
        old_period = (laporan.periode_mulai, laporan.periode_selesai)
        form = LaporanForm(request.POST if request.method == "POST" else None, instance=laporan)
        if request.method == "POST" and form.is_valid():
            laporan = form.save(commit=False)
            changed = old_period != (laporan.periode_mulai, laporan.periode_selesai)
            if changed:
                laporan.reset_hasil()
            laporan.save()
            recalculated = False
            if request.POST.get("action") == "recalculate":
                try:
                    with transaction.atomic():
                        hitung_laporan(laporan)
                    recalculated = True
                except SumberDataBelumTersedia as exc:
                    messages.warning(request, str(exc))
                except (ImportError, ValueError, TypeError):
                    logger.exception("Perhitungan ulang laporan belum berhasil")
                    messages.error(request, "Perubahan tersimpan, tetapi perhitungan ulang belum berhasil.")
            messages.success(request, "Laporan diperbarui dan dihitung ulang." if recalculated else "Laporan diperbarui." + (
                " Periode berubah; hasil sebelumnya dihapus dan perlu dihitung ulang." if changed else ""
            ))
            return redirect(laporan)
    return render(request, "laporan/form.html", {"form": form, "editing": True, "laporan": laporan, "sumber_terhubung": sumber_terhubung()})


@admin_required
@require_http_methods(["GET", "POST"])
def hapus(request, pk):
    laporan = get_object_or_404(Laporan, pk=pk)
    if request.method == "POST":
        laporan.delete()
        messages.success(request, "Laporan berhasil dihapus.")
        return redirect("laporan:dashboard")
    return render(request, "laporan/hapus.html", {"laporan": laporan, "background_reports": Laporan.objects.all()[:2]})


@admin_required
@require_POST
def generate(request, pk):
    try:
        with transaction.atomic():
            laporan = get_object_or_404(Laporan.objects.select_for_update(), pk=pk)
            hitung_laporan(laporan)
    except SumberDataBelumTersedia as exc:
        messages.warning(request, str(exc))
    except (ImportError, ValueError, TypeError) as exc:
        logger.exception("Konfigurasi agregasi laporan tidak valid", exc_info=exc)
        messages.error(request, "Perhitungan belum berhasil. Hasil sebelumnya tetap tersimpan.")
    else:
        messages.success(request, "Angka dampak berhasil dihitung dan disimpan.")
    return redirect("laporan:detail", pk=pk)


@admin_required
@require_http_methods(["GET"])
def ekspor_csv(request, pk):
    laporan = get_object_or_404(Laporan.objects.select_related("dibuat_oleh"), pk=pk)
    response = HttpResponse(buat_csv(laporan), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="laporan-{laporan.pk}.csv"'
    return response


@admin_required
@require_http_methods(["GET"])
def ekspor_pdf(request, pk):
    laporan = get_object_or_404(Laporan.objects.select_related("dibuat_oleh"), pk=pk)
    try:
        content = buat_pdf(laporan)
    except PDFDependencyMissing:
        return render(request, "laporan/pdf_unavailable.html", {"laporan": laporan}, status=503)
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="laporan-{laporan.pk}.pdf"'
    return response
