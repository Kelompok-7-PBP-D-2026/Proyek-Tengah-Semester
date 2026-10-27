# Modul 5 — Laporan Dampak

## Acuan tampilan Figma

Tampilan mengikuti halaman `Modul 5 - Laporan Dampak` pada file
`MT2ZypZ7HGnSp8RB2AaWKt`: 5A Daftar (`102:1589`), 5B Buat (`102:1737`),
5C Detail (`102:1816`), 5D Edit (`102:1935`), dan 5E Konfirmasi Hapus (`102:2012`).
Navbar 73px, konten lebar 1024px, form 824px, font Inter/Poppins/Fredoka,
warna, kartu, tabel, logo dan ikon asli, serta footer mengikuti desain tersebut.
Perilaku responsif ditambahkan untuk ponsel karena frame rujukan berukuran desktop.

Data contoh Figma tidak dimasukkan ke database pengguna. Statistik tahunan memakai
provider untuk satu periode tahunan, bukan penjumlahan laporan yang bisa tumpang
tindih. Tanpa provider, statistik dan pratinjau tetap `—`. Tabel rincian donor
masih menampilkan status belum tersedia sampai kontrak data Klaim mendukungnya.
Judul form opsional dan otomatis memakai periode. Tombol hitung ulang pada edit
memakai periode form yang sudah divalidasi; tombol nonaktif saat sumber belum ada.
Pencarian, informasi tambahan, dan akses keluar tetap tersedia melalui bagian
yang dapat dibuka. Konfirmasi hapus memakai dialog dengan fokus keyboard dan Escape.
Tautan fitur anggota lain yang belum tersedia ditandai nonaktif.

Semua kode modul ini berada di `laporan/`. App lain, konfigurasi URL utama,
template bersama, dan database utama tidak perlu diubah untuk mencoba modul.

## Yang sudah tersedia

- Model laporan tersimpan: judul, periode inklusif awal–akhir, catatan, pembuat,
  status, total porsi, jumlah donor/penerima unik, dan waktu perhitungan.
- CRUD draf dengan validasi periode, daftar berpaginasi, pencarian, dan filter status.
- Akses hanya untuk akun aktif dengan `is_staff` atau `is_superuser`. Login saja
  tidak cukup. Seluruh pengelola memiliki akses laporan tingkat kampus.
- Dashboard dampak tahunan dari sumber data, dengan jumlah arsip dan filter status.
  Tidak menjumlahkan dampak antar laporan karena periodenya bisa tumpang tindih.
- PDF dan tabel CSV dari satu laporan tersimpan. Draf diberi penanda jelas;
  nilai `NULL` ditampilkan sebagai “belum tersedia”, bukan nol.
- Perubahan periode menghapus hasil hitungan lama; perubahan catatan/judul saja
  mempertahankan hasil. Admin Django hanya menyediakan tampilan baca agar
  perubahan tidak melewati alur validasi tersebut.
- CSRF untuk mutasi, hapus melalui POST, escaping HTML/PDF, dan perlindungan
  formula injection pada CSV.

## Menjalankan modul secara terpisah (PowerShell)

Jalankan dari folder utama `Proyek-Tengah-Semester`, menggunakan virtual
environment proyek yang sudah berisi requirements utama:

```powershell
.\.venv\Scripts\python.exe -m pip install -r laporan\requirements.txt
.\.venv\Scripts\python.exe manage.py migrate --settings=laporan.local_settings
.\.venv\Scripts\python.exe manage.py createsuperuser --settings=laporan.local_settings
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8001 --settings=laporan.local_settings
```

Buka `http://127.0.0.1:8001/laporan/`. Buat akun lokal sendiri melalui perintah
`createsuperuser`; tidak ada akun atau kata sandi bawaan.

Settings lokal memakai database terpisah `laporan/.local.sqlite3` yang diabaikan
Git. Akun/data dari `db.sqlite3` utama tidak otomatis muncul. File settings ini
hanya untuk pengembangan, bukan deployment. URL utama proyek tetap utuh;
perintah runserver biasa belum memasang `/laporan/`.

## Pengujian

```powershell
.\.venv\Scripts\python.exe manage.py test laporan --settings=laporan.local_settings
.\.venv\Scripts\python.exe manage.py check --settings=laporan.local_settings
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --settings=laporan.local_settings
```

Tests menggunakan database sementara. Provider palsu pada `tests.py` hanya
untuk menguji kontrak integrasi; jangan dipasang dalam settings aplikasi nyata.

## Batas saat ini dan kontrak integrasi Klaim

Belum ada model Klaim nyata di checkout saat implementasi. Karena itu belum
ada query agregasi produksi: tombol hitung nonaktif secara default dan endpoint
tetap menolak perhitungan tanpa sumber data. CRUD dan ekspor draf sudah berfungsi.
Jangan menyamakan stok `Donasi.jumlah_porsi` dengan jumlah makanan tersalurkan.

Setelah skema Klaim disepakati, buat provider di dalam modul laporan, misalnya
`laporan.klaim_adapter.agregasi`, lalu konfigurasikan `LAPORAN_AGGREGATOR` ke
path tersebut. Provider menerima `(periode_mulai, periode_selesai)` berupa
`datetime.date` dan mengembalikan `laporan.services.RingkasanDampak`:

```python
RingkasanDampak(total_porsi=..., jumlah_donor=..., jumlah_penerima=...)
```

Provider harus menghitung porsi dari klaim yang benar-benar diambil, memakai
waktu pengambilan pada periode inklusif dalam zona waktu kampus, mengecualikan
pending/batal, dan menghitung donor/penerima unik. Tidak ada data dalam periode
yang valid berarti tiga angka nol. Sumber belum tersedia harus melempar
`SumberDataBelumTersedia`, bukan mengembalikan nol. Provider tidak boleh
memutasi data klaim/donasi. Angka yang lolos validasi disimpan sebagai snapshot.

Perlu kesepakatan kelompok: nama model/field Klaim, status selesai, timestamp
serah-terima, relasi penerima/donor, serta pemetaan akun unit kampus ke role admin.
Model laporan tidak mengimpor model Klaim sehingga migrasi tidak bergantung padanya.
Metrik kg, CO2e, dan rincian fakultas belum dibuat tanpa sumber data yang sah.

## Integrasi proyek bersama nanti

Setelah integrasi disetujui, tambahkan satu route
`path("laporan/", include("laporan.urls"))` ke URL utama dan dependency dari
`laporan/requirements.txt` ke proses instalasi. App sudah tercantum dalam
`INSTALLED_APPS`. Terapkan migrasi laporan pada database tujuan dan pasang
tautan navigasi sesuai kesepakatan desain. Perubahan tersebut tidak dilakukan
oleh implementasi mandiri ini.
