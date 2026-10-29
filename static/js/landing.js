// Tab peran mengganti panel donor/penerima tanpa memuat ulang halaman.
document.querySelectorAll("[data-role-tab]").forEach((tab) => {
    tab.addEventListener("click", () => {
        const selectedRole = tab.dataset.roleTab;

        document.querySelectorAll("[data-role-tab]").forEach((item) => {
            const isSelected = item.dataset.roleTab === selectedRole;
            item.classList.toggle("is-active", isSelected);
            item.setAttribute("aria-selected", isSelected);
        });

        document.querySelectorAll("[data-role-panel]").forEach((panel) => {
            panel.hidden = panel.dataset.rolePanel !== selectedRole;
        });
    });
});

// Jika file foto lama hilang, sembunyikan gambar rusak dan pakai ilustrasi latar.
document.querySelectorAll("[data-donation-photo]").forEach((photo) => {
    photo.addEventListener("error", () => {
        photo.hidden = true;
    });
});
