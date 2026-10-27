# Modul Klaim dan Reservasi (`klaim`)

Modul ini menangani alur **klaim makanan** pada aplikasi **MBG (Makanan Berlebih Gratis)**, proyek PBP Kelompok 7. Penerima mengklaim makanan surplus dari donasi, mendapat **kode ambil unik**, lalu menunjukkan kode itu ke donor saat mengambil makanan. Donor memverifikasi kode, dan klaim dinyatakan selesai.

Modul ini terhubung ke dua modul lain lewat satu file adapter, `klaim/integrations.py`:

- **`donasi`**: data makanan, stok porsi, batas ambil.
- **`profil`**: peran pengguna (donor atau penerima), nama organisasi, dan NIM.

## Fitur

**Penerima**
- Form klaim: jumlah porsi, waktu ambil (slot 30 menit), catatan opsional (maks. 140 huruf).
- Kode ambil otomatis berformat `MBG-XXXX` (tanpa karakter 0, O, 1, I).
- Halaman **Klaim Saya**: tabel, chip filter status dengan jumlah, paginasi 5 per halaman.
- Halaman **Detail Klaim**: kode ambil, timeline, rincian, tombol **Batalkan klaim** (hanya di sini).

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

- `is_recipient(user)`: true jika user punya `profil_penerima`. Alasan penolakan tersedia lewat `recipient_block_reason(user)`.
- `is_donor(user)`: true jika user punya `profil_donor`. Akun tanpa profil apa pun (misalnya akun lama atau superuser) memakai fallback ke `donasi.permissions.is_donor`.
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

## Struktur folder

```
klaim/
├── admin.py
├── forms.py                  # ClaimForm (porsi, slot waktu, catatan)
├── integrations.py           # SATU-SATUNYA adapter ke donasi dan profil
├── models.py                 # Claim, ClaimStatus, konstanta
├── services.py               # aturan bisnis (create, cancel, verify, expire)
├── urls.py
├── utils.py                  # slot waktu (WIB), kode ambil, format tanggal Indonesia
├── views.py
├── management/commands/
│   └── expire_claims.py
├── templatetags/
│   └── claim_extras.py       # filter format + tag {% claim_button %}
├── templates/klaim/
│   ├── claim_form.html       # 3A Buat Klaim
│   ├── claim_list.html       # 3B Klaim Saya
│   ├── claim_detail.html     # 3C Detail Klaim
│   ├── incoming_claims.html  # 3E/3F/3G Klaim Masuk + modal verifikasi
│   └── _*.html               # partial: badge, pagination, messages, ikon, tombol klaim
└── static/klaim/
    ├── css/claim.css         # di-scope di bawah .claim-page
    └── js/claim.js           # konfirmasi, modal verifikasi, penghitung huruf, dll.
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
| `donor_name` | `donor.profil_donor.nama_unit`, fallback ke nama atau username pemilik |
| `distance_km` | belum ada, ditampilkan `-` |

### Profil (`profil`)

| Kebutuhan | Sumber |
|---|---|
| Peran donor | `user.profil_donor` |
| Peran penerima | `user.profil_penerima` |
| Nama donor | `ProfilDonor.nama_unit` |
| Nama penerima | `ProfilPenerima.nama_lengkap` |
| NIM (disamarkan untuk donor) | `ProfilPenerima.nim`, tampil sebagai `2506 xxxx` (`NIM_VISIBLE_DIGITS`) |
| Halaman profil | URL `profil:profil_saya` |

Jika nama model, field, atau URL berubah, cukup ubah konstanta di bagian atas `integrations.py`: `DONATION_MODEL`, `FIELD_MAP`, `DONOR_PROFILE_ATTR`, `RECIPIENT_PROFILE_ATTR`, dan nama URL.

### Tombol "Klaim" di modul donasi

Template donasi memasang tag berikut, dengan variabel berupa **instance `Donasi`**:

```django
{% load claim_extras %}
{% claim_button item %}
```

Perilaku tombol:

| Kondisi | Tampilan |
|---|---|
| Belum login | Tombol aktif, diarahkan ke login |
| Donor, atau pemilik donasi | Tombol disembunyikan |
| Akun tanpa profil penerima | Tombol nonaktif, alasan sebagai tooltip |
| Donasi habis, lewat batas, atau sudah diklaim | Tombol nonaktif, alasan sebagai tooltip |
| Bisa diklaim | Tombol *Klaim* aktif |

Tag ini butuh context processor `django.template.context_processors.request`.

### Navbar (`templates/header.html`)

Menu dibedakan per peran dan menu aktif ditandai pil hijau:

| Peran | Menu |
|---|---|
| Penerima | Klaim saya (`klaim:claim_list`), Cari makanan (`donasi:daftar`), Dampak |
| Donor | Klaim masuk (`klaim:incoming_claim_list`), Donasi saya (`donasi:daftar?mine=1`), Dampak |

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

Di deployment, jalankan `python manage.py collectstatic` (WhiteNoise) dan atur `LOGIN_URL` ke halaman login tim.


Alur uji:

1. Login donor, buat donasi di `/donasi/buat/` (batas ambil beberapa jam ke depan, porsi misalnya 10).
2. Login penerima, buka `/klaim/create/<id donasi>/`, lalu kirim klaim. Stok donasi berkurang. Di detail klaim, kolom Donor berisi nama unit.
3. Cek `/klaim/` (status Menunggu, tombol *Lihat detail*) dan detail klaim (kode ambil, tombol *Batalkan klaim*).
4. Login donor, buka `/klaim/incoming/`. Penerima tampil sebagai `Rina Sari (2506 xxxx)`. Klik **Setujui**, isi kode salah lalu kode benar.
5. Cek ulang sebagai penerima: status *Sudah diambil* dan tombol batalkan hilang.
6. Uji batal: klaim baru lalu batalkan, stok donasi kembali.
7. Uji peran: sebagai donor, tombol Klaim tidak muncul di daftar donasi. Akun tanpa profil melihat tombol nonaktif dan diarahkan ke halaman profil.

## Catatan untuk tim

- **Modul donasi (penting):** `donasi/permissions.py` menentukan donor lewat grup Django `Donor`, sedangkan pendaftaran di `profil` tidak menambahkan grup itu. Akibatnya donor yang daftar lewat profil tidak bisa membuat donasi. Usul: `is_donor` di donasi memakai `hasattr(user, "profil_donor")` atau superuser, supaya satu sumber kebenaran dengan klaim.
- **Modul donasi:** `jumlah_porsi` kini berarti stok sisa. Label di form edit sebaiknya "Sisa porsi". Panggil `expire_overdue_claims()` di view daftar dan detail donasi, atau jadwalkan `expire_claims`, agar porsi klaim kedaluwarsa cepat kembali.
- **Hapus donasi:** karena `donation_id` bukan ForeignKey, `ProtectedError` tidak terpicu. Cek dulu `Claim.objects.filter(donation_id=pk, status="pending").exists()` sebelum menghapus.
- **Modul laporan:** data dampak dari `Claim.objects.filter(status="picked_up")`, misalnya `Sum("portions")`.
- **Modul venue:** jika lokasi pindah ke model venue, ubah satu baris `FIELD_MAP["pickup_location"]`, dan `distance_km` bisa diisi di sana juga.

## Keterbatasan saat ini

- Klaim yang dibuat sebelum integrasi profil tetap menampilkan nama donor lama, karena nama donor disimpan sebagai snapshot saat klaim dibuat.
- Jarak ke lokasi belum tersedia (`distance_km` kosong) sampai modul venue siap.
- Belum ada unit test untuk aturan bisnis (overbooking, klaim ganda, hak akses, kedaluwarsa).