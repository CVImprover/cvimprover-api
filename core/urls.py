# core/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.views import (
    CreateCheckoutSessionView, 
    StripeWebhookView, 
    PlanListView, 
    CreateBillingPortalSessionView, 
    VerifyCheckoutSessionView, 
    HealthCheckView,
    RateLimitStatusView  # Add this import
)

router = DefaultRouter()

urlpatterns = [
    # Health check
    path('health/', HealthCheckView.as_view(), name='health_check'),
    
    # Payment endpoints
    path('payments/create-checkout-session/', CreateCheckoutSessionView.as_view(), name='create_checkout_session'),
    path('payments/webhook/stripe/', StripeWebhookView.as_view(), name='stripe_webhook'),
    path('payments/verify-session/', VerifyCheckoutSessionView.as_view(), name='verify_checkout_session'),
    
    # Plan endpoints
    path('plans/', PlanListView.as_view(), name='plan-list'),
    
    # Billing portal
    path('billing/portal/', CreateBillingPortalSessionView.as_view(), name='billing_portal'),
    
    # Rate limit status - NEW ENDPOINT
    path('rate-limits/status/', RateLimitStatusView.as_view(), name='rate_limit_status'),
    
    # Router URLs
    path('', include(router.urls)),
]