const deleteDialog = document.querySelector('[data-report-delete]');
if (deleteDialog && typeof deleteDialog.showModal === 'function') {
  deleteDialog.close();
  deleteDialog.showModal();
  document.querySelector('[data-delete-backdrop]')?.remove();
  deleteDialog.addEventListener('cancel', event => {
    event.preventDefault();
    window.location.assign(deleteDialog.dataset.cancelUrl);
  });
}

const previewForm = document.querySelector('[data-preview-url]');
if (previewForm) {
  const start = previewForm.elements.periode_mulai;
  const end = previewForm.elements.periode_selesai;
  const stats = previewForm.querySelector('[data-preview-stats]');
  const message = previewForm.querySelector('[data-preview-message]');
  const retry = previewForm.querySelector('[data-preview-retry]');
  const numbers = stats.querySelectorAll('[data-impact]');
  const formatter = new Intl.NumberFormat('id-ID');
  let controller;
  let timer;
  let requestId = 0;

  const updatePreview = () => {
    clearTimeout(timer);
    controller?.abort();
    const currentId = ++requestId;
    numbers.forEach(number => { number.textContent = '—'; });
    retry.hidden = true;
    stats.setAttribute('aria-busy', 'false');
    if (!start.value || !end.value || !start.validity.valid || !end.validity.valid) {
      message.textContent = 'Isi kedua tanggal yang valid untuk melihat pratinjau.';
      return;
    }
    if (end.value < start.value) {
      message.textContent = 'Tanggal akhir tidak boleh sebelum tanggal mulai.';
      return;
    }
    message.textContent = 'Menghitung pratinjau…';
    stats.setAttribute('aria-busy', 'true');
    timer = setTimeout(async () => {
      controller = new AbortController();
      const url = new URL(previewForm.dataset.previewUrl, window.location.origin);
      url.searchParams.set('periode_mulai', start.value);
      url.searchParams.set('periode_selesai', end.value);
      try {
        const response = await fetch(url, {
          signal: controller.signal,
          headers: { Accept: 'application/json' },
          cache: 'no-store',
        });
        if (response.redirected || response.status === 403) {
          throw new Error('Sesi pengelola berakhir. Muat ulang halaman dan masuk kembali.');
        }
        const data = await response.json();
        if (!response.ok) {
          const errors = Object.values(data.errors || {}).flat();
          throw new Error(errors[0]?.message || data.error || 'Pratinjau belum tersedia. Silakan coba lagi.');
        }
        if (currentId !== requestId) return;
        numbers.forEach(number => {
          number.textContent = formatter.format(data[number.dataset.impact]);
        });
        message.textContent = `Angka diambil dari ${formatter.format(data.jumlah_klaim)} klaim berstatus sudah diambil pada periode ini (WIB).`;
      } catch (error) {
        if (error.name === 'AbortError' || currentId !== requestId) return;
        message.textContent = error instanceof SyntaxError || error instanceof TypeError
          ? 'Pratinjau belum tersedia. Periksa koneksi, lalu coba lagi.' : error.message;
        retry.hidden = false;
      } finally {
        if (currentId === requestId) stats.setAttribute('aria-busy', 'false');
      }
    }, 250);
  };

  start.addEventListener('input', updatePreview);
  end.addEventListener('input', updatePreview);
  retry.addEventListener('click', updatePreview);
}
