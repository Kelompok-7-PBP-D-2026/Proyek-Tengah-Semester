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

## Public API yang Digunakan

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
- Deployment PWS: akan ditambahkan setelah deployment pertama
- Desain Figma: akan ditambahkan setelah desain selesai dibuat