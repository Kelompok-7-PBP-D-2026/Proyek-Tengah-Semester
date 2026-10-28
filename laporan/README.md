# Modul 5 — Laporan Dampak

## Integrasi dan acuan desain

Modul tersedia langsung di `/laporan/` melalui konfigurasi utama aplikasi.
Menu Laporan pada navigasi admin dan footer terhubung ke dashboard; logo MBG
kembali ke beranda, dan tautan Venue, Daftar, serta Verifikasi memakai URL aplikasi.

Tampilan mengikuti file Figma `MT2ZypZ7HGnSp8RB2AaWKt`: 5A Daftar
(`102:1589`), 5B Buat (`102:1737`), 5C Detail (`102:1816`), 5D Edit
(`102:1935`), dan 5E Konfirmasi Hapus (`102:2012`). Warna, font,
kartu statistik, tabel, logo, dan ukuran konten mengikuti desain desktop;
layout menyesuaikan ponsel. Angka contoh desain tidak dimasukkan ke database.

## Aturan perhitungan

`LAPORAN_AGGREGATOR = "laporan.klaim_adapter.agregasi"` aktif secara default.
Provider membaca `klaim.Claim` tanpa mengubah klaim atau stok donasi:

- Hanya `status="picked_up"` dengan `picked_up_at` terisi yang dihitung.
- Periode memakai waktu pengambilan aktual dalam **Asia/Jakarta (WIB)**,
  mulai pukul 00:00:00 sampai 23:59:59.999999 pada tanggal akhir, inklusif.
  Waktu reservasi, pembuatan klaim, dan batas ambil bukan dasar periode.
- Porsi adalah jumlah `portions`; donor dan penerima dihitung dari ID akun unik.
  Orang yang menerima dari beberapa donor tetap dihitung satu kali pada total.
- Rincian donor berisi nama unit, jenis donor, porsi, serta penerima unik per donor.
  Akun tanpa profil memakai nama pada klaim atau username dan jenis belum
  diklasifikasikan. Akun berbeda dengan nama sama tetap donor berbeda.
- Klaim dengan donor yang dihapus digabung dalam baris "Donor dihapus".
  Porsi dan penerima tetap dihitung; identitas yang hilang tidak direka ulang
  dan tidak ditambahkan ke jumlah donor unik. Catatan ini muncul pada detail/ekspor.
- Periode tanpa klaim menghasilkan nol. Sumber gagal dihitung menampilkan
  kesalahan, bukan angka nol palsu.

Dashboard menghitung satu periode tahunan langsung dari klaim, bukan
menjumlahkan laporan yang mungkin memiliki periode tumpang tindih.

## Alur laporan

1. Admin aktif (`is_staff` atau `is_superuser`) memilih tanggal pada Buat Laporan.
   Judul kosong otomatis memakai periode. Pratinjau diperbarui lewat GET JSON
   `/laporan/pratinjau/`, tanpa menyimpan laporan. Tampilan awal tersedia tanpa JS.
2. Buat laporan menghitung ulang di server dan menyimpan total, jumlah klaim,
   rincian donor, pembuat, dan waktu perhitungan sebagai satu snapshot.
   Angka atau pembuat yang dikirim klien diabaikan.
3. Detail, CSV, dan PDF membaca snapshot yang sama. Perubahan sumber/profil
   setelahnya tidak diam-diam mengubah laporan tersimpan.
4. Perubahan tanggal atau tombol Hitung ulang menghitung snapshot baru.
   Perubahan judul/catatan saja mempertahankan snapshot. Kegagalan hitung
   membatalkan perubahan sehingga periode dan hasil lama tetap konsisten.
5. Hapus membutuhkan konfirmasi dan POST ber-CSRF. Escape membatalkan dialog.

Migrasi `0002` menambahkan kolom nullable tanpa mengubah laporan lama.
Laporan lama tanpa rincian tetap bisa dibuka/diekspor; tekan **Hitung dampak**
untuk mengisi rincian dari sumber terkini. Jika provider sengaja dinonaktifkan,
mode draf tetap tersedia, dengan angka belum tersedia (berbeda dari nol).

CSV melindungi teks dari formula injection; PDF/HTML meng-escape teks pengguna.
Ekspor menyertakan rincian donor dan catatan, dengan tabel PDF berulang judul
kolom saat melewati satu halaman. Tidak ada klaim kg/CO2e tanpa sumber data.

## Menjalankan aplikasi (PowerShell)

Dari folder utama proyek dengan virtual environment aktif:

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Gunakan akun admin yang sudah ada jika tersedia; `createsuperuser` hanya
perlu untuk membuat akun admin baru. Buka `http://127.0.0.1:8000/laporan/`.
Dependency PDF otomatis terpasang melalui requirements utama.

Modul memakai settings, URL, database, dan dependency utama proyek, sama seperti
modul donasi dan klaim. Tidak diperlukan settings atau database tambahan.

## Pengujian

```powershell
python manage.py test
python manage.py check
python manage.py makemigrations --check --dry-run
```

`tests.py` mempertahankan pengujian CRUD, otorisasi, CSRF, mode draf, dan ekspor.
`test_integrasi.py` menguji model Claim nyata, batas WIB, keunikan akun,
snapshot, pratinjau, rollback, rincian donor, navigasi utama, dan ekspor.
Tests memakai database sementara; provider palsu hanya untuk pengujian.

Batas data sumber tetap berlaku: `recipient` pada Claim menggunakan CASCADE.
Penghapusan akun penerima dapat menghapus klaim sumber untuk perhitungan
berikutnya; snapshot laporan yang sudah dibuat tetap tersimpan.

## Struktur kode

- `models.py`, `forms.py`, `views.py`, `urls.py`: model, formulir, dan alur halaman.
- `services.py`: validasi dan penyimpanan hasil perhitungan laporan.
- `klaim_adapter.py`: agregasi data Claim sesuai periode.
- `exports.py`: ekspor CSV dan PDF dari snapshot yang tersimpan.
- `permissions.py`: pembatasan akses pengelola.
- `tests.py`, `test_integrasi.py`: pengujian fitur dan integrasi Claim.
- `migrations/`, `templates/`, `static/`, `templatetags/`: skema database dan tampilan.

Nama kelas memakai PascalCase, fungsi memakai snake_case, dan nama domain
mengikuti istilah Indonesia yang digunakan proyek. Gunakan indentasi empat
spasi untuk Python dan dua spasi untuk HTML/CSS/JS. Dependency dipasang melalui
`requirements.txt` utama; tidak ada konfigurasi formatter khusus modul.
