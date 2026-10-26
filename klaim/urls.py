"""URL routes for the claim module (mounted at /klaim/)."""
from django.urls import path

from . import views

app_name = "klaim"

urlpatterns = [
    # Recipient
    path("", views.claim_list, name="claim_list"),
    path("create/<int:donation_id>/", views.claim_create, name="claim_create"),
    path("<int:pk>/", views.claim_detail, name="claim_detail"),
    path("<int:pk>/cancel/", views.claim_cancel, name="claim_cancel"),
    # Donor
    path("incoming/", views.incoming_claim_list, name="incoming_claim_list"),
    path("incoming/verify/", views.claim_verify_code, name="claim_verify_code"),
    path("<int:pk>/approve/", views.claim_approve, name="claim_approve"),
    path("<int:pk>/reject/", views.claim_reject, name="claim_reject"),
    path("<int:pk>/delete/", views.claim_delete, name="claim_delete"),
]