# Modul Klaim dan Reservasi (`klaim`)

Modul ini menangani alur **klaim makanan** pada aplikasi **MBG (Makanan Berlebih Gratis)**, proyek PBP Kelompok 7. Penerima mengklaim makanan surplus dari donasi, mendapat **kode ambil unik**, lalu menunjukkan kode itu ke donor saat mengambil makanan. Donor memverifikasi kode, dan klaim dinyatakan selesai.

Modul ini terhubung ke tiga modul lain lewat satu file adapter, `klaim/integrations.py`:

- **`donasi`**: data makanan, stok porsi, batas ambil.
- **`profil`**: peran pengguna (donor atau penerima), nama organisasi, dan NIM.
- **`venue`**: koordinat lokasi pengambilan untuk jarak dan tautan peta.

## Fitur

**Penerima**
- Form klaim: jumlah porsi, waktu ambil (slot 30 menit), catatan opsional (maks. 140 huruf).
- Kode ambil otomatis berformat `MBG-XXXX` (tanpa karakter 0, O, 1, I).
- Halaman **Klaim Saya**: tabel, chip filter status dengan jumlah, paginasi 5 per halaman.
- Halaman **Detail Klaim**: kode ambil, timeline, rincian, kartu lokasi (lokasi ambil, tautan peta, rute, dan jarak), tombol **Batalkan klaim** (hanya di sini).
- Tombol **Klaim** di halaman donasi, dengan alasan penolakan tampil sebagai popover.

**Donor**
- Halaman **Klaim Masuk**: tiga kartu ringkasan (menunggu diambil, sudah diambil, tidak diambil) dan tabel klaim.
- Tombol **Setujui** membuka modal verifikasi kode. Kode cocok berarti klaim selesai, kode salah menampilkan pesan error di modal.
- Nama penerima tampil beserta NIM yang disamarkan, misalnya `Rina Sari (2506 xxxx)`.

## Status klaim

| Nilai di DB | Label | Keterangan |
|---|---|---|
| `pending` | Menunggu | Klaim terkirim, menunggu penerima datang mengambil. |
| `picked_up` | Sudah diambil | Kode sudah diverifikasi donor. Tidak bisa dibatalkan. |
| `cancelled` | Dibatalkan | Dibatalkan oleh penerima. |
| `expired` | Kedaluwarsa | Penerima tidak datang sampai batas waktu ambil klaim. |

Kolom **Keterangan** pada tabel:

| Status | Klaim Saya (penerima) | Klaim Masuk (donor) |
|---|---|---|
| Menunggu | Tombol *Lihat detail* | Tombol *Setujui* |
| Sudah diambil | Tombol *Lihat detail* | Teks *Selesai* |
| Dibatalkan | *Klaim dibatalkan pengguna* | *Klaim dibatalkan* |
| Kedaluwarsa | *Klaim kedaluwarsa* | *Klaim dibatalkan* |

## Peran pengguna

Satu akun hanya punya satu peran, ditentukan oleh profil yang diisi saat daftar (modul `profil`).

| Peran | Penanda | Hak di modul klaim |
|---|---|---|
| Penerima | `user.profil_penerima` | Mengklaim makanan, melihat dan membatalkan klaim miliknya |
| Donor | `user.profil_donor` | Melihat klaim atas donasinya dan memverifikasi kode ambil |

Aturan pengecekan (semua di `integrations.py`):

- `is_recipient(user)` bernilai true jika user punya `profil_penerima`. Alasan penolakan tersedia lewat `recipient_block_reason(user)`.
- `is_donor(user)` bernilai true jika user punya `profil_donor`. Akun tanpa profil apa pun (misalnya akun lama atau superuser) memakai fallback ke `donasi.permissions.is_donor`.
- Akun donor tidak bisa mengklaim makanan, dan akun penerima tidak bisa membuka Klaim Masuk.
- Verifikasi admin (`terverifikasi`) belum diwajibkan. Ubah `REQUIRE_VERIFIED_DONOR` dan `REQUIRE_VERIFIED_RECIPIENT` menjadi `True` di `integrations.py` jika tim ingin mewajibkannya.

## Aturan bisnis

Semua aturan divalidasi di server.

- Hanya user yang login. Penerima hanya bisa melihat dan membatalkan klaim miliknya. Donor hanya bisa mengelola klaim atas donasinya sendiri.
- Hanya akun dengan profil penerima yang bisa mengklaim. Akun tanpa profil diarahkan ke halaman profil dengan pesan penjelasan.
- Donor tidak boleh mengklaim donasinya sendiri.
- Maksimal **3 porsi per klaim** dan tidak boleh melebihi sisa porsi.
- Satu penerima hanya boleh punya **satu klaim `pending`** per donasi (dijaga juga lewat constraint database).
- Donasi yang habis atau lewat batas ambil tidak bisa diklaim.
- Pembuatan klaim berjalan di `transaction.atomic()` dengan `select_for_update()` pada baris donasi untuk mencegah overbooking.
- Penerima hanya bisa membatalkan klaim `pending` yang belum kedaluwarsa.
- Semua aksi yang mengubah data memakai POST dengan CSRF dan `@require_POST`.
- Verifikasi kode membandingkan input dengan `secrets.compare_digest`.

### Sinkronisasi porsi

`Donasi.jumlah_porsi` diperlakukan sebagai **stok sisa**:

| Kejadian | Efek pada `jumlah_porsi` |
|---|---|
| Klaim dibuat | dikurangi sejumlah porsi klaim |
| Klaim dibatalkan | dikembalikan |
| Klaim kedaluwarsa | dikembalikan |
| Klaim diambil (`picked_up`) | tidak berubah (porsi sudah dikurangi saat klaim dibuat) |

Perubahan dilakukan lewat `integrations.adjust_portions()` memakai ekspresi `F()`, tanpa mengubah kode model donasi.

### Kedaluwarsa

Klaim kedaluwarsa jika penerima tidak datang melewati **waktu ambil yang dipilih + toleransi**, dan tidak pernah melewati batas ambil donasi.

- Toleransi diatur di `PICKUP_GRACE_MINUTES` pada `models.py` (default 30, isi `0` untuk batas ketat).
- Rumus ada di `services.calculate_expires_at()`.
- Status disimpan ke database oleh `services.expire_overdue_claims()`, yang dipanggil otomatis di halaman klaim. Bisa juga dijadwalkan:

```powershell
python manage.py expire_claims
```

## Jarak dan rute ke lokasi pengambilan

Jarak **dihitung ulang setiap halaman dibuka**, dari lokasi penerima ke venue tempat makanan diambil.

- **Lokasi makanan:** `Claim.pickup_location` dicocokkan ke `Venue.nama` (tanpa membedakan huruf besar atau kecil). Kalau tidak ada venue yang cocok, jarak tampil `-`.
- **Lokasi penerima:** diambil di browser lewat Geolocation API. Kalau izin ditolak atau tidak tersedia, titik asal memakai pusat kampus (`venue.utils.CAMPUS_CENTER`) dengan keterangan "Perkiraan dari pusat kampus".
- **Moda:** dropdown **Pilih moda** berisi Jalan kaki, Sepeda, dan Motor / mobil. Sebelum moda dipilih, jarak menampilkan *Pilih moda*. Setelah dipilih, tampil seperti **2,1 km (9 menit)**.
- **Rute:** dihitung di browser lewat OSRM milik OpenStreetMap (`routing.openstreetmap.de`), sama seperti halaman venue. Kalau routing gagal, tampil garis lurus (haversine) dengan keterangan "garis lurus".
- **Cache:** hasil rute disimpan di `sessionStorage` maksimal 5 menit, dan permintaan dikirim satu per satu supaya tidak melebihi batas layanan. Pilihan moda diingat selama sesi (`REMEMBER_MODE` di `claim_distance.js`).
- **Tautan peta:** **Lihat Lokasi dan Peta** mengarah ke `venue:detail` (`/venue/<id>/`).
- **Privasi:** lokasi tidak dikirim ke server Django, tetapi koordinat penerima dan venue dikirim ke layanan routing OpenStreetMap setelah moda dipilih.

Halaman yang menampilkannya:

| Halaman | Tampilan |
|---|---|
| Detail Klaim | Kartu lokasi (lokasi ambil, tautan peta, rute, jarak). Rute dan jarak hanya untuk klaim yang masih aktif. |
| Form klaim | Baris **Rute** dan **Jarak** di kartu Ringkasan, dan jarak singkat di kartu makanan setelah moda dipilih. |

## Tombol Klaim di halaman donasi

Template donasi memasang tag berikut, dengan variabel berupa **instance `Donasi`**:

```django
{% load claim_extras %}
{% claim_button item %}
```

Dan di blok script halaman:

```django
{% block extra_scripts %}
{% claim_button_scripts %}
{% endblock %}
```

Perilaku tombol:

| Kondisi | Tampilan |
|---|---|
| Belum login | Tombol aktif, diarahkan ke login |
| Donor, atau pemilik donasi | Tombol disembunyikan |
| Akun tanpa profil penerima | Tombol pudar, alasan tampil di popover |
| Donasi habis, lewat batas, atau sudah diklaim | Tombol pudar, alasan tampil di popover |
| Bisa diklaim | Tombol *Klaim* aktif |

Tombol pudar tetap bisa diklik tanpa pindah halaman. Popover Bootstrap (`claim_popover.js`) memakai delegasi pada `<body>`, jadi tetap berfungsi setelah daftar donasi diperbarui oleh filter atau pencarian. Tag ini butuh context processor `django.template.context_processors.request`.

## Struktur folder

```
klaim/
├── admin.py
├── forms.py                  # ClaimForm (porsi, slot waktu, catatan)
├── integrations.py           # SATU-SATUNYA adapter ke donasi, profil, dan venue
├── models.py                 # Claim, ClaimStatus, konstanta
├── services.py               # aturan bisnis (create, cancel, verify, expire)
├── tests.py                  # unit test seluruh modul
├── urls.py
├── utils.py                  # slot waktu (WIB), kode ambil, format tanggal Indonesia
├── views.py
├── management/commands/
│   └── expire_claims.py
├── templatetags/
│   └── claim_extras.py       # filter format + tag claim_button, claim_location_card, dll.
├── templates/klaim/
│   ├── claim_form.html       # Buat Klaim
│   ├── claim_list.html       # Klaim Saya
│   ├── claim_detail.html     # Detail Klaim
│   ├── incoming_claims.html  # Klaim Masuk + modal verifikasi
│   ├── _claim_button.html    # tombol Klaim di halaman donasi
│   ├── _location_card.html   # kartu lokasi (lokasi ambil, rute, jarak)
│   ├── _distance_rows.html   # baris Rute (dropdown) dan Jarak
│   ├── _distance_inline.html # jarak singkat di kartu makanan
│   └── _*.html               # partial lain: badge, pagination, messages, ikon
└── static/klaim/
    ├── css/claim.css         # di-scope di bawah .claim-page
    └── js/
        ├── claim.js          # konfirmasi, modal verifikasi, penghitung huruf, dll.
        ├── claim_distance.js # rute dan jarak dari lokasi penerima
        └── claim_popover.js  # popover alasan di tombol Klaim
```

Template klaim memuat CSS lewat `{% block extra_head %}` dan JS lewat `{% block extra_scripts %}` milik `base.html`.

## URL

Semua rute berada di bawah `/klaim/` dengan namespace `klaim`.

| URL | Nama | Akses | Keterangan |
|---|---|---|---|
| `/klaim/` | `klaim:claim_list` | Login | Klaim Saya |
| `/klaim/create/<donation_id>/` | `klaim:claim_create` | Penerima | Form klaim |
| `/klaim/<pk>/` | `klaim:claim_detail` | Pemilik klaim | Detail klaim |
| `/klaim/<pk>/cancel/` | `klaim:claim_cancel` | Pemilik klaim, POST | Batalkan klaim |
| `/klaim/incoming/` | `klaim:incoming_claim_list` | Donor | Klaim Masuk |
| `/klaim/<pk>/verify/` | `klaim:claim_verify_code` | Donor pemilik, POST | Verifikasi kode (JSON untuk modal) |

## Integrasi dengan modul lain

### Donasi (`donasi.Donasi`)

`Claim` menyimpan **snapshot** data donasi (nama makanan, nama donor, lokasi, batas ambil) dan `donation_id` sebagai integer biasa, bukan ForeignKey. Pemetaan field ada di `FIELD_MAP`:

| Kunci klaim | Sumber |
|---|---|
| `food_name` | `Donasi.nama` |
| `pickup_location` | `Donasi.lokasi` |
| `pickup_start` | `Donasi.waktu_tersedia` |
| `pickup_deadline` | `Donasi.waktu_akhir_pengambilan` |
| `available_portions` | `Donasi.jumlah_porsi` (stok sisa) |
| `owner_id` | `Donasi.donor_id` |
| `donor_name` | `donor.profil_donor.nama_unit`, dengan fallback ke nama atau username pemilik |
| `distance_km` | tidak disimpan, dihitung di browser |

### Profil (`profil`)

| Kebutuhan | Sumber |
|---|---|
| Peran donor | `user.profil_donor` |
| Peran penerima | `user.profil_penerima` |
| Nama donor | `ProfilDonor.nama_unit` |
| Nama penerima | `ProfilPenerima.nama_lengkap` |
| NIM | `ProfilPenerima.nim`, disamarkan untuk donor menjadi `2506 xxxx` (`NIM_VISIBLE_DIGITS`) |
| Halaman profil | URL `profil:profil_saya` |

### Venue (`venue.Venue`)

| Kebutuhan | Sumber |
|---|---|
| Pencocokan lokasi | `Claim.pickup_location` dengan `Venue.nama` (case-insensitive, `pk` terkecil jika ada nama kembar) |
| Koordinat | `Venue.latitude` dan `Venue.longitude` |
| Pusat kampus (titik asal cadangan) | `venue.utils.CAMPUS_CENTER` |
| Tautan peta | URL `venue:detail` |

Jika nama model, field, atau URL berubah, cukup ubah konstanta di bagian atas `integrations.py`: `DONATION_MODEL`, `FIELD_MAP`, `DONOR_PROFILE_ATTR`, `RECIPIENT_PROFILE_ATTR`, `VENUE_MODEL`, `VENUE_NAME_FIELD`, dan nama URL.

### Navbar (`templates/header.html`)

Menu dibedakan per peran, dan menu aktif ditandai pil hijau:

| Peran | Menu |
|---|---|
| Penerima | Klaim saya (`klaim:claim_list`), Cari makanan (`donasi:daftar`), Dampak |
| Donor | Klaim masuk (`klaim:incoming_claim_list`), Donasi saya (`donasi:daftar` dengan `?mine=1`), Dampak |

## Cara menjalankan

Prasyarat: Django 5.2, `'klaim'` di `INSTALLED_APPS`, dan `path("klaim/", include("klaim.urls"))` di `pts_project/urls.py`.

```powershell
python manage.py makemigrations klaim
python manage.py migrate
python manage.py runserver
```

Jika skema berubah dan migrasi lama perlu dibuat ulang, balikkan dulu sebelum menghapus file migrasi:

```powershell
python manage.py migrate klaim zero
Remove-Item klaim\migrations\0*.py
python manage.py makemigrations klaim
python manage.py migrate
```

Di deployment, jalankan `python manage.py collectstatic` (WhiteNoise), atur `LOGIN_URL` ke halaman login tim, dan akses lewat HTTPS (Geolocation API ditolak browser di koneksi tidak aman, kecuali `localhost`).

### Data uji

Cara termudah adalah mendaftar lewat halaman `daftar/` modul profil (satu akun donor dan satu akun penerima). Atau buat lewat `python manage.py shell`:

```python
from django.contrib.auth import get_user_model
from profil.models import ProfilDonor, ProfilPenerima
U = get_user_model()

donor = U.objects.create_user("demo_donor", password="demo12345")
ProfilDonor.objects.create(
    user=donor, nama_unit="BEM Fasilkom UI", jenis="himpunan",
    kontak="bem@example.com",
)

recipient = U.objects.create_user("demo_recipient", password="demo12345")
ProfilPenerima.objects.create(
    user=recipient, nama_lengkap="Rina Sari", nim="2506000001",
    fakultas="fasilkom", kontak="rina@example.com",
)
```

Untuk mencoba jarak, buat venue yang namanya sama dengan lokasi donasi (misalnya lewat `python manage.py seed_venue` atau halaman `/venue/tambah/`).

Alur uji manual:

1. Login donor, buat donasi di `/donasi/buat/` (batas ambil beberapa jam ke depan, porsi misalnya 10).
2. Login penerima, buka `/klaim/create/<id donasi>/`, lalu kirim klaim. Stok donasi berkurang. Di detail klaim, kolom Donor berisi nama unit.
3. Pilih moda di kartu lokasi, lalu cek jarak dan tautan peta.
4. Cek `/klaim/` (status Menunggu, tombol *Lihat detail*) dan detail klaim (kode ambil, tombol *Batalkan klaim*).
5. Login donor, buka `/klaim/incoming/`. Penerima tampil sebagai `Rina Sari (2506 xxxx)`. Klik **Setujui**, isi kode salah lalu kode benar.
6. Cek ulang sebagai penerima: status *Sudah diambil* dan tombol batalkan hilang.
7. Uji batal: klaim baru lalu batalkan, stok donasi kembali.
8. Uji peran: sebagai donor, tombol Klaim tidak muncul di daftar donasi. Klaim donasi yang sudah kamu klaim memunculkan popover, tanpa pindah halaman.

## Pengujian otomatis

```powershell
python manage.py test klaim
```

Test ada di `klaim/tests.py` dan memakai database test terpisah, jadi data lokal aman. Cakupannya:

| Bagian | Yang diuji |
|---|---|
| Utilitas | Format dan normalisasi kode ambil, slot 30 menit (pembulatan, batas deadline, mulai tersedia, batas jumlah), format tanggal dan jarak |
| Model | Status dan properti (`is_overdue`, `can_cancel`, `display_status`), timeline, constraint database (satu klaim `pending` per donasi, batas 1 sampai 3 porsi) |
| Membuat klaim | Snapshot donasi, pengurangan stok, batas 3 porsi, tidak melebihi stok, donasi habis atau lewat batas, klaim ganda, donor tidak bisa klaim donasinya sendiri, validasi waktu ambil, klaim kedaluwarsa melepas porsi sebelum klaim baru |
| Membatalkan | Porsi kembali, tidak bisa dibatalkan dua kali atau setelah diambil, klaim overdue menjadi kedaluwarsa |
| Verifikasi kode | Kode benar atau salah, kode tidak peka huruf besar, kode tidak bisa dipakai dua kali, klaim batal atau kedaluwarsa ditolak, stok tidak berubah saat diambil |
| Kedaluwarsa | Porsi kembali, idempoten, tidak menyentuh klaim aktif atau selesai, filter per donasi, perintah `expire_claims` |
| View penerima | Wajib login, form klaim, validasi form, redirect, daftar dengan filter dan paginasi, detail hanya milik sendiri, pembatalan lewat POST dengan `next` yang aman |
| View donor | Hanya donor yang bisa membuka Klaim Masuk, NIM disamarkan, kartu ringkasan, endpoint verifikasi (JSON, 400, 403, 404) |
| Integrasi | Peran dari profil, nama tampilan, adapter donasi, tag `claim_button` (donor, popover, anonim), pencocokan venue, kartu lokasi |

Catatan:

- Test yang butuh venue otomatis dilewati kalau app `venue` tidak terpasang.
- Test memakai penyimpanan static biasa, jadi `collectstatic` tidak diperlukan.
- Perlindungan klaim bersamaan lewat `select_for_update()` baru berlaku di PostgreSQL. SQLite lokal tidak punya kunci baris, jadi aturan yang sama diuji secara berurutan.
- Rute OSRM, Geolocation, dan popover adalah perilaku browser (JavaScript) dan belum diuji otomatis.

## Catatan untuk tim

- **Modul donasi (penting):** `donasi/permissions.py` menentukan donor lewat grup Django `Donor`, sedangkan pendaftaran di `profil` tidak menambahkan grup itu. Akibatnya donor yang daftar lewat profil tidak bisa membuat donasi. Usul: `is_donor` di donasi memakai `hasattr(user, "profil_donor")` atau superuser, supaya satu sumber kebenaran dengan klaim.
- **Modul donasi:** `jumlah_porsi` kini berarti stok sisa. Label di form edit sebaiknya "Sisa porsi". Panggil `expire_overdue_claims()` di view daftar dan detail donasi, atau jadwalkan `expire_claims`, agar porsi klaim kedaluwarsa cepat kembali.
- **Hapus donasi:** karena `donation_id` bukan ForeignKey, `ProtectedError` tidak terpicu. Cek dulu `Claim.objects.filter(donation_id=pk, status="pending").exists()` sebelum menghapus.
- **Venue:** `Donasi.lokasi` adalah teks yang dicocokkan ke `Venue.nama`. Kalau venue diganti namanya atau dihapus, jarak klaim lama menjadi `-`. Kalau nanti `Donasi` memakai ForeignKey ke `Venue`, ubah `get_location_point` di `integrations.py`.
- **Modul laporan:** data dampak dari `Claim.objects.filter(status="picked_up")`, misalnya `Sum("portions")`.

## Keterbatasan saat ini

- Jarak memakai pencocokan nama teks ke venue, dan pilihan moda disimpan terpisah dari halaman venue (kunci `sessionStorage` berbeda).
