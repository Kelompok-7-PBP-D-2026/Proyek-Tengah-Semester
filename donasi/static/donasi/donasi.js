(() => {
  // Form filter dikirim oleh HTMX; JavaScript hanya mengatur tab statusnya.
  const filterForm = document.querySelector("#donation-filter");

  function getCookie(name) {
    // Token CSRF dari cookie wajib dikirim pada request POST Django.
    const cookies = document.cookie.split(";");
    for (const cookie of cookies) {
      const [key, value] = cookie.trim().split("=");
      if (key === name) return decodeURIComponent(value);
    }
    return null;
  }

  function showToast(messages, type = "error") {
    // Satu fungsi menangani toast sukses maupun kumpulan pesan validasi.
    const toast = document.querySelector("#donation-toast");
    if (!toast) return;

    const messageList = Array.isArray(messages) ? messages : [messages];
    const body = document.querySelector("#donation-toast-body");
    const title = document.querySelector("#donation-toast-title");
    body.replaceChildren();
    title.textContent = type === "success" ? "Berhasil" : "Periksa kembali";
    toast.classList.toggle("toast-success", type === "success");

    for (const message of messageList) {
      const paragraph = document.createElement("p");
      paragraph.textContent = message;
      body.append(paragraph);
    }

    new window.bootstrap.Toast(toast, { autohide: type === "success" }).show();
  }

  function getErrorMessages(errors) {
    // Ubah object error Django menjadi daftar teks yang bisa dimasukkan ke toast.
    const messages = [];
    for (const fieldErrors of Object.values(errors || {})) {
      for (const error of fieldErrors) messages.push(error.message);
    }
    return messages;
  }

  function updateActiveTab() {
    if (!filterForm) return;
    document.querySelectorAll(".donation-tab").forEach((tab) => {
      // Tab aktif mengikuti input tersembunyi `mine` atau `status` pada form filter.
      let active;
      if (tab.dataset.filterMine) {
        active = filterForm.elements.mine.value === "1";
      } else {
        active = filterForm.elements.mine.value !== "1"
          && filterForm.elements.status.value === tab.dataset.filterStatus;
      }
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-pressed", active);
    });
  }

  if (filterForm) {
    // Klik tab mengisi input tersembunyi, lalu HTMX mengirim form GET yang sama.
    document.querySelectorAll(".donation-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        filterForm.elements.mine.value = tab.dataset.filterMine || "";
        filterForm.elements.status.value = tab.dataset.filterStatus || "";
        updateActiveTab();
        filterForm.requestSubmit();
      });
    });
  }

  document.querySelectorAll("[data-donation-notice]").forEach((notice) => {
    showToast(notice.textContent.trim(), notice.dataset.noticeType);
    notice.hidden = true;
  });

  const initialErrors = document.querySelector("#donation-initial-errors");
  // Error dari submit biasa tetap ditampilkan sebagai toast saat halaman dimuat ulang.
  if (initialErrors) showToast(getErrorMessages(JSON.parse(initialErrors.textContent)));

  // Form buat, edit, dan hapus dikirim melalui AJAX; backend juga menerima submit biasa.
  document.querySelectorAll("[data-donation-form], [data-delete-form]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type='submit']");
      const originalLabel = button.textContent;
      button.disabled = true;
      button.textContent = "Memproses…";

      try {
        const response = await fetch(form.action || window.location.href, {
          method: "POST",
          headers: {
            Accept: "application/json",
            "X-CSRFToken": getCookie("csrftoken"),
          },
          body: new FormData(form),
        });
        const data = await response.json();

        if (response.ok) {
          window.location.href = data.url;
          return;
        }

        const messages = getErrorMessages(data.errors);
        showToast(messages.length ? messages : data.message || "Data gagal disimpan.");
      } catch (error) {
        showToast("Terjadi kesalahan. Silakan coba lagi.");
      } finally {
        button.disabled = false;
        button.textContent = originalLabel;
      }
    });
  });
})();
