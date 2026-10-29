# Modul Donasi Makanan — Rindu Maharani Nadhirah

Modul donasi MBG dibuat dengan Django MVT, Bootstrap 5, HTMX, dan JavaScript `fetch`.
Desain mengacu ke [Figma Modul 2](https://www.figma.com/design/MT2ZypZ7HGnSp8RB2AaWKt/Untitled?node-id=94-90).

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
| `/donasi/` | GET | Daftar HTML; header JSON mengembalikan partial hasil |
| `/donasi/api/` | GET | Data donasi dalam JSON dan pagination |
| `/donasi/<id>/` | GET | Detail HTML atau JSON |
| `/donasi/buat/` | GET, POST | Form dan pembuatan donasi |
| `/donasi/<id>/edit/` | GET, POST | Form dan perubahan donasi milik sendiri |
| `/donasi/<id>/hapus/` | GET, POST | Konfirmasi dan penghapusan milik sendiri |
| `/donasi/<id>/foto/` | GET | Menampilkan foto donasi |

Parameter daftar: `q`, `lokasi`, `waktu` (`hari_ini`, `besok`, `pekan_ini`),
`status` (`tersedia`, `habis`), `mine=1`, dan `page`.

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

Saat audit terakhir, 25 tes donasi dan 83 tes seluruh proyek lulus. Coverage kode
Python inti app donasi adalah 93%. Tes sengaja memakai pola dasar `TestCase`,
`self.client`, `reverse`, dan assertion Django agar mudah dipahami untuk live coding.
