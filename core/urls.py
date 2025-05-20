from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.views import CreateCheckoutSessionView, StripeWebhookView, PlanListView

router = DefaultRouter()

urlpatterns = [
    path('payments/create-checkout-session/', CreateCheckoutSessionView.as_view(), name='create_checkout_session'),
    path('payments/webhook/stripe/', StripeWebhookView.as_view(), name='stripe_webhook'),
    path('plans/', PlanListView.as_view(), name='plan-list'),
    path('', include(router.urls)),
]
