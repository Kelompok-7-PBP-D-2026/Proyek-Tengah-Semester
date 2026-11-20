from rest_framework.permissions import BasePermission, SAFE_METHODS

from profil.models import ProfilDonor, ProfilPenerima


def is_donor(user):
    """Donor adalah akun aktif yang memiliki ProfilDonor."""
    if not (user.is_authenticated and user.is_active):
        return False
    return ProfilDonor.objects.filter(user=user).exists()


def is_recipient(user):
    """Penerima adalah akun aktif yang memiliki ProfilPenerima."""
    if not (user.is_authenticated and user.is_active):
        return False
    return ProfilPenerima.objects.filter(user=user).exists()


class IsDonorOwnerOrReadOnly(BasePermission):
    """Izinkan baca publik; tulis hanya untuk donor pemilik Donasi."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return is_donor(request.user)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.donor_id == request.user.id
