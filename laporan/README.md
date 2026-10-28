# Modul Laporan Dampak (`laporan`)

Modul ini menangani **laporan penyaluran makanan** pada aplikasi **MBG (Makanan Berlebih Gratis)**, proyek PBP Kelompok 7.

Admin memilih periode, melihat pratinjau, lalu membuat laporan dari klaim makanan yang sudah diambil. Laporan tersimpan dapat dilihat, diedit, dihapus, serta diunduh dalam format PDF atau CSV.

Desain mengacu ke [Figma Modul 5](https://www.figma.com/design/MT2ZypZ7HGnSp8RB2AaWKt/Untitled?node-id=101-91).

## Fitur

- Dashboard ringkasan dampak tahunan.
- Daftar laporan dengan pencarian judul, filter status, dan pagination.
- Form pembuatan laporan berdasarkan periode.
- Judul otomatis jika kolom judul dikosongkan.
- Pratinjau total porsi, donor, dan penerima.
- Detail laporan dengan rincian per donor.
- Edit judul, periode, dan catatan.
- Perhitungan ulang berdasarkan data klaim terbaru.
- Hapus laporan melalui halaman konfirmasi.
- Unduh laporan dalam format PDF atau CSV.

## Hak akses

Seluruh halaman laporan hanya dapat digunakan oleh **akun admin aktif**, yaitu pengguna dengan `is_staff` atau `is_superuser`.

- Pengguna yang belum login diarahkan ke halaman masuk.
- Pengguna biasa tidak dapat membuka, mengubah, atau mengunduh laporan.
- Admin dapat mengelola laporan tingkat kampus, termasuk laporan yang dibuat admin lain.
- Identitas pembuat laporan diambil dari akun yang sedang login.

## Status laporan

| Nilai di database | Label | Keterangan |
| --- | --- | --- |
| `draf` | Draf — menunggu data | Hasil perhitungan belum tersedia. |
| `siap` | Siap — sudah dihitung | Hasil perhitungan sudah disimpan. |

Angka **0** berarti tidak ada hasil penyaluran pada periode tersebut. Tanda **—** berarti data belum tersedia atau belum dihitung.

Secara default, sumber data Claim sudah terhubung. Pembuatan laporan langsung menghitung dan menyimpan hasilnya.

## Aturan perhitungan

Semua perhitungan dilakukan di server.

- Sumber data adalah `klaim.Claim`.
- Hanya klaim berstatus `picked_up` dengan `picked_up_at` terisi yang dihitung.
- Periode mengikuti waktu pengambilan aktual dalam **WIB**, termasuk seluruh tanggal mulai dan selesai.
- Total makanan tersalurkan dijumlahkan dari field `portions`.
- Donor dan penerima dihitung berdasarkan akun unik.
- Satu penerima yang membuat beberapa klaim tetap dihitung sekali pada total penerima.
- Rincian donor menghitung porsi dan penerima unik untuk masing-masing donor.
- Stok tersisa pada Donasi tidak digunakan sebagai jumlah makanan tersalurkan.
- Dashboard tahunan menghitung langsung dari Claim, bukan menjumlahkan laporan yang periodenya mungkin tumpang tindih.

Contoh: penerima A mengambil 2 porsi dan 1 porsi, sedangkan penerima B mengambil 3 porsi dari donor yang sama. Hasilnya adalah **6 porsi, 1 donor, 2 penerima, dan 3 klaim**.

### Penyimpanan hasil

Laporan menyimpan **snapshot**, yaitu salinan hasil pada saat perhitungan dilakukan.

| Tindakan | Dampak pada hasil laporan |
| --- | --- |
| Membuat laporan | Menghitung dan menyimpan hasil sesuai periode. |
| Mengubah judul atau catatan | Mempertahankan hasil sebelumnya. |
| Mengubah periode | Menghitung ulang sesuai periode baru. |
| Menekan tombol hitung ulang | Mengambil data klaim terbaru. |
| Data sumber berubah | Laporan tersimpan tetap sama sampai dihitung ulang. |
| Perhitungan gagal | Perubahan tidak disimpan; hasil lama tetap aman. |

Pratinjau tidak menyimpan laporan. Saat form dikirim, server menghitung kembali agar hasil tidak bergantung pada angka dari browser.

## Struktur folder

```text
laporan/
├── admin.py
├── apps.py
├── models.py             # Data laporan dan validasi model
├── forms.py              # Form laporan, login admin, dan filter
├── views.py              # Alur halaman dan respons JSON
├── urls.py               # Rute modul laporan
├── permissions.py        # Pembatasan akses admin
├── klaim_adapter.py      # Membaca dan menghitung data Claim
├── services.py           # Validasi dan penyimpanan hasil perhitungan
├── exports.py            # Pembuatan CSV dan PDF
├── tests.py              # Pengujian fitur laporan
├── test_integrasi.py     # Pengujian integrasi dengan modul lain
├── migrations/
├── templatetags/
│   └── laporan_format.py
├── templates/laporan/
└── static/laporan/
    ├── laporan.css
    ├── laporan.js
    └── images/
```

## URL

Semua rute berada di bawah `/laporan/` dengan namespace `laporan`.

| URL | Metode | Fungsi |
| --- | --- | --- |
| `/laporan/` | GET | Dashboard dan daftar laporan |
| `/laporan/login/` | GET, POST | Masuk sebagai admin |
| `/laporan/logout/` | POST | Keluar |
| `/laporan/buat/` | GET, POST | Form dan pembuatan laporan |
| `/laporan/pratinjau/` | GET | Pratinjau perhitungan dalam JSON |
| `/laporan/<id>/` | GET | Detail laporan |
| `/laporan/<id>/edit/` | GET, POST | Form dan perubahan laporan |
| `/laporan/<id>/hapus/` | GET, POST | Konfirmasi dan penghapusan laporan |
| `/laporan/<id>/generate/` | POST | Hitung ulang laporan |
| `/laporan/<id>/ekspor.csv` | GET | Unduh CSV |
| `/laporan/<id>/ekspor.pdf` | GET | Unduh PDF |

Parameter daftar: `q` untuk judul, `status` untuk status laporan, dan `page` untuk nomor halaman.

## Integrasi dengan modul lain

- **Klaim:** menyediakan status pengambilan, waktu pengambilan aktual, jumlah porsi, donor, dan penerima.
- **Profil:** menyediakan nama unit dan jenis donor untuk rincian laporan.
- **Donasi:** terhubung melalui Claim. Modul laporan tidak mengubah stok donasi.
- **Aplikasi utama:** menyediakan konfigurasi, database, autentikasi, dan tautan menuju laporan.

Provider perhitungan diatur melalui `LAPORAN_AGGREGATOR` pada settings utama, dengan nilai default `laporan.klaim_adapter.agregasi`.

## Cara menjalankan

Dari folder yang berisi `manage.py`, dengan virtual environment aktif:

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Buka `http://127.0.0.1:8000/laporan/` menggunakan akun admin.

Jika belum memiliki akun admin:

```powershell
python manage.py createsuperuser
```

Modul memakai konfigurasi dan database utama proyek. Tidak diperlukan database atau settings tambahan.

## Pengujian

```powershell
python manage.py test laporan
python manage.py test
python manage.py check
python manage.py makemigrations --check --dry-run
```

Tes mencakup CRUD, hak akses, CSRF, validasi periode, perhitungan Claim, pratinjau, snapshot, rincian donor, dan ekspor.

Pengujian integrasi juga mencakup alur donasi → klaim → konfirmasi kode ambil → laporan → ekspor. Tes menggunakan database sementara.

### Alur uji manual

1. Login sebagai donor dan buat donasi.
2. Login sebagai penerima, lalu klaim beberapa porsi.
3. Login sebagai donor dan konfirmasi kode ambil.
4. Login sebagai admin dan buka `/laporan/buat/`.
5. Pilih periode yang mencakup waktu pengambilan, lalu periksa pratinjau.
6. Buat laporan dan cocokkan total serta rincian donornya.
7. Unduh CSV dan PDF.
8. Coba edit periode, hitung ulang, dan hapus laporan melalui konfirmasi.

## Catatan untuk tim

- Laporan lama tanpa rincian donor dapat diperbarui melalui tombol **Hitung dampak**.
- Klaim dari akun donor yang dihapus tetap masuk total porsi dan penerima, tetapi tidak dihitung sebagai donor unik.
- Penghapusan akun penerima dapat menghapus klaim sumber. Snapshot laporan yang sudah tersimpan tetap utuh.
- Metrik berat makanan dan CO2e belum dihitung karena belum tersedia data sumbernya.
- Setelah merge atau deployment, pasang requirements terbaru dan jalankan migrasi.