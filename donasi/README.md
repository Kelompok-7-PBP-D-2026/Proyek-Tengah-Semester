# Modul Donasi Makanan — Rindu Maharani Nadhirah

Modul donasi MBG memakai Django MVT, Bootstrap 5, dan JavaScript `fetch`.
Desain mengacu ke [Figma Modul 2](https://www.figma.com/design/MT2ZypZ7HGnSp8RB2AaWKt/Untitled?node-id=94-90).

## Menjalankan

Di direktori yang berisi `manage.py`, gunakan Python dari virtual environment:

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Buka `http://127.0.0.1:8000/donasi/` dan masuk menggunakan akun yang dibuat.
Superuser dapat mencoba fitur donor, tetapi tombol edit/hapus pada halaman donasi
tetap hanya berlaku untuk donasi miliknya sendiri.

Untuk akun biasa, buat melalui Django Admin (`/admin/`), lalu beri akses donor
dengan membuat profil donor:

```powershell
python manage.py grant_donor username_akun
```

Perintah ini membuat `ProfilDonor` untuk akun yang sudah ada dan tidak membuat akun
atau kata sandi baru. Akun yang mendaftar sendiri lewat `/daftar/` sebagai donor
otomatis punya profil donor. Akun tanpa profil donor dapat membaca donasi, tetapi
tidak dapat mengelolanya.

## Data contoh

```powershell
python manage.py seed_donasi --donor username_akun --count 50
```

Data dibuat di database, berlabel `[Contoh NN]`, dengan catatan bahwa datanya
sintetis. Menjalankan perintah yang sama kembali tidak menduplikasi atau mengubah
data sebelumnya. Waktu contoh dihitung saat pertama kali dibuat; donasi yang sudah
pengambilannya sudah berakhir tetap terlihat lewat filter **Donasi saya**. Tidak ada akun, kata sandi,
atau data contoh yang otomatis dibuat saat aplikasi dijalankan.

## Fitur dan aturan

- Daftar dan detail publik; identitas donor hanya ditampilkan setelah login.
- CRUD melalui HTML form, dengan `fetch` untuk simpan/hapus dan respons JSON.
- Pemilik ditentukan dari `request.user`, tidak menerima donor dari input pengguna.
- Donor hanya boleh mengedit/menghapus donasinya sendiri, termasuk lewat URL langsung.
- Hapus membutuhkan POST dan CSRF. GET hanya menampilkan konfirmasi.
- Pencarian nama, filter lokasi, status, waktu, dan donasi sendiri; pagination 6 per halaman.
- AJAX filter memperbarui URL, mendukung pagination dan tombol Back/Forward browser.
- Hari ini/besok/pekan ini menggunakan WIB, menghitung irisan waktu ketersediaan
  dengan periode filter. Pekan ini berakhir pada Senin berikutnya pukul 00.00 WIB.
- Donasi yang pengambilannya selesai disembunyikan dari daftar publik, tetapi
  pemilik masih bisa melihatnya lewat Donasi saya.
- Donor cukup mengisi stok (`jumlah_porsi`), tanpa memilih status. Donasi baru
  wajib memiliki stok minimal 1 porsi; pada edit, 0 berarti stok sudah habis.
  Stok harus bulat dan tidak melebihi 2.147.483.647 (batas portable database).
- Label Tersedia/Habis dihitung langsung dari stok; tidak ada field status yang
  perlu disimpan atau diubah manual. Label Pengambilan selesai dihitung dari waktu.
- `waktu_akhir_pengambilan` adalah batas terakhir makanan bisa diambil, bukan
  tanggal kedaluwarsa makanan. Harus setelah `waktu_tersedia` dan di masa depan
  untuk donasi aktif. Pemilik boleh menutup donasi lama dengan 0 stok tanpa
  mengubah waktu akhirnya. Waktu mulai boleh sudah lewat jika makanan sudah tersedia.
- Migrasi 0003 mengganti nama kolom batas waktu dengan mempertahankan nilainya,
  dan menghapus kolom status manual. Pengujian migrasi memverifikasi stok dan
  batas waktu tetap sama, termasuk saat migrasi dibalik.
- Validasi form juga dipakai di Django Admin, termasuk interpretasi waktu WIB.
- Foto opsional, tervalidasi Pillow, hanya JPEG/PNG maksimal 5 MB, nama file dibuat acak.
  Foto dapat diganti atau dihapus dari form edit.
- Pemeriksaan urutan waktu juga dilindungi constraint database.
- Kesalahan form ditampilkan melalui toast Bootstrap dan pesan di bawah kolom.
  Toast error tetap tampil sampai ditutup, memperbarui pesan tanpa menumpuk, dan
  menjaga isian form. Pesan berasal dari server dan dimasukkan ke DOM sebagai teks.
- Sesi AJAX yang berakhir mendapat respons JSON 401, dengan tautan masuk di tab
  baru. Setelah login ulang, JavaScript memakai cookie CSRF terkini agar form lama
  bisa dikirim tanpa kehilangan isian (konfigurasi cookie standar project).
- Respons HTML untuk error CSRF/akses, data tak ditemukan, konflik penghapusan,
  unggahan terlalu besar, dan kegagalan server ditangani dengan pesan yang sesuai.
- Jika permintaan terputus, pengguna diminta memeriksa daftar sebelum mengirim
  ulang; aplikasi tidak mengulangi operasi simpan/hapus secara otomatis.

## Endpoint

| URL | Metode | Fungsi |
| --- | --- | --- |
| `/donasi/` | GET | Daftar HTML; `Accept: application/json` memberikan fragment HTML untuk AJAX |
| `/donasi/api/` | GET | Data JSON berpaginasi untuk konsumsi klien |
| `/donasi/<id>/` | GET | Detail HTML atau JSON berdasarkan header Accept |
| `/donasi/buat/` | GET, POST | Form dan simpan donasi baru |
| `/donasi/<id>/edit/` | GET, POST | Form dan simpan perubahan milik sendiri |
| `/donasi/<id>/hapus/` | GET, POST | Konfirmasi dan hapus milik sendiri |
| `/donasi/<id>/foto/` | GET | File foto, termasuk saat DEBUG=False |
| `/donasi/masuk/` | GET, POST | Login bawaan Django; halaman utama memakai `/akun/login/` |
| `/donasi/keluar/` | POST | Logout; navbar memakai `/akun/logout/` |

Parameter filter: `q`, `lokasi`, `waktu` (`hari_ini`, `besok`, `pekan_ini`),
`status` (`tersedia`, `habis`, dihitung dari stok), `mine=1`, dan `page`.
Respons waktu akhir menggunakan key `waktu_akhir_pengambilan`.
Nama donor tidak disertakan dalam JSON untuk pengguna anonim. Endpoint JSON ini
adalah API internal aplikasi, **bukan pengganti kewajiban Public API eksternal**.

## Integrasi kelompok yang masih perlu disambungkan

Navbar khusus halaman donasi menampilkan **Klaim masuk, Donasi saya** untuk donor
dan **Cari makanan, Klaim saya** untuk penerima. Menu klaim masih ditandai Segera
dan tidak dapat diklik selama route modul klaim belum tersedia di checkout.
Setelah modul tersebut digabung, isi `CLAIMS_VIEW_NAMES` di `donasi/navigation.py`
dengan nama URL namespaced yang benar untuk masing-masing role. Tidak perlu
mengubah template bersama atau app klaim untuk menghubungkan menu donasi ini.
Navbar halaman modul lain tetap dikelola anggota terkait.

Semua kartu menyediakan tombol **Lihat detail**. Pemilik donor mendapat tombol
ikon pensil tambahan dengan label aksesibel dan title **Edit donasi**.

Model profil, venue, dan klaim belum tersedia saat implementasi modul ini.
Implementasi sementara sengaja tidak menambahkan model ke app milik anggota lain.

1. **Profil (Fikri):** sudah tersambung. Donor berelasi ke `settings.AUTH_USER_MODEL`
   melalui `Donasi.donor` (`related_name='donasi'`), dan adapter role di
   `donasi/permissions.py` memakai `ProfilDonor` (plus superuser aktif) sebagai
   penentu akses donor. Login/logout, tautan profil di navbar dan footer, serta
   halaman detail memakai autentikasi bersama `/akun/` dari `django.contrib.auth`.
   Rute `/donasi/masuk/` dan `/donasi/keluar/` tetap ada demi kompatibilitas.
   Tidak perlu membuat akun donor kedua.
2. **Venue (Marvin):** `lokasi` saat ini teks maksimal 200 karakter. Setelah model
   venue disepakati, buat relasi ForeignKey dan migrasi data teks yang sudah ada;
   sesuaikan form dan filter. Public API OpenStreetMap, data venue dari API,
   dan perhitungan jarak belum diimplementasikan oleh modul ini. Filter lokasi
   sekarang hanya memfilter data donasi di database; ketentuan filter data Public
   API perlu diverifikasi kembali setelah integrasi venue.
3. **Klaim (Kireina):** referensikan `donasi.Donasi` dari model klaim. Sepakati makna
   `jumlah_porsi` adalah stok saat ini yang dicatat donor, belum terhubung ke
   reservasi. Pengurangan stok harus atomik
   untuk menghindari klaim berlebih. Statistik diklaim/diambil dan tombol klaim
   belum ditampilkan sampai data dan route klaim tersedia.
4. **Penghapusan dengan klaim:** gunakan kebijakan relasi yang disepakati kelompok.
   Jika ForeignKey klaim memakai `PROTECT`, modul ini mengembalikan 409 dengan
   pesan yang jelas; belum ada pembatalan klaim otomatis. Jangan memakai CASCADE
   tanpa memutuskan dampaknya ke riwayat dan laporan.
5. **Laporan (Joshua):** agregasi laporan sebaiknya menggunakan data klaim/serah
   terima yang sebenarnya. Jangan menyamakan jumlah porsi yang dicatat dengan
   makanan yang sudah tersalurkan.

## Penyimpanan foto dan deployment

`media/` diabaikan Git. `MEDIA_ROOT` dapat diatur lewat environment untuk menunjuk
volume persisten di deployment. Pastikan lokasi tersebut tetap tersimpan antar
restart/deploy; WhiteNoise hanya melayani aset statis, bukan unggahan pengguna.
Route foto modul ini membaca file melalui Django storage. Untuk skala lebih besar,
gunakan storage objek/media server sesuai kesepakatan kelompok.

Setelah menggabungkan branch, terapkan migrasi dan jalankan collectstatic saat
deployment. Jangan commit `.env`, database lokal, unggahan, atau direktori `env/`.

## Pengecekan

```powershell
python -m pip install -r requirements-dev.txt
python manage.py check
python manage.py makemigrations --check --dry-run
python -m coverage run --source=donasi --omit="donasi/test*.py,donasi/migrations/*" manage.py test
python -m coverage report -m
```

Test menggunakan database dan direktori foto sementara. Pengujian mencakup CRUD,
role dan kepemilikan, CSRF, validasi porsi dan waktu, konsistensi WIB, filter,
pagination, foto, autentikasi, penanganan relasi terproteksi, dan seed idempoten.

Hasil audit tambahan dan batas cakupannya tersedia di [AUDIT.md](AUDIT.md).
