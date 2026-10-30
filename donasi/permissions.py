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
