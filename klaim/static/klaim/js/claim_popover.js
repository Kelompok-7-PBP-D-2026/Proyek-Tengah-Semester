/* Popover for blocked claims on donation pages.
   The donation module owns the "Klaim" link (href -> klaim:claim_create).
   This script intercepts clicks on those links, asks the server whether the user
   may claim, and shows the reason in a Bootstrap popover instead of navigating.
   Without JavaScript the link still works and the server rejects the request. */
(function () {
    "use strict";

    var script = document.currentScript;
    var createUrl = script && script.dataset.createUrl;
    var checkUrl = script && script.dataset.checkUrl;
    if (!createUrl || !checkUrl || !window.bootstrap || !window.bootstrap.Popover) {
        return;
    }

    // "/klaim/create/0/" -> "/klaim/create/", "/klaim/check/0/" -> "/klaim/check/"
    var createBase = createUrl.replace(/0\/$/, "");
    var checkBase = checkUrl.replace(/0\/$/, "");
    var activePopover = null;

    /* Return the donation id when the link points to the claim form, else null. */
    function donationIdFrom(anchor) {
        var url;
        try {
            url = new URL(anchor.href, window.location.href);
        } catch (error) {
            return null;
        }
        if (url.origin !== window.location.origin || url.pathname.indexOf(createBase) !== 0) {
            return null;
        }
        var rest = url.pathname.slice(createBase.length);
        return /^\d+\/$/.test(rest) ? rest.slice(0, -1) : null;
    }

    function hideActive() {
        if (activePopover) {
            activePopover.dispose();
            activePopover = null;
        }
    }

    function showReason(anchor, message) {
        hideActive();
        activePopover = new window.bootstrap.Popover(anchor, {
            content: message,
            trigger: "manual",
            placement: "top",
            container: "body",
        });
        activePopover.show();
    }

    document.addEventListener("click", function (event) {
        var anchor = event.target.closest ? event.target.closest("a[href]") : null;
        var donationId = anchor ? donationIdFrom(anchor) : null;
        if (donationId === null) {
            hideActive();
            return;
        }
        // Let "open in new tab" and similar clicks behave normally.
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
            return;
        }

        event.preventDefault();
        if (anchor.dataset.claimChecking === "true") {
            return;
        }
        anchor.dataset.claimChecking = "true";

        fetch(checkBase + donationId + "/", {
            credentials: "same-origin",
            headers: { "X-Requested-With": "XMLHttpRequest", Accept: "application/json" },
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("check failed");
                }
                return response.json();
            })
            .then(function (data) {
                if (data.ok) {
                    window.location.href = anchor.href;
                } else {
                    showReason(anchor, data.message || "Klaim tidak bisa dibuat saat ini.");
                }
            })
            .catch(function () {
                // Could not check: let the server decide on the claim page.
                window.location.href = anchor.href;
            })
            .then(function () {
                delete anchor.dataset.claimChecking;
            });
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            hideActive();
        }
    });
})();