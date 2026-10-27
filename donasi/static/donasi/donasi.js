(() => {
  // Elemen utama untuk filter tanpa memuat ulang seluruh halaman.
  const filterForm = document.querySelector("#donation-filter");
  const results = document.querySelector("#donation-results");
  let filterController;

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

    if (window.bootstrap) {
      new window.bootstrap.Toast(toast, { autohide: type === "success" }).show();
    } else {
      toast.classList.add("show");
    }
  }

  function getErrorMessages(errors) {
    const messages = [];
    for (const fieldErrors of Object.values(errors || {})) {
      for (const error of fieldErrors) messages.push(error.message);
    }
    return messages;
  }

  function updateActiveTab() {
    if (!filterForm) return;
    document.querySelectorAll(".donation-tab").forEach((tab) => {
      const active = tab.dataset.filterMine
        ? filterForm.elements.mine.value === "1"
        : filterForm.elements.mine.value !== "1"
          && filterForm.elements.status.value === tab.dataset.filterStatus;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-pressed", active);
    });
  }

  async function loadResults(url) {
    // Batalkan request lama jika pengguna mengganti filter dengan cepat.
    if (filterController) filterController.abort();
    filterController = new AbortController();
    results.setAttribute("aria-busy", "true");

    try {
      const response = await fetch(url, {
        headers: { Accept: "application/json" },
        signal: filterController.signal,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || "Donasi gagal dimuat.");

      results.innerHTML = data.html;
      document.querySelector("#filter-feedback").textContent = `${data.count} donasi ditemukan.`;
      updateActiveTab();
    } catch (error) {
      if (error.name !== "AbortError") showToast(error.message || "Donasi gagal dimuat.");
    } finally {
      results.removeAttribute("aria-busy");
    }
  }

  if (filterForm && results) {
    // Filter dan pagination meminta HTML kartu terbaru melalui JSON.
    filterForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const url = new URL(window.location.href);
      url.search = new URLSearchParams(new FormData(filterForm)).toString();
      loadResults(url);
    });

    document.querySelectorAll(".donation-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        filterForm.elements.mine.value = tab.dataset.filterMine || "";
        filterForm.elements.status.value = tab.dataset.filterStatus || "";
        filterForm.requestSubmit();
      });
    });

    results.addEventListener("click", (event) => {
      const link = event.target.closest("a[data-page]");
      if (!link) return;
      event.preventDefault();
      loadResults(link.href);
    });
  }

  document.querySelectorAll("[data-donation-notice]").forEach((notice) => {
    showToast(notice.textContent.trim(), notice.dataset.noticeType);
    notice.hidden = true;
  });

  const initialErrors = document.querySelector("#donation-initial-errors");
  // Error dari submit biasa tetap ditampilkan sebagai toast saat halaman dimuat ulang.
  if (initialErrors) showToast(getErrorMessages(JSON.parse(initialErrors.textContent)));

  // Form buat, edit, dan hapus dikirim melalui AJAX dengan fallback tetap tersedia di Django.
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
