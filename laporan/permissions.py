from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.shortcuts import render
from django.urls import reverse


def is_admin(user):
    return user.is_authenticated and user.is_active and (user.is_staff or user.is_superuser)


def admin_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), reverse("laporan:login"))
        if not is_admin(request.user):
            return render(request, "laporan/forbidden.html", status=403)
        return view(request, *args, **kwargs)
    return wrapped
