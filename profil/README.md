# Modul Profil Pengguna - Fikri Okto Setiadi

Modul profil MBG dibuat dengan Django MVT, Bootstrap 5, HTMX, dan Python murni
untuk perhitungan jarak. Desain mengacu ke [Figma Modul 1](https://www.figma.com/design/MT2ZypZ7HGnSp8RB2AaWKt/Untitled?node-id=94-89)
(page "Profil Pengguna" layar 1A sampai 1D).

Modul ini jadi titik masuk aplikasi: pendaftaran akun donor dan penerima,
halaman profil sendiri, edit profil, dan daftar donor publik. Hak akses "donor"
dan "penerima" di seluruh aplikasi ditentukan dari profil yang dibuat di sini,
jadi modul lain (Donasi, Klaim) tinggal bertanya ke model modul ini.

## Menjalankan

Di direktori yang berisi `manage.py`:

```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Halaman utama modul:

- `/` landing page dengan donasi terbaru dan angka dampak
- `/daftar/` pendaftaran akun donor atau penerima (`?peran=donor|penerima`)
- `/profil/` profil sendiri (wajib login)
- `/profil/edit/` edit profil sendiri (wajib login)
- `/donor/` daftar donor publik dengan filter

Tidak perlu superuser untuk memakai modul ini. Semua akun dibuat dari halaman
pendaftaran.

## Fitur utama

- Pendaftaran satu form: akun user Django plus profil donor atau penerima
  sekaligus, langsung login setelah berhasil.
- Daftar donor publik dengan chip filter jenis (jumlahnya dihitung dari
  database), pencarian nama unit, dan pagination 9 donor per halaman.
- Filter dan pencarian memakai HTMX: panel hasil ditukar tanpa memuat ulang
  halaman, dan link biasa tetap jadi fallback kalau JavaScript mati.
- **Filter radius dari data OpenStreetMap (poin 7 rubrik):** donor bisa mengisi
  lokasi dari autocomplete Nominatim (klien milik modul Venue), lalu di daftar
  donor ada dropdown "dalam radius" (2/5/10/25 km) yang menyaring donor berdasar
  jarak haversine dari titik acuan profil donor yang login.
- Kontak donor hanya tampil untuk pengguna yang sudah login (rubrik poin 6).
- Statistik profil donor: jumlah donasi dibuat, porsi tersedia, dan donasi
  aktif, dihitung langsung dari model `Donasi`.
- Layar 1A sampai 1D sudah disesuaikan dengan desain Figma, termasuk kartu
  peran besar di halaman pendaftaran dan komponen design system MBG bersama.

## Model

- `ProfilDonor`: satu akun satu profil donor (`OneToOneField` ke user). Isinya
  nama unit, jenis donor (panitia, himpunan, kantin, katering), kontak, dan
  deskripsi. Lokasi ditambahkan sebagai `alamat` + `latitude` + `longitude`
  (boleh kosong), diisi dari hasil pencarian OpenStreetMap.
- `ProfilPenerima`: satu akun satu profil penerima. Isinya nama lengkap, NIM
  (unik), fakultas, dan kontak. NIM terkunci setelah pendaftaran supaya
  identitas mahasiswa tidak bisa diubah sembarangan.

Koordinat validasi latitude dan longitude sama dengan milik modul Venue
(`-90..90` dan `-180..180`).

## Endpoint

| URL | Metode | Fungsi |
| --- | --- | --- |
| `/` | GET | Landing page dengan donasi terbaru dan angka dampak |
| `/daftar/` | GET, POST | Pendaftaran donor atau penerima |
| `/profil/` | GET | Profil sendiri, statistik donor |
| `/profil/edit/` | GET, POST | Edit profil sendiri |
| `/donor/` | GET | Daftar donor: `jenis`, `q`, `radius`, `page` |
| `/donor/<id>/` | GET | Detail donor, kontak hanya untuk yang login |
| `/api/cari-lokasi/` | GET | Autocomplete alamat dari Nominatim, param `q` |

Parameter daftar donor: `jenis` (nilai dari `JenisDonor`), `q` (nama unit),
`radius` (km, titik acuan dari lokasi profil donor yang login), dan `page`.

## Struktur dan alur kode

| File | Tanggung jawab |
| --- | --- |
| `models.py` | Model profil donor dan penerima, pilihan jenis, inisial avatar. |
| `forms.py` | Form pendaftaran (akun + profil) dan form edit profil. |
| `jarak.py` | Haversine dan filter radius, Python murni tanpa PostGIS. |
| `views.py` | Landing, daftar, edit, daftar donor, detail, endpoint autocomplete. |
| `urls.py` | Pemetaan URL modul. |
| `templates/profil/` | Halaman dan partial HTMX. |
| `static/js/profil_lokasi.js` | Autocomplete lokasi: debounce, fetch, isi field tersembunyi lat/lng. |
| `tests.py` | Regression test model, view, HTMX, filter radius, dan endpoint. |

Alur request utama:

1. URL memilih fungsi di `views.py`.
2. Untuk halaman yang butuh login, `@login_required` lempar ke halaman masuk.
3. View memvalidasi input melalui `ModelForm` dan Django auth.
4. Request HTMX menerima partial panel, request biasa menerima halaman penuh.
5. Filter radius memanggil `jarak.filter_radius()` untuk menandai donor dalam
   radius, hasilnya difilter sebelum pagination.

## Hubungan dengan modul kelompok

- **Venue:** modul ini konsumen klien `venue.osm.cari_alamat()` untuk
  autocomplete lokasi. Tidak ada klien Nominatim kedua, satu layanan disebagai
  sumber data lokasi untuk seluruh aplikasi.
- **Donasi:** statistik profil donor (jumlah donasi, porsi) dihitung dari model
  `Donasi`. Sebaliknya hak akses donor di modul Donasi berasal dari
  `ProfilDonor` milik modul ini.
- **Klaim:** penerima yang dibuat di sini jadi penentu siapa boleh klaim.
- **Laporan:** angka dampak di landing page dihitung dari agregasi `Donasi`,
  siap ditarik ulang dari modul Laporan kalau mau lebih detail.

## Keputusan implementasi

- Status "donor" dan "penerima" tidak disimpan di user. Keduanya ditentukan
  dari keberadaan baris `ProfilDonor` atau `ProfilPenerima`, jadi admin tidak
  otomatis jadi donor.
- Filter radius dihitung di Python (haversine) bukan di SQL karena jumlah donor
  kecil dan proyek tidak pakai PostGIS. Sederhana dan mudah diuji.
- Titik acuan filter radius diambil dari lokasi profil yang login, bukan dari
  URL, supaya tidak bisa dipalsukan lewat query string.
- Donor tanpa koordinat dikeluarkan dari hasil filter radius. Daftar biasa
  (tanpa radius) tetap menampilkan semua donor.
- Angka di chip filter jenis dihitung dari seluruh donor, bukan hasil filter
  aktif, supaya angka tidak berubah-ubah saat pengguna memilih kategori.
- Data contoh (seed) dikirim sebagai data migration yang hanya jalan kalau
  env var `MBG_SEED_DEMO` diset di Environs PWS. Test dan lokal tidak
  terganggu karena env var itu tidak pernah diset di sana.

## Penggunaan AI

Pengembangan modul ini menggunakan **Claude (Hermes Agent)** sebagai alat
bantu, dipakai secara interaktif lewat perintah di terminal. AI tidak menjadi
sumber kebenaran tunggal dan hasilnya tidak langsung diterima tanpa
pemeriksaan.

### Tujuan penggunaan

- Memecah ketentuan tugas dan rubrik menjadi rencana implementasi Profil.
- Membantu membuat model, form, view, template, CSS, dan regression test.
- Menyesuaikan lima layar Modul 1 dengan desain Figma layar demi layar.
- Membuat filter radius dan integrasi OpenStreetMap dengan pola yang sudah
  dipakai modul lain.
- Menjelaskan kembali alur kode untuk demo dan live coding.

### Strategi prompt

Prompt diberikan bersama konteks rubrik, desain Figma, dan isi repository
sehingga AI tidak menebak struktur. AI selalu diarahkan untuk:

- mengubah hanya app `profil` kecuali file bersama sudah disetujui
- memakai pola yang sudah dipelajari di tutorial PBP (MVT, HTMX, TestCase)
- tidak menyentuh file milik modul lain (misal klien `venue.osm`)
- memvalidasi perubahan melalui `manage.py test` dan system check

Contoh penerapannya:

| Tujuan | Contoh prompt | Hasil bantuan AI | Peninjauan dan perbaikan manual |
| --- | --- | --- | --- |
| Desain Figma | `Sesuaikan lima layar Modul 1 dengan desain Figma layar demi layar.` | Patch template, CSS, dan test komponen desain. | Tampilan diperiksa di browser, test komponen ditulis ulang. |
| Filter radius | `Tambahkan filter radius donor dengan jarak haversine dan titik acuan dari profil.` | Modul `jarak.py`, parameter view, dan dropdown HTMX. | Titik acuan dipindah dari URL ke profil yang login supaya tidak dipalsukan. |
| Integrasi API | `Konsumsi klien Nominatim modul Venue untuk autocomplete lokasi di edit profil.` | Endpoint `cari-lokasi` dan JS autocomplete. | Diperiksa ulang supaya tidak membaca file milik modul lain, hanya mengimpor. |
| Seed data | `Buat data migration seed minimal 50 baris yang idempoten.` | Empat migration seed profil, donasi, venue, klaim. | Guard env var ditambahkan supaya test teman yang asumsi database kosong tetap lulus. |
| Pengujian | `Tambahkan regression test untuk filter radius, endpoint, dan komponen desain.` | Daftar skenario positif dan negatif. | Test disesuaikan dengan perilaku view yang benar, bukan asumsi. |

### Keterbatasan dan perbaikan manual

- AI tidak mengetahui keadaan repository secara real time. Setiap kerjaan
  diawali audit `git status` dan `git log` untuk memastikan tidak ada kerjaan
  teman yang tertimpa.
- AI tidak bisa melihat tampilan browser. Pemeriksaan visual dilakukan manual
  di layar dan dibandingkan dengan Figma.
- Saran test AI bisa melewatkan perilaku negatif. Test tambahan ditulis untuk
  kasus AnonymousUser, parameter URL tidak valid, dan donor tanpa koordinat.
- Validasi akhir tetap dilakukan manual: `manage.py check`, cek migrasi, dan
  seluruh unit test sebelum setiap push.

## Pengecekan

```bash
python -m pip install -r requirements-dev.txt
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test profil
python manage.py test
```

Saat audit terakhir, 49 test profil dan 302 test seluruh proyek lulus. Test
memakai pola dasar `TestCase`, `self.client`, `reverse`, dan assertion Django
agar mudah dipahami untuk live coding.
