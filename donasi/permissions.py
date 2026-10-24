def is_donor(user):
    """Shared auth adapter: replace group lookup when profil defines its role model."""
    return user.is_authenticated and user.is_active and (
        user.is_superuser or user.groups.filter(name="Donor").exists()
    )
