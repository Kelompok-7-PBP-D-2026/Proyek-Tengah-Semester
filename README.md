# Platform Pendistribusian Surplus Makanan Acara Kampus

## Deskripsi Aplikasi

Aplikasi ini merupakan sebuah platform web yang menghubungkan penyelenggara acara kampus
seperti BEM, himpunan, UKM, dan panitia seminar dengan mitra katering serta kantin kampus
yang memiliki makanan surplus. Makanan surplus tersebut kemudian disalurkan secara gratis
kepada mahasiswa atau komunitas penerima di lingkungan kampus.

Aplikasi ini dibuat karena banyak acara kampus menyisakan makanan yang berujung menjadi
limbah, sementara ada mahasiswa yang membutuhkan. Selain mengurangi limbah makanan,
platform ini juga membantu unit kampus dalam menyusun laporan dampak keberlanjutan yang
dapat digunakan untuk kebutuhan pelaporan SDG, akreditasi, maupun UI GreenMetric.

Manfaat aplikasi ini bagi masyarakat antara lain:

1. Makanan surplus acara kampus tersalurkan kepada mahasiswa yang membutuhkan sehingga
   mengurangi jumlah limbah makanan.
2. Penyelenggara acara mendapatkan catatan dampak donasi secara otomatis, mulai dari
   total makanan yang diselamatkan hingga jumlah penerima yang terbantu.
3. Unit kampus memperoleh laporan bulanan yang siap dipakai sebagai bahan laporan
   SDG 2 (Zero Hunger) dan SDG 12 (Responsible Consumption and Production).

## Anggota Kelompok

| Nama | NPM |
| --- | --- |
| Joshua Imanuel Setiawan | 2506656854 |
| Kireina Naura Alifa | 2506590006 |
| Immanuel Marvin Pandjaitan | 2506623881 |
| Fikri Okto Setiadi | 2506621655 |
| Rindu Maharani Nadhirah | 2506587131 |

## Modul dan Pembagian Kerja

| No | Modul | Deskripsi | PIC |
| --- | --- | --- | --- |
| 1 | Profil Pengguna | Model profil donor (panitia acara, kantin, katering) dan profil penerima (mahasiswa). Melengkapi data saat registrasi, melihat dan mengedit profil sendiri, serta filter daftar donor berdasarkan jenis donor. | Fikri Okto Setiadi |
| 2 | Donasi Makanan | Model item makanan surplus berisi nama, jumlah porsi, waktu tersedia, waktu kedaluwarsa, lokasi, dan status. Donor dapat membuat, melihat, mengedit, dan menghapus donasi, serta memfilter donasi berdasarkan lokasi dan waktu. | Rindu Maharani Nadhirah |
| 3 | Klaim dan Reservasi | Model klaim yang berelasi dengan item makanan dan penerima. Penerima dapat membuat klaim, melihat status klaim, dan membatalkannya, sedangkan donor dapat menghapus klaim yang tidak diambil. Hanya penerima yang sudah login yang dapat melihat dan membuat klaim. | Kireina Naura Alifa |
| 4 | Venue dan Lokasi | Model titik pengambilan berisi nama gedung, fakultas, koordinat, dan deskripsi akses. Admin dan donor dapat mengelola venue, dengan integrasi OpenStreetMap untuk menampilkan peta dan menghitung jarak ke lokasi pengguna. | Immanuel Marvin Pandjaitan |
| 5 | Laporan Dampak | Model laporan berisi periode, total makanan tersalurkan, dan jumlah donor serta penerima yang terlibat. Admin dapat membuat laporan dari agregasi data klaim, mengedit, menghapus, dan mengunduh laporan dalam bentuk PDF atau tabel. | Joshua Imanuel Setiawan |

## Dokumentasi Modul dan Penggunaan AI

Penjelasan teknis dan AI disclosure ditulis pada README setiap modul. Dokumentasi
ini mencakup tujuan penggunaan AI, contoh prompt, hasil yang digunakan, serta
peninjauan dan perbaikan manual oleh pengembang.

- [Donasi Makanan](donasi/README.md)
- [Klaim dan Reservasi](klaim/README.md)
- [Venue dan Lokasi](venue/README.md)
- [Laporan Dampak](laporan/README.md)

README untuk modul Profil Pengguna akan ditambahkan oleh PIC modul tersebut.

## Public API yang Digunakan

Implementasi dan cara mencoba modul Donasi Makanan dijelaskan di
[donasi/README.md](donasi/README.md), termasuk integrasi profil, venue, dan klaim
yang masih menunggu model anggota terkait.

Aplikasi ini menggunakan API dari [OpenStreetMap](https://www.openstreetmap.org).
API ini digunakan untuk mencari alamat titik pengambilan makanan di lingkungan kampus
serta menghitung jarak antara lokasi donor dan penerima. Dokumentasi API dapat diakses
di https://wiki.openstreetmap.org/wiki/API.

## Jenis Pengguna Aplikasi

1. **Donor**, yaitu panitia acara, himpunan atau UKM, kantin, dan mitra katering kampus.
   Donor menginput dan mengelola makanan surplus, menyetujui klaim, serta melihat
   dashboard dampak donasinya.
2. **Penerima**, yaitu mahasiswa dan komunitas di lingkungan kampus. Penerima mencari
   makanan yang tersedia, mengklaim makanan, dan melacak status klaimnya.
3. **Admin**, yaitu pengelola platform atau unit kampus. Admin memverifikasi akun,
   mengelola venue, dan membuat laporan dampak tingkat kampus.

## Tautan

- Repositori: https://github.com/Kelompok-7-PBP-D-2026/Proyek-Tengah-Semester
- Deployment PWS: https://immanuel-marvin-pts-surplus.pws.cs.ui.ac.id
- Desain Figma: https://www.figma.com/design/MT2ZypZ7HGnSp8RB2AaWKt

## Design System

Desain antarmuka MBG (Makan Berlebih Gratis) dikelola dalam satu file Figma
(link di atas) dan sudah diimplementasikan sebagai token di
`static/css/style.css` serta kerangka template bersama di `templates/`
(`base.html`, `header.html`, `footer.html`).

- **Palet warna**: Forest Green `#19532B`, Sunshine `#FFCA26`, Cream `#F3E8CC`,
  Crisp Carrot `#F86015`, Kiwi `#9ABC04`, Tomato Burst `#D42518`.
- **Tipografi**: Fredoka untuk judul (display), Poppins untuk teks isi,
  tombol, dan caption.
- **Radius**: 12px untuk tombol/input/chip, 20px untuk kartu.
- **Kerangka CSS**: Bootstrap 5 dengan variabel warna yang dioverride memakai
  token palet di atas, sehingga komponen bawaan ikut tema.
- **Komponen bersama**: tombol (primary hijau/oranye, sekunder kuning, outline),
  chip status, badge tenggat waktu, kartu makanan, kartu statistik dampak,
  navbar dan footer.

## Menjalankan Secara Lokal

1. Buat dan aktifkan virtual environment:
   ```bash
   python -m venv env
   source env/Scripts/activate
   ```
2. Pasang dependensi proyek:
   ```bash
   python -m pip install -r requirements.txt
   ```
3. Salin `.env.example` menjadi `.env`. Untuk pengembangan lokal, nilai default
   `DEBUG=True` sudah cukup; jangan isi maupun commit kredensial PWS ke file ini.
4. Terapkan migrasi lalu jalankan server:
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```
5. Buka http://127.0.0.1:8000/ di browser.

## Deployment PWS

Aplikasi sudah ter-deploy di PWS:

**https://immanuel-marvin-pts-surplus.pws.cs.ui.ac.id**

- Repository PWS: https://pws.cs.ui.ac.id/immanuel.marvin/pts-surplus
- Database: PostgreSQL (schema `tugas_kelompok`)
- Konfigurasi lewat tab Environs di PWS: `PRODUCTION`, `DEBUG`, `SECRET_KEY`, `DB_*`, `SCHEMA`, `PWS_DEPLOY_URL`

## CI/CD

Otomatisasi ada di `.github/workflows/ci-cd.yml` dan terdiri dari dua job:

| Job | Kapan jalan | Yang dilakukan |
|---|---|---|
| `test` | Setiap pull request ke `main` dan setiap push ke `main` | `manage.py check`, cek migrasi belum tertinggal, lalu `manage.py test` beserta laporan coverage |
| `deploy` | Hanya push ke `main`, dan hanya kalau job `test` lulus | Mengambil kode di `main` lalu `git push` ke repository PWS (`main` → `master`), yang memicu build dan `migrate` otomatis di PWS |

**Secret yang dibutuhkan:** `PWS_URL`, dibuat di **Settings → Secrets and variables → Actions → New repository secret**. Isinya URL git PWS lengkap dengan kredensial pemilik proyek:

```
https://<username-PWS>:<password-PWS>@pws.cs.ui.ac.id/immanuel.marvin/pts-surplus
```

## Data Contoh (Seed) di Deployment

Syarat spesifikasi: minimal 50 baris data utama keisi saat deploy. Seed dikirim sebagai
data migration (`profil/0003`, `donasi/0004`, `venue/0002`, `klaim/0002`) yang **hanya
mengisi data kalau env var `MBG_SEED_DEMO` bernilai apa pun** di Environs. Tanpa env
var itu, migration jalan tanpa mengisi apa-apa — database test dan lokal tetap kosong,
dan suite modul lain tidak terganggu.

Crew deployment: tambahkan satu entri di tab **Environs** PWS:

```
MBG_SEED_DEMO = 1
```

Migration `migrate` yang PWS jalankan otomatis setiap deploy akan mengisi ±14 profil
donor, 11 penerima, 6 venue, 56 donasi, dan 8 klaim (semua idempoten). Kalau nanti
butuh database bersih di deployment, hapus env var itu lalu tekan redeploy.

Kredensialnya milik akun pemilik proyek PWS, jadi yang bisa mengisi secret ini adalah pemilik proyek sekaligus admin repositori. Username dan password-nya diambil dari dashboard PWS: **Project → Settings → Git Credentials** (Username dan Git Password; password ini hanya tampil sekali, kalau lupa klik **Regenerate**). Ini bukan password SSO. Kalau password mengandung karakter khusus, tulis dalam bentuk URL-encoded (misalnya `@` jadi `%40`, `!` jadi `%21`). **Buat secret ini sebelum workflow di-merge ke `main`**, supaya tidak ada workflow merah yang gagal deploy. Kalau `PWS_URL` masih kosong, job `deploy` tidak gagal — hanya menulis peringatan dan melewati deploy.

Workflow memakai Python 3.13, sama dengan versi di PWS. Setelah workflow aktif, sebaiknya aktifkan juga aturan di **Settings → Branches → Branch protection rule** untuk `main`: wajib lulus status check `Test` sebelum pull request boleh di-merge.

Deploy tidak pernah jalan dari branch fitur, jadi pekerjaan di branch aman: kode baru sampai ke PWS setelah pull request-nya di-merge ke `main`.
