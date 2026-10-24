# Audit validasi modul donasi — 24 Oktober 2026

Audit ini mencakup modul `donasi`. Perubahan audit hanya berada di dalam app ini,
termasuk migrasi pembatas stok dan migrasi `0003_pickup_end_and_automatic_stock_status`.
Modul anggota lain tidak diubah.

## Hasil dan perbaikan

| Bagian | Aturan / hasil audit |
| --- | --- |
| Urutan waktu | Mulai pengambilan harus lebih awal dari akhir pengambilan; nilai yang sama juga ditolak. Dilindungi validasi model dan constraint database. |
| Batas akhir | Donasi baru/aktif harus memiliki batas akhir di masa depan. Donasi lama yang sudah berakhir hanya boleh ditutup dengan 0 stok dan waktu akhir lama yang tidak diubah. |
| Waktu WIB | Parsing dan tampilan WIB tetap konsisten di form publik dan Django Admin, meskipun timezone project adalah UTC. |
| Stok | Donasi baru minimal 1 porsi, edit boleh 0 jika habis. Bilangan negatif, pecahan, teks, dan overflow ditolak. Batas atas 2.147.483.647 menjaga konsistensi dengan PostgreSQL. |
| Ketersediaan | Tidak ada input atau kolom status manual. Tersedia/Habis mengikuti stok secara otomatis, termasuk jika stok diperbarui langsung oleh modul klaim nanti. |
| Teks | Nama dan lokasi wajib diisi; spasi kosong ditolak; nama 140, lokasi 200, dan catatan 200 karakter. Spasi di tepi dibersihkan. |
| Foto | Opsional, JPEG/PNG maksimal 5 MB, file kosong/rusak ditolak. Hapus dan unggah foto bersamaan ditolak. Ekstensi penyimpanan mengikuti format gambar yang didekode, bukan nama unggahan. |
| Hak akses | Login dan role donor diperiksa di server; pemilik ditentukan dari akun yang login. URL edit/hapus milik donor lain tetap ditolak. |
| Sesi | JSON 401 untuk sesi AJAX yang berakhir; form tidak dialihkan otomatis dan isian tetap ada. Cookie CSRF baru dibaca saat kirim ulang setelah login di tab lain. |
| Hapus | GET hanya konfirmasi, POST + CSRF untuk menghapus. Relasi PROTECT menghasilkan 409. |
| Filter | Hari ini/besok/pekan ini memakai WIB dan irisan periode; batas tengah malam diuji. Donasi sendiri tetap terpisah antar akun. |
| Pesan error | Toast memuat pesan per kesalahan, tetap ada sampai ditutup, tidak menumpuk setelah submit berulang, serta diikuti penanda dan pesan pada kolom. |
| Error HTTP | Penanganan JSON maupun HTML untuk 400/401/403/404/405/409/413/429 dan error server; HTML error CSRF tidak lagi dianggap kegagalan parsing JSON biasa. |
| Gangguan koneksi | Tidak ada retry otomatis untuk mutasi; pengguna diminta memeriksa daftar sebelum mengirim ulang agar tidak menduplikasi data. |
| HTML pengguna | Template Django melakukan escaping; toast dan pesan field menggunakan textContent, bukan interpolasi HTML pengguna. |

Sesuai revisi, field batas waktu bernama `waktu_akhir_pengambilan` dan tidak
menyatakan kedaluwarsa makanan. Migrasi dari nama lama mempertahankan nilai batas
waktu dan stok; pengujian mencakup migrasi maju maupun balik.

## Pengecekan

- Suite pengujian diperbarui untuk form tanpa status, stok awal minimal 1,
  perhitungan ketersediaan otomatis, dan migrasi yang mempertahankan data.
- Hasil setelah revisi: 31 test project lulus (29 test donasi, termasuk migrasi),
  coverage Python modul donasi 99% dengan file test dan migrasi dikecualikan.
- Django system check dan pengecekan migrasi tidak menemukan masalah.
- Unit/integration tests Django: jalur valid dan invalid, database constraints,
  role/kepemilikan/CSRF, filter, foto, admin, dan seed.
- Coverage dihitung untuk kode Python `donasi`, dengan tests dan migrations dikecualikan.
- JavaScript diperiksa menggunakan `node --check`.
- Pengecekan browser menggunakan database dan akun sementara, tidak mengisi atau
  mengubah data lokal pengguna: toast urutan waktu, beberapa kesalahan sekaligus,
  simpan berhasil setelah perbaikan, serta logout/login di tab lain dan kirim ulang
  form tanpa kehilangan isian.

## Batas cakupan

- Relasi venue/Public API, profil, klaim, dan laporan masih mengikuti catatan
  integrasi di README. Stok bersamaan dan penghapusan dengan klaim nyata perlu
  diuji kembali ketika modul klaim tersedia.
- Pengujian utama dijalankan dengan SQLite lokal; PostgreSQL deployment belum
  dijalankan pada audit ini. Batas porsi sudah ditetapkan secara eksplisit untuk
  konsistensi tipe integer antar database.
- Pemulihan CSRF memakai cookie standar project. Jika autentikasi bersama nanti
  mengaktifkan CSRF cookie HttpOnly atau CSRF_USE_SESSIONS, mekanisme refresh token
  perlu disesuaikan; penolakan CSRF tetap menampilkan pesan yang dapat ditindaklanjuti.
- Jaringan/server yang terputus setelah menyimpan dapat membuat hasil tidak pasti.
  Pencegahan klik ganda di UI tersedia, tetapi idempotency key di server belum dibuat.

## Referensi

- [Validasi form Django 5.2](https://docs.djangoproject.com/en/5.2/ref/forms/validation/)
- [Toast Bootstrap 5.3](https://getbootstrap.com/docs/5.3/components/toasts/)
