from profil.models import ProfilDonor


def is_donor(user):
    """Adapter autentikasi bersama: role donor ditentukan oleh modul Profil Pengguna.

    Donor adalah akun aktif yang punya `ProfilDonor`. Superuser tetap boleh mencoba
    fitur donor (kepemilikan donasi tetap dibatasi ke donasi miliknya sendiri).
    """
    if not (user.is_authenticated and user.is_active):
        return False
    if user.is_superuser:
        return True
    return ProfilDonor.objects.filter(user=user).exists()
