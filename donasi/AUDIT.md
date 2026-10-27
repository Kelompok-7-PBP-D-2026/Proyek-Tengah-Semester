# Audit modul donasi — 27 Oktober 2026

Audit ini hanya mengubah file di dalam app `donasi`. Tidak ada template bersama,
konfigurasi proyek, atau file app anggota lain yang diubah.

## Kesesuaian dengan materi

Implementasi utama memakai konsep yang ada di Tutorial 0–6:

- Django model, URL, view, template, `ModelForm`, dan CRUD;
- autentikasi, pemeriksaan role, kepemilikan data, dan CSRF;
- `JsonResponse`, `fetch`, `async/await`, `FormData`, toast, dan `AbortController`;
- partial template untuk memperbarui hasil filter tanpa reload halaman penuh;
- `TestCase`, test client, `reverse`, dan assertion Django.

Bagian yang sebelumnya terlalu kompleks sudah disederhanakan: test migrasi,
mocking waktu, test exception database, pemulihan sesi lintas tab, penanganan
banyak jenis status HTTP, history Back/Forward, custom decorator berbasis
`functools.wraps`, dan management command tambahan.

`ZoneInfo` tetap dipakai agar waktu donasi konsisten dalam WIB tanpa mengubah
timezone seluruh proyek. `FileResponse` tetap dipakai untuk menampilkan unggahan
foto dari app donasi tanpa perlu mengubah konfigurasi URL/media bersama.

## Validasi yang dipertahankan

| Bagian | Aturan |
| --- | --- |
| Urutan waktu | Akhir pengambilan harus setelah waktu mulai; nilai yang sama ditolak. |
| Batas akhir | Donasi aktif harus mempunyai akhir pengambilan di masa depan. |
| Stok | Donasi baru minimal 1 porsi; edit boleh 0 untuk menandai habis. Nilai negatif, pecahan, teks, dan angka di luar batas ditolak. |
| Status | Tersedia/Habis dihitung dari stok; Pengambilan selesai dihitung dari waktu akhir. Tidak ada input status manual. |
| Teks | Nama dan lokasi wajib; spasi kosong ditolak; panjang setiap field dibatasi. |
| Foto | Opsional, berupa JPG/PNG valid, dan maksimal 5 MB. |
| Hak akses | Hanya donor login yang dapat mengelola donasi dan hanya pemilik yang dapat mengedit/menghapus. |
| Hapus | GET menampilkan konfirmasi; penghapusan membutuhkan POST dan CSRF. |
| Pesan error | Kesalahan `ModelForm` dikirim sebagai JSON dan ditampilkan lewat toast. |
| Keamanan tampilan | Template Django melakukan escaping dan JavaScript memasukkan pesan memakai `textContent`. |

## Hasil pengecekan

- 15 tes donasi lulus.
- 36 tes seluruh proyek lulus.
- Coverage kode Python inti app donasi: 85% (test, migrasi, dan folder management
  dikecualikan dari perhitungan).
- `python manage.py check`: bersih.
- `python manage.py makemigrations --check --dry-run`: tidak ada perubahan model.
- `node --check donasi/static/donasi/donasi.js`: sintaks valid.

Acceptance test browser memakai database uji terpisah dan mencakup:

- desktop 1440 px: grid 3 kolom;
- tablet 768 px: grid 2 kolom;
- mobile 390 px: grid 1 kolom dan navbar terlipat;
- tidak ada horizontal overflow pada ketiga ukuran layar;
- tamu tidak melihat tombol edit dan identitas donor disembunyikan;
- penerima melihat menu Cari makanan/Klaim saya dan identitas donor setelah login;
- donor melihat Klaim masuk/Donasi saya, serta tombol edit/hapus hanya pada
  donasi miliknya sendiri;
- Donasi saya tetap menampilkan donasi yang telah berakhir;
- filter pencarian AJAX memperbarui daftar tanpa menghilangkan halaman utama;
- validasi waktu yang salah menampilkan toast yang sesuai dan mempertahankan
  nilai form;
- tidak ditemukan error atau warning JavaScript selama skenario tersebut.

Tes donasi sekarang berfokus pada perilaku yang mudah dijelaskan: halaman daftar
dan detail, CRUD HTML/AJAX, role dan kepemilikan, CSRF, validasi stok/waktu, filter,
Donasi saya, pagination, privasi JSON, navigasi, badge stok, dan informasi porsi.

## Batas cakupan

- Relasi venue, klaim, serta laporan belum diintegrasikan karena modul-modul
  tersebut dikerjakan anggota lain.
- Statistik porsi diklaim dan diambil masih 0 sampai model klaim tersedia.
- Route **Klaim masuk/Klaim saya** belum dihubungkan sampai nama URL modul klaim
  tersedia.
- Pengujian dilakukan dengan database test Django lokal. Integrasi deployment dan
  PostgreSQL tetap perlu diperiksa oleh tim setelah semua modul digabung.
