/* Autocomplete lokasi donor dari OpenStreetMap (endpoint profil:cari_lokasi).
 *
 * Alur: ketik di #id_alamat -> (debounce 400ms) GET ?q= -> render daftar hasil
 * -> klik satu hasil: isi input dengan alamat lengkap, isi field tersembunyi
 * latitude/longitude. Tombol "Bersihkan lokasi" kosongkan semua. Jika user
 * mengubah teks tanpa memilih hasil, koordinat lama dikosongkan supaya tidak
 * tersimpan koordinat yang tidak cocok dengan alamat yang tampil.
 */
(function () {
  "use strict";

  var alamat = document.getElementById("id_alamat");
  var hasilBox = document.getElementById("lokasi-donor-hasil");
  var latInput = document.getElementById("id_latitude");
  var lngInput = document.getElementById("id_longitude");
  var bersihBtn = document.getElementById("lokasi-donor-bersih");
  var urlEl = document.getElementById("cari-lokasi-url");
  if (!alamat || !hasilBox || !latInput || !lngInput || !urlEl) return;

  var endpoint = JSON.parse(urlEl.textContent);
  var timer = null;
  var kesed = "Mencari lokasi...";

  function tampilkanBersih(tampil) {
    if (bersihBtn) bersihBtn.hidden = !tampil;
  }

  function tutupHasil() {
    hasilBox.hidden = true;
    hasilBox.innerHTML = "";
  }

  function renderHasil(daftar) {
    if (!daftar.length) {
      hasilBox.innerHTML = '<div class="mbg-osm-kosong">Lokasi tidak ditemukan.</div>';
    } else {
      hasilBox.innerHTML = daftar
        .map(function (item, i) {
          return (
            '<button type="button" class="mbg-osm-pilihan" data-index="' + i + '">' +
            '<strong>' + item.judul + '</strong>' +
            '<span>' + item.subjudul + '</span>' +
            '</button>'
          );
        })
        .join("");
      var tombol = hasilBox.querySelectorAll(".mbg-osm-pilihan");
      daftar.forEach(function (item, i) {
        tombol[i].addEventListener("click", function () {
          alamat.value = item.alamat;
          latInput.value = item.lat;
          lngInput.value = item.lng;
          tutupHasil();
          tampilkanBersih(true);
        });
      });
    }
    hasilBox.hidden = false;
  }

  function cari() {
    var q = alamat.value.trim();
    if (q.length < 3) {
      tutupHasil();
      return;
    }
    hasilBox.hidden = false;
    hasilBox.innerHTML = '<div class="mbg-osm-kosong">' + kesed + "</div>";
    fetch(endpoint + "?q=" + encodeURIComponent(q))
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data.error) {
          hasilBox.innerHTML = '<div class="mbg-osm-kosong">Layanan lokasi sedang tidak bisa dihubungi.</div>';
          return;
        }
        renderHasil(data.hasil || []);
      })
      .catch(function () {
        hasilBox.innerHTML = '<div class="mbg-osm-kosong">Layanan lokasi sedang tidak bisa dihubungi.</div>';
      });
  }

  alamat.addEventListener("input", function () {
    // Teks berubah tanpa memilih hasil -> koordinat lama tidak boleh dibiarkan.
    latInput.value = "";
    lngInput.value = "";
    tampilkanBersih(false);
    if (timer) clearTimeout(timer);
    timer = setTimeout(cari, 400);
  });

  document.addEventListener("click", function (e) {
    if (!hasilBox.contains(e.target) && e.target !== alamat) tutupHasil();
  });

  if (bersihBtn) {
    bersihBtn.addEventListener("click", function () {
      alamat.value = "";
      latInput.value = "";
      lngInput.value = "";
      tutupHasil();
      bersihBtn.hidden = true;
      alamat.focus();
    });
  }

  tampilkanBersih(Boolean(alamat.value && latInput.value));
})();
