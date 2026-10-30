# Modul Venue dan Lokasi

PIC: Immanuel Marvin Pandjaitan. Titik pengambilan makanan dengan peta OpenStreetMap.

## Halaman

| URL | Nama | Siapa |
| --- | --- | --- |
| `/venue/` | `venue:daftar` | Semua orang. Filter fakultas (chip), pencarian nama/fakultas, peta, jarak. |
| `/venue/<id>/` | `venue:detail` | Semua orang. Informasi venue dan donasi di venue itu. |
| `/venue/tambah/` | `venue:buat` | Admin (staff) dan donor. Cari alamat lewat OpenStreetMap, koordinat terisi otomatis. |
| `/venue/<id>/edit/` | `venue:edit` | Admin dan donor. |
| `/venue/<id>/hapus/` | `venue:hapus` | Admin dan donor, hanya POST. Ditolak bila masih ada donasi aktif di venue. |
| `/venue/api/cari-alamat/?q=` | `venue:cari_alamat` | Admin dan donor. Proksi Nominatim (di-cache 1 jam, User-Agent terisi). |

Anonim yang membuka halaman kelola dialihkan ke login. Penerima mendapat 403.

## Model `Venue`

`nama`, `fakultas` (pilihan `UnitVenue`, kodenya sama dengan `profil.Fakultas` ditambah `kampus`),
`alamat` (dari OpenStreetMap), `latitude`, `longitude` (6 desimal, menerima koma), `deskripsi_akses`,
`dibuat_oleh`. Nama unik per fakultas tanpa membedakan huruf besar/kecil.

## Jarak dan rute

Jarak yang tampil adalah **rute jalan** dari lokasi pengguna, dengan pilihan moda: jalan kaki
(default), sepeda, atau motor/mobil. Lokasi diambil di browser lewat Geolocation API. Rute dihitung
di browser lewat OSRM milik OpenStreetMap (`routing.openstreetmap.de`, awalan `routed-foot`,
`routed-bike`, `routed-car`). Halaman daftar memakai satu permintaan `table` untuk semua venue;
halaman detail memakai `route` dan menggambar garis rute di peta. Hasil di-cache di
`sessionStorage`, dan modanya diingat selama sesi.

Privasi: lokasi tidak dikirim ke server Django, tetapi koordinat pengguna dan venue dikirim ke
layanan routing OpenStreetMap. Catatan di halaman menyebutkan hal ini.

Cadangan: bila routing gagal atau lambat (batas wajar 1 permintaan/detik), yang tampil jarak garis
lurus (haversine). Bila izin lokasi ditolak, jarak garis lurus dihitung dari titik pusat kampus
(`utils.CAMPUS_CENTER`, perkiraan) dan pilihan moda disembunyikan. Server menerima `?lat=&lng=`
untuk pengujian (jarak garis lurus).

## Integrasi dengan donasi

Semua yang menyentuh modul donasi ada di `integrations.py`. `Donasi.lokasi` masih teks bebas, jadi
donasi dicocokkan ke venue lewat nama gedung (tanpa membedakan huruf besar/kecil), dan hanya yang
belum lewat batas pengambilan. "Donasi aktif" (penghalang hapus) = masih ada stok dan belum lewat batas.

Kalau `Donasi` nanti memakai `ForeignKey` ke `Venue`, cukup ubah dua fungsi di `integrations.py`.

## Data contoh dan tes

```
python manage.py seed_venue   # 4 venue contoh dari desain (koordinat perkiraan, cek ulang)
python manage.py test venue
```
