"""Navigation links supplied by the claims module when its URLs are available."""

from django.urls import NoReverseMatch, reverse


# Fill these with the actual namespaced URL names after the claims module is merged.
# Keep unresolved links disabled instead of sending users to a guessed URL or '#'.
CLAIMS_VIEW_NAMES = {"donor": None, "penerima": None}


def claims_url(*, donor):
    view_name = CLAIMS_VIEW_NAMES["donor" if donor else "penerima"]
    if not view_name:
        return None
    try:
        return reverse(view_name)
    except NoReverseMatch:
        return None
