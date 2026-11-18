"""URL routes for the claim module (mounted at /klaim/)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api, views

app_name = "klaim"

api_router = DefaultRouter()
api_router.register("api/claim", api.ClaimViewSet, basename="api-claim")

urlpatterns = [
    # Recipient
    path("", views.claim_list, name="claim_list"),
    path("create/<int:donation_id>/", views.claim_create, name="claim_create"),
    path("<int:pk>/", views.claim_detail, name="claim_detail"),
    path("<int:pk>/cancel/", views.claim_cancel, name="claim_cancel"),
    path("check/<int:donation_id>/", views.claim_check, name="claim_check"),
    # Donor
    path("incoming/", views.incoming_claim_list, name="incoming_claim_list"),
    path("<int:pk>/verify/", views.claim_verify_code, name="claim_verify_code"),
    path("", include(api_router.urls)),
]