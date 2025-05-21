from rest_framework import viewsets
from dj_rest_auth.views import UserDetailsView
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import BaseAuthentication
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiExample
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import get_user_model
from .serializers import CustomUserDetailsSerializer, PlanSerializer
from .models import Plan
from datetime import datetime
from django.utils import timezone
from dj_rest_auth.registration.views import SocialLoginView
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter

import stripe
import logging

logger = logging.getLogger(__name__)

User = get_user_model()
stripe.api_key = settings.STRIPE_SECRET_KEY
FRONTEND_URL = settings.FRONTEND_URL
if not FRONTEND_URL.startswith(('http://', 'https://')):
    if 'localhost' in FRONTEND_URL or '127.0.0.1' in FRONTEND_URL:
        FRONTEND_URL = f'http://{FRONTEND_URL}'
    else:
        FRONTEND_URL = f'https://{FRONTEND_URL}'
        
class CustomUserDetailsView(UserDetailsView):
    serializer_class = CustomUserDetailsSerializer
    permission_classes = [IsAuthenticated]

class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter

class CreateCheckoutSessionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'plan_id': {'type': 'integer'},
                    'billing': {'type': 'string', 'enum': ['monthly', 'yearly']},
                },
                'required': ['plan_id', 'billing'],
            }
        },
        responses={
            200: {'type': 'object', 'properties': {'url': {'type': 'string'}}},
            400: {'type': 'object', 'properties': {'error': {'type': 'string'}}},
            404: {'type': 'object', 'properties': {'error': {'type': 'string'}}},
        },
        examples=[
            OpenApiExample(
                name="Basic monthly plan",
                value={"plan_id": 2, "billing": "monthly"},
                request_only=True,
                response_only=False,
            )
        ]
    )
    def post(self, request):
        data = request.data
        plan_id = data.get('plan_id')
        billing_cycle = data.get('billing')

        if not plan_id or not billing_cycle:
            return Response({'error': 'Missing plan_id or billing'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            plan = Plan.objects.get(id=plan_id)
            price_id = (
                plan.stripe_price_id_monthly if billing_cycle == 'monthly'
                else plan.stripe_price_id_yearly
            )

            if not price_id:
                return Response({'error': 'Plan does not support that billing cycle.'}, status=status.HTTP_400_BAD_REQUEST)

            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                mode='subscription',
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                success_url=f'{FRONTEND_URL}/payments/success?session_id={{CHECKOUT_SESSION_ID}}',
                cancel_url=f'{FRONTEND_URL}/payments/cancelled',
                customer_email=request.user.email,
                metadata={
                    'plan_id': str(plan.id),
                }
            )

            return Response({'url': session.url})
        
        except Plan.DoesNotExist:
            return Response({'error': 'Plan not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class StripeWebhookAuthentication(BaseAuthentication):
    def authenticate(self, request):
        return None


class StripeWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [StripeWebhookAuthentication]

    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        webhook_secret = settings.STRIPE_WEBHOOK_SECRET

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except (ValueError, stripe.error.SignatureVerificationError):
            return HttpResponse(status=400)

        event_type = event["type"]

        if event_type == "checkout.session.completed":
            session = event["data"]["object"]
            email = session.get("customer_email")
            subscription_id = session.get("subscription")
            customer_id = session.get("customer")
            plan_id = session.get("metadata", {}).get("plan_id")
            

            try:
                user = User.objects.get(email=email)

                if plan_id:
                    plan = Plan.objects.get(id=plan_id)
                    user.plan = plan

                if subscription_id:
                    try:
                        subscription = stripe.Subscription.retrieve(subscription_id)
                        user.stripe_subscription_id = subscription_id
                        user.stripe_subscription_status = "active"

                        current_period_end = subscription.get("current_period_end")
                        if current_period_end:
                            user.subscription_renewal_date = datetime.fromtimestamp(current_period_end, tz=timezone.utc)
                    except Exception as sub_err:
                        logger.error(f"❌ Failed to retrieve subscription {subscription_id}: {sub_err}")   

                if customer_id:
                    user.stripe_customer_id = customer_id                            

                user.save()
                logger.info(f"✅ Updated user {user.email} to plan {user.plan} with subscription {subscription_id}")
            except Exception as e:
                logger.error(f"❌ Failed to update user after checkout: {e}")

        elif event_type == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            subscription_id = subscription["id"]

            try:
                user = User.objects.get(stripe_subscription_id=subscription_id)
                user.plan = Plan.objects.get(name="Free")
                user.stripe_subscription_status = "canceled"
                user.save()
                logger.info(f"⚠️ Subscription {subscription_id} canceled. Downgraded user {user.email} to Free.")
            except Exception as e:
                logger.error(f"❌ Failed to handle subscription cancellation: {e}")

        elif event_type == "customer.subscription.updated":
            subscription = event["data"]["object"]
            subscription_id = subscription["id"]
            status = subscription["status"]

            try:
                user = User.objects.get(stripe_subscription_id=subscription_id)
                user.stripe_subscription_status = status

                current_period_end = subscription.get("current_period_end")
                if current_period_end:
                    user.subscription_renewal_date = datetime.fromtimestamp(current_period_end, tz=timezone.utc)

                # Optional: update plan if changed
                price_id = subscription["items"]["data"][0]["price"]["id"]
                plan = Plan.objects.filter(
                    stripe_price_id_monthly=price_id
                ).first() or Plan.objects.filter(
                    stripe_price_id_yearly=price_id
                ).first()

                if plan:
                    user.plan = plan
                user.save()
                logger.info(f"🔄 Synced subscription update for {user.email} – {status}")
            except User.DoesNotExist:
                logger.error(f"❌ No user found with subscription ID {subscription_id}")               

        return HttpResponse(status=200)
    


@extend_schema(
    responses={
        200: PlanSerializer(many=True),
    },
    examples=[
        OpenApiExample(
            name="Plan list with current plan marked",
            value=[
                {
                    "id": 2,
                    "name": "Basic",
                    "description": "",
                    "monthly_price": {
                        "amount": 5,
                        "currency": "USD",
                        "interval": "month"
                    },
                    "yearly_price": {
                        "amount": 55,
                        "currency": "USD",
                        "interval": "year"
                    },
                    "is_current": True
                },
                {
                    "id": 1,
                    "name": "Free",
                    "description": "",
                    "monthly_price": None,
                    "yearly_price": None,
                    "is_current": False
                }
            ],
            response_only=True
        )
    ]
)
class PlanListView(ListAPIView):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        billing = self.request.query_params.get('billing')
        queryset = Plan.objects.all()

        if billing == 'monthly':
            queryset = queryset.exclude(stripe_price_id_monthly__isnull=True).exclude(stripe_price_id_monthly='')
        elif billing == 'yearly':
            queryset = queryset.exclude(stripe_price_id_yearly__isnull=True).exclude(stripe_price_id_yearly='')

        return queryset    
    
class CreateBillingPortalSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user.stripe_customer_id:
            return Response({"error": "No Stripe customer ID found."}, status=400)

        try:
            session = stripe.billing_portal.Session.create(
                customer=user.stripe_customer_id,
                return_url=f"https://{settings.FRONTEND_URL}/profile"
            )
            return Response({"url": session.url})
        except Exception as e:
            return Response({"error": str(e)}, status=500)    