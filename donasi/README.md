# Modul Donasi Makanan — Rindu Maharani Nadhirah

Modul donasi MBG dibuat dengan Django MVT, Bootstrap 5, HTMX, dan JavaScript `fetch`.
Desain mengacu ke [Figma Modul 2](https://www.figma.com/design/MT2ZypZ7HGnSp8RB2AaWKt/Untitled?node-id=94-90).

Modul ini menjadi sumber data makanan surplus. Donor mengelola stok dan waktu
pengambilan, penerima membaca donasi yang tersedia lalu membuat klaim melalui modul
Klaim, sedangkan pilihan lokasi berasal dari modul Venue.

## Menjalankan

Di direktori yang berisi `manage.py`:

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Buka `http://127.0.0.1:8000/donasi/`. Akun donor dapat dibuat melalui halaman
pendaftaran aplikasi. Hak akses donor mengikuti keberadaan `ProfilDonor` dari
modul profil; tidak perlu membuat superuser khusus untuk memakai modul donasi.

## Fitur utama

- Daftar dan detail donasi dapat dibaca publik.
- Donor yang login dapat membuat, mengedit, dan menghapus donasinya sendiri.
- Form HTML tetap berfungsi tanpa JavaScript. Dengan JavaScript, simpan dan hapus
  memakai `fetch`, `FormData`, CSRF token, respons JSON, dan toast.
- Pencarian, filter, dan pagination memakai HTMX untuk mengganti partial kartu tanpa
  memuat ulang seluruh halaman. Form dan link biasa tetap menjadi fallback.
- Daftar memakai pagination sebanyak 6 donasi per halaman.
- Identitas donor tidak dikirim dalam JSON kepada pengguna anonim.
- Foto bersifat opsional, hanya JPG/PNG, dan maksimal 5 MB.

## Aturan data dan validasi

- `jumlah_porsi` adalah stok saat ini. Donasi baru minimal 1 porsi; saat diedit,
  nilai 0 berarti stok sudah habis.
- Tidak ada input status manual. Status **Tersedia** atau **Habis** dihitung dari
  stok, sedangkan **Pengambilan selesai** dihitung dari waktu akhir.
- `waktu_akhir_pengambilan` adalah batas terakhir makanan dapat diambil, bukan
  tanggal kedaluwarsa makanan.
- Akhir pengambilan harus setelah waktu mulai dan masih berada di masa depan saat
  donasi aktif dibuat atau diubah.
- Nama dan lokasi wajib diisi. Catatan bersifat opsional dan maksimal 200 karakter.
- Lokasi dipilih dari data Venue agar nama lokasi, peta OpenStreetMap, dan daftar
  donasi pada detail venue tetap sinkron.
- Kesalahan form dikembalikan oleh `ModelForm` dan ditampilkan melalui toast.
- Pemilik selalu diambil dari `request.user`; donor tidak dapat mengubah pemilik
  melalui isi form atau URL.
- Klaim yang melewati batas diproses saat daftar/detail donasi dibuka, sehingga
  porsinya langsung kembali ke stok.
- Admin tidak otomatis menjadi donor; pengelolaan donasi membutuhkan `ProfilDonor`.

Waktu form dan tampilan donasi memakai WIB secara lokal di app `donasi`, tanpa
mengubah konfigurasi timezone milik seluruh proyek.

## Endpoint

| URL | Metode | Fungsi |
| --- | --- | --- |
| `/donasi/` | GET | Daftar HTML; request HTMX mengembalikan partial hasil |
| `/donasi/api/` | GET | Data donasi dalam JSON dan pagination |
| `/donasi/<id>/` | GET | Detail HTML atau JSON |
| `/donasi/buat/` | GET, POST | Form dan pembuatan donasi |
| `/donasi/<id>/edit/` | GET, POST | Form dan perubahan donasi milik sendiri |
| `/donasi/<id>/hapus/` | GET, POST | Konfirmasi dan penghapusan milik sendiri |
| `/donasi/<id>/foto/` | GET | Menampilkan foto donasi |

Parameter daftar: `q`, `lokasi`, `waktu` (`hari_ini`, `besok`, `pekan_ini`),
`status` (`tersedia`, `habis`), `mine=1`, dan `page`.

## Struktur dan alur kode

| File/folder | Tanggung jawab |
| --- | --- |
| `models.py` | Struktur data Donasi, aturan waktu, serta status stok otomatis. |
| `forms.py` | Field form, pilihan Venue, dan validasi stok, waktu, serta foto. |
| `permissions.py` | Pemeriksaan role donor dan penerima berdasarkan profil pengguna. |
| `views.py` | Query/filter, JSON serialization, detail, CRUD, dan pengiriman file foto. |
| `urls.py` | Pemetaan URL ke view Donasi. |
| `templates/donasi/` | Halaman dan partial HTML yang dirender Django/HTMX. |
| `static/donasi/donasi.js` | Tab filter, AJAX CRUD, CSRF, dan toast. |
| `tests.py` | Regression test model, form, view, security, AJAX, HTMX, dan integrasi. |

Alur request utama:

1. URL Donasi memilih fungsi di `views.py`.
2. View memeriksa role dan kepemilikan data sebelum operasi pengelolaan.
3. `DonasiForm` memvalidasi input; model menjaga aturan data yang tetap berlaku di
   luar form.
4. Request biasa menerima halaman lengkap. Request HTMX menerima partial daftar,
   sedangkan AJAX CRUD menerima JSON.
5. Setelah penyimpanan berhasil, halaman diarahkan ke detail Donasi. Kesalahan
   validasi ditampilkan sebagai toast tanpa menghilangkan isi form.

## Hubungan dengan modul kelompok

- **Profil:** sudah dipakai untuk menentukan apakah pengguna adalah donor.
- **Venue:** sudah terintegrasi melalui pilihan Venue pada form dan tautan peta pada
  detail. Nama venue tetap disimpan sebagai teks sesuai kontrak `venue.integrations`
  dan diteruskan ke snapshot lokasi pada Klaim.
- **Klaim:** sudah terintegrasi. Penerima dapat membuka form klaim dari card atau
  detail donasi. Navbar mengarah ke **Klaim masuk/Klaim saya**, stok diperbarui
  oleh proses klaim, dan statistik detail membaca data klaim yang sebenarnya.
- **Laporan:** sebaiknya menghitung makanan tersalurkan dari data klaim/serah terima,
  bukan langsung dari stok yang ditulis donor.

Semua halaman donasi memakai `templates/header.html` dan `templates/footer.html`
bersama. Integrasi ini tidak mengubah file di app `klaim`.

## Keputusan implementasi

- Status tidak disimpan sebagai input terpisah agar tidak bertentangan dengan stok
  dan waktu. Status dihitung setiap kali data ditampilkan.
- Nama Venue disimpan sebagai teks sesuai kontrak integrasi kelompok, sementara
  pilihan form tetap diambil dari database Venue.
- HTMX dipakai untuk pembacaan/filter daftar, sedangkan `fetch` dipakai untuk
  pengiriman form CRUD. Form HTML biasa tetap menjadi fallback jika JavaScript mati.
- Foto dikirim melalui endpoint Donasi agar file media tidak harus dibuka sebagai
  URL publik langsung.
- Klaim menyimpan snapshot data Donasi. Perubahan stok tetap dilakukan oleh service
  Klaim agar satu aturan tidak ditulis ulang di dua modul.

## Penggunaan AI

Pengembangan modul ini menggunakan **OpenAI ChatGPT/Codex** sebagai alat bantu.
AI tidak menjadi sumber kebenaran tunggal dan hasilnya tidak langsung diterima tanpa
pemeriksaan.

### Tujuan penggunaan

- Memecah ketentuan tugas dan rubrik menjadi rencana implementasi Donasi.
- Membantu membuat rancangan awal model, form, view, template, CSS, JavaScript,
  regression test, dan dokumentasi.
- Membandingkan implementasi dengan desain Figma serta mencari edge case validasi,
  authorization, AJAX, HTMX, dan integrasi antarmodul.
- Membantu menjelaskan kembali alur kode dengan bahasa yang mudah dipelajari untuk
  demo dan live coding.

### Strategi prompt

Prompt diberikan bersama konteks rubrik, tutorial PBP, desain Figma, struktur repo,
dan kontrak data dengan Profil, Venue, serta Klaim. AI selalu diarahkan untuk:

- mengubah hanya app Donasi kecuali perubahan file bersama sudah disetujui;
- memakai pola Django dan JavaScript yang sudah dipelajari;
- menjaga kode tetap sederhana dan memberi komentar hanya pada logika penting;
- memvalidasi perubahan melalui test, coverage, Django system check, dan pemeriksaan
  JavaScript.

Contoh penerapannya:

| Tujuan | Contoh prompting | Hasil bantuan AI | Peninjauan dan perbaikan manual |
| --- | --- | --- | --- |
| Validasi data | “Audit validasi stok dan waktu pengambilan Donasi berdasarkan ketentuan tugas.” | Saran validasi lintas-field dan skenario error. | Pesan error disesuaikan dengan istilah aplikasi dan logika dijaga tetap memakai `ModelForm.clean()`. |
| Authorization | “Pastikan donor hanya dapat mengubah donasinya sendiri dan berikan respons yang sesuai untuk HTML dan AJAX.” | Rancangan pemeriksaan role, ownership, serta respons 401/403. | Alur session, CSRF, dan query berdasarkan pemilik diperiksa kembali melalui negative test. |
| Interaktivitas | “Gunakan HTMX untuk filter dan pagination, serta `fetch` untuk form CRUD tanpa menghilangkan fallback HTML.” | Struktur partial template, respons JSON, dan toast. | JavaScript disederhanakan, fallback tanpa JavaScript dipertahankan, dan interaksi diuji melalui browser. |
| Integrasi modul | “Cocokkan Donasi dengan model Profil, Venue, dan Klaim yang sudah ada di repository.” | Pemetaan role, lokasi, stok, dan data klaim. | Implementasi disesuaikan kembali setelah kode tiap modul digabung agar memakai field dan route yang sebenarnya. |
| Desain antarmuka | “Sesuaikan card dan detail Donasi dengan Figma serta design system bersama.” | Rancangan template dan CSS responsif. | Tampilan dibandingkan dengan Figma, lalu header/footer khusus diganti dengan template bersama agar konsisten. |
| Pengujian | “Tambahkan regression test untuk validasi, izin akses, AJAX, HTMX, dan integrasi.” | Daftar skenario positif dan negatif. | Test disederhanakan ke pola `TestCase` dan Django test client, lalu coverage dan seluruh test dijalankan ulang. |

### Keterbatasan dan perbaikan manual

- Beberapa rancangan awal lebih kompleks daripada materi yang dibutuhkan. Kode dan
  test disederhanakan agar memakai `TestCase`, Django test client, `ModelForm`, HTMX,
  dan `fetch` yang mudah dipahami saat live coding.
- AI belum mengetahui perubahan kode anggota lain sebelum modul digabung. Kontrak
  data selalu diperiksa ulang terhadap model, field, dan route terbaru di repository.
- Hasil desain dari AI tidak otomatis menjamin kesesuaian visual dan responsivitas.
  Tampilan dibandingkan kembali dengan Figma dan diuji pada beberapa ukuran layar.
- Saran test AI dapat melewatkan perilaku negatif atau terlalu bergantung pada detail
  implementasi. Skenario authorization, CSRF, validasi, dan fallback tanpa JavaScript
  ditinjau serta diperbaiki manual.
- Validasi akhir tetap dilakukan manual melalui browser, `manage.py check`, cek
  migrasi, seluruh unit test, coverage, dan pemeriksaan sintaks JavaScript.

## Pengecekan

```powershell
python -m pip install -r requirements-dev.txt
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test donasi
python manage.py test
python -m coverage run --source=donasi --omit="donasi/test*.py,donasi/migrations/*,donasi/management/*" manage.py test donasi
python -m coverage report -m --omit="donasi/test*.py,donasi/migrations/*,donasi/management/*"
node --check donasi/static/donasi/donasi.js
```

Saat audit terakhir, 25 tes Donasi dan 149 tes seluruh proyek lulus. Coverage kode
Python inti app donasi adalah 93%. Tes sengaja memakai pola dasar `TestCase`,
`self.client`, `reverse`, dan assertion Django agar mudah dipahami untuk live coding.
