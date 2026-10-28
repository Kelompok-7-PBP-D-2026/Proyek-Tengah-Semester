# Modul 5 — Laporan Dampak

Modul ini membantu admin membuat laporan penyaluran makanan dari data klaim.
Tampilan mengacu ke [Figma Modul 5](https://www.figma.com/design/MT2ZypZ7HGnSp8RB2AaWKt/Untitled?node-id=101-91).

## Menjalankan

Dari folder yang berisi `manage.py`, dengan virtual environment aktif:

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Buka `http://127.0.0.1:8000/laporan/` dan masuk dengan akun admin aktif
(`is_staff` atau `is_superuser`). Jika belum ada, buat akun dengan
`python manage.py createsuperuser`.

Modul memakai settings, database, dan dependency utama proyek.

## Fitur utama

- Daftar laporan dengan pencarian, filter status, dan pagination.
- Buat laporan berdasarkan periode, dengan judul otomatis jika dikosongkan.
- Pratinjau total porsi, donor, dan penerima sebelum laporan disimpan.
- Detail laporan dengan rincian per donor dan catatan.
- Edit, hitung ulang, dan hapus laporan melalui konfirmasi.
- Unduh CSV atau PDF berisi hasil yang sama dengan detail laporan.

## Aturan perhitungan

- Sumbernya `klaim.Claim` berstatus `picked_up` dengan `picked_up_at` terisi.
  Periode mengikuti waktu pengambilan aktual dalam **WIB**, termasuk seluruh
  tanggal mulai dan selesai. Stok donasi tidak dipakai sebagai angka penyaluran.
- Total porsi dijumlahkan dari `portions`. Donor dan penerima dihitung berdasarkan
  akun unik; penerima yang mengambil dari beberapa donor tetap dihitung sekali
  pada total laporan. Rincian menghitung penerima unik untuk masing-masing donor.
- Dashboard menghitung dampak tahunan langsung dari klaim, sehingga laporan
  dengan periode tumpang tindih tidak membuat angka terhitung dua kali.
- Periode tanpa klaim menghasilkan **0**. Data belum tersedia ditampilkan **—**;
  kegagalan perhitungan tidak dianggap nol. Mode draf tersedia jika sumber
  sengaja dinonaktifkan melalui `LAPORAN_AGGREGATOR`.
- Hasil disimpan sebagai **snapshot** (salinan hasil saat dihitung). Perubahan
  sumber tidak otomatis mengubah laporan. Mengubah periode atau menekan tombol
  hitung memperbarui hasil; mengubah judul/catatan saja mempertahankannya.
  Jika perhitungan gagal, perubahan tidak disimpan dan hasil lama tetap aman.
- Klaim dari donor yang dihapus tetap masuk total porsi dan penerima, tetapi
  tidak dihitung sebagai donor unik. Penghapusan akun penerima dapat menghapus
  klaim sumber; laporan yang sudah tersimpan tetap utuh.

Untuk laporan lama yang belum memiliki rincian donor, klik **Hitung dampak**.

## Struktur penting

- `models.py`, `forms.py`, `views.py`, `urls.py`: data, formulir, dan halaman laporan.
- `klaim_adapter.py`, `services.py`: membaca Claim, menghitung, dan menyimpan hasil.
- `exports.py`, `permissions.py`: ekspor file dan pembatasan akses admin.
- `templates/`, `static/`, `templatetags/`: tampilan dan format angka/tanggal.

## Pengujian

```powershell
python manage.py test
python manage.py check
python manage.py makemigrations --check --dry-run
```

Tes laporan ada di `tests.py` dan `test_integrasi.py`, meliputi CRUD, hak akses,
CSRF, perhitungan Claim, pratinjau, snapshot, serta ekspor CSV/PDF.
Pengujian memakai database sementara.
