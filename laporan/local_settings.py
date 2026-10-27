from pts_project.settings import *

ROOT_URLCONF = "laporan.local_urls"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "laporan" / ".local.sqlite3",
    }
}
TIME_ZONE = "Asia/Jakarta"
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
