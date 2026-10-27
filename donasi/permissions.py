from profil.models import ProfilDonor, ProfilPenerima


def is_donor(user):
    """Adapter autentikasi bersama: role donor ditentukan oleh modul Profil Pengguna.

    Donor adalah akun aktif yang punya `ProfilDonor`. Superuser tetap boleh mencoba
    fitur donor (kepemilikan donasi tetap dibatasi ke donasi miliknya sendiri).
    """
    if not (user.is_authenticated and user.is_active):
        return False
    return ProfilDonor.objects.filter(user=user).exists()


def is_recipient(user):
    if not (user.is_authenticated and user.is_active):
        return False
    return ProfilPenerima.objects.filter(user=user).exists()
