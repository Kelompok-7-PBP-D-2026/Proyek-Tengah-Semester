from profil.models import ProfilDonor


def can_manage_venue(user):
    """Admin (staff) dan donor boleh mengelola venue. Melihat venue terbuka untuk umum."""
    if not (user.is_authenticated and user.is_active):
        return False
    return user.is_staff or ProfilDonor.objects.filter(user=user).exists()
