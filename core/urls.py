from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.views import CreateCheckoutSessionView, StripeWebhookView, PlanListView, CreateBillingPortalSessionView, VerifyCheckoutSessionView

router = DefaultRouter()

urlpatterns = [
    path('payments/create-checkout-session/', CreateCheckoutSessionView.as_view(), name='create_checkout_session'),
    path('payments/webhook/stripe/', StripeWebhookView.as_view(), name='stripe_webhook'),
    path('payments/verify-session/', VerifyCheckoutSessionView.as_view(), name='verify_checkout_session'),
    path('plans/', PlanListView.as_view(), name='plan-list'),

    path('billing/portal/', CreateBillingPortalSessionView.as_view(), name='billing_portal'),    
    path('', include(router.urls)),
]
