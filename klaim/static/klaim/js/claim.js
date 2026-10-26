/* Claim module behavior (vanilla JS): confirm dialogs, double-submit guard,
   note character counter, portion input limiter, pickup code uppercase. */
(function () {
    "use strict";

    var root = document.querySelector(".claim-page");
    if (!root) {
        return;
    }

    // ---- Confirm dialog (forms with data-confirm) ----------------------
    var dialog = null;

    function buildDialog() {
        var element = document.createElement("dialog");
        element.className = "claim-confirm";
        element.innerHTML =
            '<form method="dialog" class="claim-confirm__form">' +
            '<h2 class="claim-confirm__title">Konfirmasi</h2>' +
            '<p class="claim-confirm__message"></p>' +
            '<div class="claim-confirm__actions">' +
            '<button type="submit" value="cancel" class="claim-btn claim-btn--outline">Batal</button>' +
            '<button type="submit" value="confirm" class="claim-btn claim-btn--forest">Ya, lanjutkan</button>' +
            "</div></form>";
        // Appended inside .claim-page so scoped CSS still applies.
        root.appendChild(element);
        return element;
    }

    function openConfirm(message, onConfirm) {
        if (!dialog) {
            dialog = buildDialog();
        }
        if (typeof dialog.showModal !== "function") {
            if (window.confirm(message)) {
                onConfirm();
            }
            return;
        }
        dialog.querySelector(".claim-confirm__message").textContent = message;
        dialog.returnValue = "";
        dialog.addEventListener(
            "close",
            function () {
                if (dialog.returnValue === "confirm") {
                    onConfirm();
                }
            },
            { once: true }
        );
        dialog.showModal();
    }

    // ---- Double-submit guard -----------------------------------------
    function submitButtons(form) {
        return form.querySelectorAll('button[type="submit"], button:not([type])');
    }

    function lockForm(form) {
        form.dataset.submitting = "true";
        // Delay so the browser still submits normally before buttons are disabled.
        window.setTimeout(function () {
            submitButtons(form).forEach(function (button) {
                button.disabled = true;
                button.classList.add("is-loading");
            });
        }, 0);
    }

    function unlockForm(form) {
        delete form.dataset.submitting;
        delete form.dataset.confirmed;
        submitButtons(form).forEach(function (button) {
            button.disabled = false;
            button.classList.remove("is-loading");
        });
    }

    document.addEventListener("submit", function (event) {
        var form = event.target;
        if (!form.closest || !form.closest(".claim-page")) {
            return;
        }
        if (form.getAttribute("method") === "dialog") {
            return; // the confirm dialog's own form
        }
        if (form.dataset.submitting === "true") {
            event.preventDefault();
            return;
        }
        var message = form.getAttribute("data-confirm");
        if (message && form.dataset.confirmed !== "true") {
            event.preventDefault();
            var submitter = event.submitter || undefined;
            openConfirm(message, function () {
                form.dataset.confirmed = "true";
                form.requestSubmit(submitter);
            });
            return;
        }
        lockForm(form);
    });

    // Restore forms when the page comes back from the back/forward cache.
    window.addEventListener("pageshow", function (event) {
        if (event.persisted) {
            root.querySelectorAll("form").forEach(unlockForm);
        }
    });

    // ---- Note character counter ----------------------------------------
    root.querySelectorAll("[data-char-counter]").forEach(function (input) {
        var counter = document.querySelector(input.getAttribute("data-char-counter"));
        if (!counter) {
            return;
        }
        var max = parseInt(input.getAttribute("maxlength"), 10) || 140;
        function update() {
            counter.textContent = input.value.length + "/" + max;
        }
        input.addEventListener("input", update);
        update();
    });

    // ---- Portions input limiter ----------------------------------------
    root.querySelectorAll("[data-portion-input]").forEach(function (input) {
        var min = parseInt(input.min, 10) || 1;
        var max = parseInt(input.max, 10) || min;

        function clamp() {
            var value = parseInt(input.value, 10);
            if (isNaN(value)) {
                return;
            }
            input.value = Math.min(Math.max(value, min), max);
        }

        input.addEventListener("keydown", function (event) {
            if (["e", "E", "+", "-", ".", ","].indexOf(event.key) !== -1) {
                event.preventDefault();
            }
        });
        input.addEventListener("input", clamp);
        input.addEventListener("blur", function () {
            if (input.value === "") {
                input.value = min;
            }
            clamp();
        });
    });

    // ---- Pickup code: force uppercase ----------------------------------
    root.querySelectorAll("[data-uppercase]").forEach(function (input) {
        input.addEventListener("input", function () {
            input.value = input.value.toUpperCase();
        });
    });
})();