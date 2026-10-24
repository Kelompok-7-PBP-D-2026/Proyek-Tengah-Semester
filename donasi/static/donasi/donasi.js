(() => {
  "use strict";
  const filter = document.querySelector("#donation-filter");
  const results = document.querySelector("#donation-results");
  let pendingFilter;

  function notify(messages, kind = "error", loginUrl = null) {
    const toast = document.querySelector("#donation-toast");
    if (!toast) return;
    const lines = [...new Set((Array.isArray(messages) ? messages : [messages]).filter(Boolean))];
    const body = document.querySelector("#donation-toast-body");
    body.replaceChildren();
    document.querySelector("#donation-toast-title").textContent = kind === "success" ? "Berhasil" : "Periksa kembali";
    toast.classList.toggle("toast-success", kind === "success");
    toast.setAttribute("role", kind === "success" ? "status" : "alert");
    toast.setAttribute("aria-live", kind === "success" ? "polite" : "assertive");
    const content = document.createElement(lines.length > 1 ? "ul" : "p");
    lines.forEach((message) => {
      if (lines.length === 1) content.textContent = message;
      else {
        const line = document.createElement("li");
        line.textContent = message;
        content.append(line);
      }
    });
    body.append(content);
    if (loginUrl) {
      const url = new URL(loginUrl, window.location.origin);
      if (url.origin === window.location.origin) {
        const login = document.createElement("a");
        login.href = url.href;
        login.target = "_blank";
        login.rel = "noopener";
        login.textContent = "Masuk di tab baru, lalu kembali ke form ini";
        body.append(login);
      }
    }
    if (window.bootstrap?.Toast) {
      window.bootstrap.Toast.getInstance(toast)?.dispose();
      new window.bootstrap.Toast(toast, { animation: false, autohide: kind === "success", delay: 6000 }).show();
    } else {
      toast.classList.add("show");
    }
  }

  function errorMessages(errors, fallback) {
    const messages = Object.values(errors || {}).flat().map((error) => error.message);
    return messages.length ? messages : [fallback];
  }

  async function readResponse(response) {
    const statusMessages = {
      400: "Periksa kembali isian form.",
      401: "Sesi masuk sudah berakhir. Masuk kembali untuk melanjutkan.",
      403: "Permintaan ditolak. Muat ulang halaman untuk memperbarui sesi dan periksa izin akunmu.",
      404: "Donasi tidak ditemukan atau kamu tidak memiliki akses. Periksa kembali daftar donasi.",
      405: "Tindakan ini tidak diizinkan. Muat ulang halaman dan coba kembali.",
      409: "Donasi memiliki data terkait sehingga belum dapat dihapus.",
      413: "Ukuran unggahan terlalu besar. Gunakan foto maksimal 5 MB.",
      429: "Terlalu banyak permintaan. Tunggu sebentar sebelum mencoba lagi.",
    };
    let data = {};
    if ((response.headers.get("Content-Type") || "").includes("json")) {
      try { data = await response.json(); }
      catch (error) {
        if (error.name === "AbortError") throw error;
        throw new Error("Respons server tidak dapat dibaca. Periksa daftar donasi sebelum mencoba lagi.");
      }
    }
    if (!response.ok) return { ...data, message: data.message || statusMessages[response.status] || "Server sedang bermasalah. Periksa daftar donasi sebelum mencoba lagi." };
    if (response.redirected || !data || typeof data !== "object") throw new Error("Sesi atau halaman berubah. Muat ulang halaman sebelum mencoba lagi.");
    return data;
  }

  const toastArea = document.querySelector("#donation-toast-area");
  // Keep dismissing the toast keyboard-accessible inside Bootstrap's modal focus trap.
  document.querySelectorAll(".modal").forEach((modal) => {
    modal.addEventListener("show.bs.modal", () => { if (toastArea) modal.append(toastArea); });
    modal.addEventListener("hidden.bs.modal", () => { if (toastArea) document.body.append(toastArea); });
  });
  document.querySelector("#donation-toast .btn-close")?.addEventListener("click", () => {
    if (!window.bootstrap?.Toast) document.querySelector("#donation-toast").classList.remove("show");
  });
  document.querySelectorAll("[data-donation-notice]").forEach((notice) => {
    notify(notice.textContent.trim(), notice.dataset.noticeType === "success" ? "success" : "error");
    notice.hidden = true;
  });
  const initialErrors = document.querySelector("#donation-initial-errors");
  if (initialErrors) notify(errorMessages(JSON.parse(initialErrors.textContent), "Periksa kembali isian form."));

  function showFilterState() {
    document.querySelectorAll(".donation-tab").forEach((tab) => {
      const active = tab.dataset.filterMine
        ? filter.elements.mine.value === "1"
        : filter.elements.mine.value !== "1" && filter.elements.status.value === tab.dataset.filterStatus;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-pressed", String(active));
    });
  }

  async function loadResults(url, push = true) {
    pendingFilter?.abort();
    const controller = new AbortController();
    pendingFilter = controller;
    results.setAttribute("aria-busy", "true");
    const feedback = document.querySelector("#filter-feedback");
    feedback.className = "visually-hidden";
    feedback.textContent = "Memuat donasi…";
    try {
      const response = await fetch(url, { headers: { Accept: "application/json" }, signal: controller.signal });
      const data = await readResponse(response);
      if (pendingFilter !== controller) return;
      if (!response.ok || typeof data.html !== "string") throw new Error(data.message || "Donasi belum dapat dimuat. Coba terapkan filter lagi.");
      // This fragment is rendered and escaped by Django, never built from raw user strings.
      results.innerHTML = data.html;
      feedback.textContent = `${data.count} donasi ditemukan.`;
      if (push) history.pushState({}, "", url);
      showFilterState();
    } catch (error) {
      if (error.name === "AbortError" || pendingFilter !== controller) return;
      feedback.className = "alert alert-danger";
      feedback.textContent = error instanceof TypeError ? "Donasi belum dapat dimuat. Periksa koneksi lalu coba lagi." : error.message;
      notify(feedback.textContent);
    } finally {
      if (pendingFilter === controller) results.removeAttribute("aria-busy");
    }
  }

  if (filter && results) {
    filter.addEventListener("submit", (event) => {
      event.preventDefault();
      const url = new URL(window.location.href);
      url.search = new URLSearchParams(new FormData(filter)).toString();
      loadResults(url);
    });
    document.querySelectorAll(".donation-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        filter.elements.mine.value = tab.dataset.filterMine || "";
        filter.elements.status.value = tab.dataset.filterStatus || "";
        filter.requestSubmit();
      });
    });
    results.addEventListener("click", (event) => {
      const link = event.target.closest("a[data-page]");
      if (!link || event.ctrlKey || event.metaKey || event.shiftKey) return;
      event.preventDefault();
      loadResults(new URL(link.href));
    });
    window.addEventListener("popstate", () => {
      const params = new URL(window.location.href).searchParams;
      for (const key of ["q", "lokasi", "waktu", "status", "mine"]) filter.elements[key].value = params.get(key) || "";
      loadResults(new URL(window.location.href), false);
    });
  }

  document.querySelectorAll("[data-donation-form], [data-delete-form]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type='submit']");
      if (button.disabled) return;
      const label = button.textContent;
      const summary = form.querySelector(".donation-form-errors");
      summary.textContent = "";
      form.querySelectorAll(".donation-field").forEach((field) => {
        field.classList.remove("has-error");
        field.querySelector(".donation-field-errors").textContent = "";
        field.querySelector("input, select, textarea")?.removeAttribute("aria-invalid");
      });
      button.disabled = true;
      button.textContent = "Memproses…";
      try {
        const body = new FormData(form);
        // Login in another tab rotates CSRF: prefer the current cookie over a stale hidden token.
        // When cookies are HttpOnly/session-backed, keep Django's rendered masked token.
        const cookieName = toastArea?.dataset.csrfCookieName || "csrftoken";
        const csrfCookie = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith(`${cookieName}=`));
        if (csrfCookie) body.set("csrfmiddlewaretoken", decodeURIComponent(csrfCookie.slice(cookieName.length + 1)));
        const response = await fetch(form.action || window.location.href, {
          method: "POST", body, headers: { Accept: "application/json" },
        });
        const data = await readResponse(response);
        if (response.ok) {
          if (typeof data.url !== "string") throw new Error("Respons server tidak lengkap. Periksa daftar donasi sebelum mencoba lagi.");
          window.location.assign(data.url);
          return;
        }
        summary.textContent = data.message || "Data belum dapat disimpan.";
        for (const [name, errors] of Object.entries(data.errors || {})) {
          const field = [...form.querySelectorAll("[data-field]")].find((node) => node.dataset.field === name);
          if (!field) {
            summary.textContent += ` ${errors.map((error) => error.message).join(" ")}`;
            continue;
          }
          field.classList.add("has-error");
          field.querySelector("input, select, textarea")?.setAttribute("aria-invalid", "true");
          const target = field.querySelector(".donation-field-errors");
          errors.forEach((error) => {
            const line = document.createElement("p");
            line.textContent = error.message;
            target.append(line);
          });
        }
        notify(errorMessages(data.errors, summary.textContent), "error", data.login_url);
        const firstInvalid = form.querySelector(".has-error input, .has-error select, .has-error textarea");
        (firstInvalid || summary).focus();
      } catch (error) {
        summary.textContent = error instanceof TypeError ? "Koneksi terputus. Periksa daftar donasi sebelum mengirim ulang agar donasi tidak tersimpan dua kali." : error.message;
        notify(summary.textContent);
      } finally {
        button.disabled = false;
        button.textContent = label;
      }
    });
  });
})();
