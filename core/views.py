from rest_framework import viewsets
from dj_rest_auth.views import UserDetailsView
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import BaseAuthentication
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import get_user_model
from .serializers import CustomUserDetailsSerializer, PlanSerializer
from .models import Plan
from datetime import datetime
from django.utils import timezone
from django.core.cache import cache
from core.throttling import get_rate_limit_status
from dj_rest_auth.registration.views import SocialLoginView
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from django.db import connection
from redis import Redis
from openai import OpenAI
import os
import time

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
    """Enhanced user details view with caching"""
    serializer_class = CustomUserDetailsSerializer
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        """Get user details with caching"""
        cache_key = f'user_profile_{request.user.id}'
        
        # Try cache first
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug(f"📦 Returning cached user profile for user {request.user.id}")
            return Response(cached_data)
        
        # Get fresh data
        response = super().get(request, *args, **kwargs)
        
        if response.status_code == 200:
            # Cache successful responses for 15 minutes
            cache.set(cache_key, response.data, timeout=60 * 15)
            logger.info(f"💾 Cached user profile for user {request.user.id}")
        
        return response

    def patch(self, request, *args, **kwargs):
        """Update user details and invalidate cache"""
        response = super().patch(request, *args, **kwargs)
        
        if response.status_code == 200:
            # Invalidate cache after successful update
            cache_key = f'user_profile_{request.user.id}'
            cache.delete(cache_key)
            logger.info(f"🗑️ Invalidated user profile cache for user {request.user.id}")
        
        return response

    def put(self, request, *args, **kwargs):
        """Update user details and invalidate cache"""
        response = super().put(request, *args, **kwargs)
        
        if response.status_code == 200:
            # Invalidate cache after successful update
            cache_key = f'user_profile_{request.user.id}'
            cache.delete(cache_key)
            logger.info(f"🗑️ Invalidated user profile cache for user {request.user.id}")
        
        return response

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
        user_email = request.user.email

        logger.info(f"Checkout session creation requested - User: {user_email}, Plan ID: {plan_id}, Billing: {billing_cycle}")

        if not plan_id or not billing_cycle:
            logger.warning(f"Invalid checkout request - Missing plan_id or billing from user: {user_email}")
            return Response({'error': 'Missing plan_id or billing'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            plan = Plan.objects.get(id=plan_id)
            price_id = (
                plan.stripe_price_id_monthly if billing_cycle == 'monthly'
                else plan.stripe_price_id_yearly
            )

            if not price_id:
                logger.warning(f"Plan {plan.name} does not support {billing_cycle} billing - User: {user_email}")
                return Response({'error': 'Plan does not support that billing cycle.'}, status=status.HTTP_400_BAD_REQUEST)

            logger.debug(f"Creating Stripe checkout session - Price ID: {price_id}, User: {user_email}")
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
            logger.info(f"Stripe checkout session created successfully - Session ID: {session.id}, User: {user_email}, Plan: {plan.name}")
            return Response({'url': session.url})
        
        except Plan.DoesNotExist:
            logger.error(f"Plan not found - Plan ID: {plan_id}, User: {user_email}")
            return Response({'error': 'Plan not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Unexpected error during checkout - User: {user_email}, Error: {str(e)}", exc_info=True)
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
        logger.debug("Stripe webhook received")

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
            logger.info(f"Stripe webhook verified - Event type: {event['type']}, Event ID: {event['id']}")
        except (ValueError, stripe.error.SignatureVerificationError):
            logger.error(f"Webhook verification failed - Invalid payload or signature")
            return HttpResponse(status=400)

        event_type = event["type"]

        if event_type == "checkout.session.completed":
            session = event["data"]["object"]
            email = session.get("customer_email")
            subscription_id = session.get("subscription")
            customer_id = session.get("customer")
            plan_id = session.get("metadata", {}).get("plan_id")
            logger.info(f"Processing checkout.session.completed - Email: {email}, Subscription ID: {subscription_id}, Plan ID: {plan_id}")

            try:
                user = User.objects.get(email=email)
                logger.debug(f"User found: {user.email}")

                if plan_id:
                    plan = Plan.objects.get(id=plan_id)
                    user.plan = plan
                    logger.debug(f"Plan assigned: {plan.name}")

                if subscription_id:
                    try:
                        subscription = stripe.Subscription.retrieve(subscription_id)
                        user.stripe_subscription_id = subscription_id
                        user.stripe_subscription_status = "active"

                        current_period_end = subscription.get("current_period_end")
                        if current_period_end:
                            user.subscription_renewal_date = datetime.fromtimestamp(current_period_end, tz=timezone.utc)
                            logger.debug(f"Subscription renewal date set: {user.subscription_renewal_date}")
                    except Exception as sub_err:
                        logger.error(f"❌ Failed to retrieve subscription {subscription_id}: {sub_err}")   

                if customer_id:
                    user.stripe_customer_id = customer_id
                    logger.debug(f"Stripe customer ID saved: {customer_id}")

                user.save()
                logger.info(f"✅ Updated user {user.email} to plan {user.plan} with subscription {subscription_id}")
            except Exception as e:
                logger.error(f"❌ Failed to update user after checkout: {e}")

        elif event_type == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            subscription_id = subscription["id"]

            logger.warning(f"⚠ Processing subscription cancellation - Subscription ID: {subscription_id}")

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

            logger.info(f"🔄 Processing subscription update - Subscription ID: {subscription_id}, Status: {status}")

            try:
                user = User.objects.get(stripe_subscription_id=subscription_id)
                logger.debug(f"👤 User found: {user.email}")
                user.stripe_subscription_status = status

                current_period_end = subscription.get("current_period_end")
                if current_period_end:
                    user.subscription_renewal_date = datetime.fromtimestamp(current_period_end, tz=timezone.utc)
                    logger.debug(f"📅 Updated renewal date: {user.subscription_renewal_date}")

                price_id = subscription["items"]["data"][0]["price"]["id"]
                plan = Plan.objects.filter(
                    stripe_price_id_monthly=price_id
                ).first() or Plan.objects.filter(
                    stripe_price_id_yearly=price_id
                ).first()

                if plan:
                    user.plan = plan
                    logger.debug(f"📦 Plan updated to: {plan.name}")
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
            logger.debug(f"Filtered to {queryset.count()} monthly plans")
        elif billing == 'yearly':
            queryset = queryset.exclude(stripe_price_id_yearly__isnull=True).exclude(stripe_price_id_yearly='')
            logger.debug(f"Filtered to {queryset.count()} yearly plans")

        return queryset    

    def list(self, request, *args, **kwargs):
        """Enhanced list method with intelligent caching"""
        billing = request.query_params.get('billing', 'all')
        user_id = request.user.id if request.user.is_authenticated else 'anonymous'
        
        # Create cache key that includes billing filter and user context
        cache_key = f'plans_list_{billing}_{user_id}'
        
        # Try to get cached response
        cached_response = cache.get(cache_key)
        if cached_response:
            logger.debug(f"📦 Returning cached plans list for billing={billing}, user={user_id}")
            return Response(cached_response)
        
        # Get fresh data
        response = super().list(request, *args, **kwargs)
        
        # Cache the response data for 24 hours
        cache.set(cache_key, response.data, timeout=60 * 60 * 24)
        logger.info(f"💾 Cached plans list for billing={billing}, user={user_id}")
        
        return response
    
class CreateBillingPortalSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        logger.info(f"🏦 Billing portal session requested - User: {user.email}")
        if not user.stripe_customer_id:
            logger.warning(f"⚠️ Billing portal access denied - No Stripe customer ID for user: {user.email}")
            return Response({"error": "No Stripe customer ID found."}, status=400)

        try:
            logger.debug(f"🔄 Creating billing portal session - Customer ID: {user.stripe_customer_id}")
            session = stripe.billing_portal.Session.create(
                customer=user.stripe_customer_id,
                return_url=f"https://{settings.FRONTEND_URL}/profile"
            )
            logger.info(f"✅ Billing portal session created - User: {user.email}")
            return Response({"url": session.url})
        except Exception as e:
            logger.error(f"❌ Error creating billing portal session - User: {user.email}, Error: {str(e)}",
                         exc_info=True)
            return Response({"error": str(e)}, status=500)    
        

class VerifyCheckoutSessionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(name="session_id", required=True, type=str, location=OpenApiParameter.QUERY)
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'subscription': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'integer'},
                            'plan_name': {'type': 'string'},
                            'status': {'type': 'string'},
                            'current_period_start': {'type': 'string', 'format': 'date-time'},
                            'current_period_end': {'type': 'string', 'format': 'date-time'},
                        }
                    }
                }
            },
            400: {'type': 'object', 'properties': {'error': {'type': 'string'}}},
            500: {'type': 'object', 'properties': {'error': {'type': 'string'}}},
        },
        examples=[
            OpenApiExample(
                name="Valid session verification",
                value={"session_id": "cs_test_ABC123"},
                request_only=True
            )
        ]
    )
    def get(self, request):
        session_id = request.query_params.get("session_id")
        logger.info(f"🔍 Checkout session verification requested - User: {request.user.email}, Session ID: {session_id}")
        if not session_id:
            logger.warning(f"⚠️ Session verification failed - Missing session_id for user: {request.user.email}")
            return Response({"error": "Missing session_id"}, status=status.HTTP_400_BAD_REQUEST)

        cache_key = f"stripe_verified_session_{session_id}"
        cached = cache.get(cache_key)
        if cached:
            logger.debug(f"💾 Returning cached session verification - Session ID: {session_id}")
            return Response(cached)

        try:
            logger.debug(f"🔄 Retrieving Stripe checkout session - Session ID: {session_id}")
            session = stripe.checkout.Session.retrieve(
                session_id,
                expand=["subscription"]
            )
            subscription = session.get("subscription")
            items = subscription.get("items", {}).get("data", [])
            print(f"subscription: {subscription}")
            if not subscription:
                logger.warning(f"⚠️ No subscription found in session - User: {request.user.email}, Session ID: {session_id}")
                return Response({"error": "No subscription found in session."}, status=status.HTTP_400_BAD_REQUEST)

            if not items:
                logger.warning(f"⚠️ Subscription items missing - User: {request.user.email}, Session ID: {session_id}")
                return Response({"error": "Subscription items missing."}, status=status.HTTP_400_BAD_REQUEST)
            
            user = request.user
            sub_id = subscription["id"]
            status_str = subscription["status"]
            item = items[0]
            period_start_ts = item.get("current_period_start")
            period_end_ts = item.get("current_period_end")
            if not period_start_ts or not period_end_ts:
                logger.warning(f"⚠️ Subscription period not available - User: {user.email}, Subscription ID: {sub_id}")
                return Response({"error": "Subscription period not available yet."}, status=status.HTTP_400_BAD_REQUEST)

            period_start = datetime.fromtimestamp(period_start_ts).isoformat()
            period_end = datetime.fromtimestamp(period_end_ts).isoformat()            
            plan_id = session["metadata"].get("plan_id")

            plan = None
            if plan_id:
                try:
                    plan = Plan.objects.get(id=plan_id)
                    user.plan = plan
                    logger.debug(f"📦 Plan assigned from metadata: {plan.name}")
                except Plan.DoesNotExist:
                    logger.warning(f"⚠️ Plan with ID {plan_id} not found.")
            user.stripe_subscription_id = sub_id
            user.stripe_subscription_status = status_str
            user.save()
            logger.info(
                f"✅ Session verified and user updated - User: {user.email}, Plan: {plan.name if plan else 'Unknown'}, Status: {status_str}")

            response_data = {
                "success": True,
                "subscription": {
                    "id": plan.id if plan else None,
                    "plan_name": plan.name if plan else "Unknown",
                    "status": status_str,
                    "current_period_start": period_start,
                    "current_period_end": period_end
                }
            }

            cache.set(cache_key, response_data, timeout=60 * 60)  # 1 hour
            logger.debug(f"💾 Session verification result cached - Session ID: {session_id}")
            return Response(response_data)

        except Exception as e:
            logger.error(f"❌ Error verifying Stripe session {session_id}: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    responses={
        200: {
            'type': 'object',
            'properties': {
                'overall': {'type': 'string'},
                'services': {
                    'type': 'object',
                    'properties': {
                        'db': {'type': 'string'},
                        'redis': {'type': 'string'},
                        'openai': {'type': 'string'},
                    }
                }
            }
        },
        503: {
            'type': 'object',
            'properties': {
                'overall': {'type': 'string'},
                'services': {
                    'type': 'object',
                    'properties': {
                        'db': {'type': 'string'},
                        'redis': {'type': 'string'},
                        'openai': {'type': 'string'},
                    }
                }
            }
        },
    },
    examples=[
        OpenApiExample(
            name="Healthy services",
            value={
                "overall": "healthy",
                "services": {
                    "db": "healthy",
                    "redis": "healthy",
                    "openai": "healthy"
                }
            },
            response_only=True
        ),
        OpenApiExample(
            name="OpenAI skipped",
            value={
                "overall": "healthy",
                "services": {
                    "db": "healthy",
                    "redis": "healthy",
                    "openai": "skipped"
                }
            },
            response_only=True
        )
    ]
)
class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        """Health check with caching to reduce load on services"""
        cache_key = 'health_check_status'
        
        # Try cache first (30-second TTL)
        cached_status = cache.get(cache_key)
        if cached_status:
            logger.debug("📦 Returning cached health check status")
            return Response(cached_status['data'], status=cached_status['http_status'])
        
        logger.debug("🔍 Health check initiated")
        services = {}

        # Check DB
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            services['db'] = 'healthy'
            logger.debug("✅ Database health check: healthy")
        except Exception as e:
            logger.error(f"DB health check failed: {e}")
            services['db'] = 'unhealthy'

        # Check Redis
        try:
            redis_client = Redis.from_url(settings.CACHE_URL)
            redis_client.ping()
            services['redis'] = 'healthy'
            logger.debug("✅ Redis health check: healthy")
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            services['redis'] = 'unhealthy'

        # Check OpenAI (optional)
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                client = OpenAI(api_key=api_key)
                client.models.list()  # Lightweight check
                services['openai'] = 'healthy'
                logger.debug("✅ OpenAI health check: healthy")
            except Exception as e:
                logger.error(f"OpenAI health check failed: {e}")
                services['openai'] = 'unhealthy'

        else:
            services['openai'] = 'skipped'

        # Determine overall status
        overall = 'healthy' if services['db'] == 'healthy' and services['redis'] == 'healthy' else 'unhealthy'
        http_status = status.HTTP_200_OK if overall == 'healthy' else status.HTTP_503_SERVICE_UNAVAILABLE

        response_data = {
            'overall': overall,
            'services': services
        }
        
        # Cache the result for 30 seconds
        cache_data = {
            'data': response_data,
            'http_status': http_status
        }
        cache.set(cache_key, cache_data, timeout=30)
        logger.info(f"💾 Cached health check status: {overall}")

        return Response(response_data, status=http_status)


@extend_schema(
    responses={
        200: {
            'type': 'object',
            'properties': {
                'user': {
                    'type': 'object',
                    'properties': {
                        'username': {'type': 'string'},
                        'email': {'type': 'string'},
                        'plan': {'type': 'string'},
                    }
                },
                'rate_limits': {
                    'type': 'object',
                    'properties': {
                        'ai_responses': {
                            'type': 'object',
                            'properties': {
                                'limit': {'type': 'integer'},
                                'used': {'type': 'integer'},
                                'remaining': {'type': 'integer'},
                                'reset_at': {'type': 'string', 'format': 'date-time'},
                                'percentage_used': {'type': 'number'},
                                'status': {'type': 'string', 'enum': ['healthy', 'moderate', 'warning', 'critical']},
                            }
                        },
                        'questionnaires': {
                            'type': 'object',
                            'properties': {
                                'limit': {'type': 'integer'},
                                'used': {'type': 'integer'},
                                'remaining': {'type': 'integer'},
                                'reset_at': {'type': 'string', 'format': 'date-time'},
                                'percentage_used': {'type': 'number'},
                                'status': {'type': 'string'},
                            }
                        },
                        'api_calls': {
                            'type': 'object',
                            'properties': {
                                'limit': {'type': 'integer'},
                                'used': {'type': 'integer'},
                                'remaining': {'type': 'integer'},
                                'reset_at': {'type': 'string', 'format': 'date-time'},
                                'percentage_used': {'type': 'number'},
                                'status': {'type': 'string'},
                            }
                        },
                    }
                },
                'upgrade_recommendation': {
                    'type': 'object',
                    'properties': {
                        'should_upgrade': {'type': 'boolean'},
                        'reason': {'type': 'string'},
                        'recommended_plan': {'type': 'string'},
                        'upgrade_url': {'type': 'string'},
                        'high_usage_scopes': {
                            'type': 'array',
                            'items': {'type': 'string'}
                        }
                    }
                }
            }
        }
    },
    examples=[
        OpenApiExample(
            name="Free plan user with moderate usage",
            value={
                "user": {
                    "username": "john_doe",
                    "email": "john@example.com",
                    "plan": "Free"
                },
                "rate_limits": {
                    "ai_responses": {
                        "limit": 3,
                        "used": 2,
                        "remaining": 1,
                        "reset_at": "2025-10-05T00:00:00Z",
                        "percentage_used": 66.67,
                        "status": "moderate"
                    },
                    "questionnaires": {
                        "limit": 5,
                        "used": 1,
                        "remaining": 4,
                        "reset_at": "2025-10-05T00:00:00Z",
                        "percentage_used": 20.0,
                        "status": "healthy"
                    },
                    "api_calls": {
                        "limit": 100,
                        "used": 45,
                        "remaining": 55,
                        "reset_at": "2025-10-05T01:00:00Z",
                        "percentage_used": 45.0,
                        "status": "healthy"
                    }
                },
                "upgrade_recommendation": {
                    "should_upgrade": False,
                    "reason": "Your usage is within comfortable limits",
                    "recommended_plan": None,
                    "upgrade_url": None
                }
            },
            response_only=True
        ),
        OpenApiExample(
            name="User approaching limits - upgrade suggested",
            value={
                "user": {
                    "username": "jane_smith",
                    "email": "jane@example.com",
                    "plan": "Basic"
                },
                "rate_limits": {
                    "ai_responses": {
                        "limit": 20,
                        "used": 18,
                        "remaining": 2,
                        "reset_at": "2025-10-05T00:00:00Z",
                        "percentage_used": 90.0,
                        "status": "critical"
                    },
                    "questionnaires": {
                        "limit": 50,
                        "used": 35,
                        "remaining": 15,
                        "reset_at": "2025-10-05T00:00:00Z",
                        "percentage_used": 70.0,
                        "status": "warning"
                    },
                    "api_calls": {
                        "limit": 300,
                        "used": 120,
                        "remaining": 180,
                        "reset_at": "2025-10-05T01:00:00Z",
                        "percentage_used": 40.0,
                        "status": "healthy"
                    }
                },
                "upgrade_recommendation": {
                    "should_upgrade": True,
                    "reason": "You are approaching limits on: ai_responses, questionnaires",
                    "recommended_plan": "Pro",
                    "upgrade_url": "/core/plans/",
                    "high_usage_scopes": ["ai_responses", "questionnaires"]
                }
            },
            response_only=True
        )
    ]
)
class RateLimitStatusView(APIView):
    """
    Get detailed rate limit status for the authenticated user.
    Shows current usage, remaining quota, and upgrade recommendations.
    Enhanced with intelligent caching.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Create time-based cache key (changes every minute)
        current_minute = int(time.time() / 60)
        cache_key = f'rate_limit_status_{user.id}_{current_minute}'
        
        # Try cache first
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug(f"📦 Returning cached rate limit status for user {user.id}")
            return Response(cached_data)
        
        logger.info(f"📊 Rate limit status requested - User: {user.email}")
        
        scopes = ['ai_responses', 'questionnaires', 'api_calls']
        rate_limits = {}
        
        for scope in scopes:
            status_data = get_rate_limit_status(user, scope)
            if status_data:
                percentage_used = (
                    (status_data['used'] / status_data['limit'] * 100) 
                    if status_data['limit'] > 0 else 0
                )
                
                rate_limits[scope] = {
                    'limit': status_data['limit'],
                    'used': status_data['used'],
                    'remaining': status_data['remaining'],
                    'reset_at': status_data['reset_at'],
                    'percentage_used': round(percentage_used, 2),
                    'status': self._get_status_label(percentage_used)
                }
                
                logger.debug(
                    f"Rate limit for {scope} - User: {user.email}, "
                    f"Used: {status_data['used']}/{status_data['limit']}, "
                    f"Status: {self._get_status_label(percentage_used)}"
                )
        
        # Determine if user should upgrade
        upgrade_recommendation = self._get_upgrade_recommendation(user, rate_limits)
        
        response_data = {
            'user': {
                'username': user.username,
                'email': user.email,
                'plan': user.plan.name if user.plan else 'Free',
            },
            'rate_limits': rate_limits,
            'upgrade_recommendation': upgrade_recommendation
        }
        
        # Cache for 1 minute (balances freshness with performance)
        cache.set(cache_key, response_data, timeout=60)
        logger.info(f"💾 Cached rate limit status for user {user.id}")
        
        logger.info(
            f"✅ Rate limit status returned - User: {user.email}, "
            f"Plan: {user.plan.name if user.plan else 'Free'}, "
            f"Should upgrade: {upgrade_recommendation['should_upgrade']}"
        )
        
        return Response(response_data)
    
    def _get_status_label(self, percentage):
        """Get a human-readable status label based on usage percentage."""
        if percentage >= 90:
            return 'critical'
        elif percentage >= 70:
            return 'warning'
        elif percentage >= 50:
            return 'moderate'
        else:
            return 'healthy'
    
    def _get_upgrade_recommendation(self, user, rate_limits):
        """
        Determine if user should upgrade their plan based on usage patterns.
        """
        current_plan = user.plan.name if user.plan else 'Free'
        
        # Check if any limit is close to being exceeded
        high_usage_scopes = []
        for scope, data in rate_limits.items():
            if data['percentage_used'] >= 80:
                high_usage_scopes.append(scope)
        
        if not high_usage_scopes:
            logger.debug(f"No upgrade needed for user {user.email} - all usage below 80%")
            return {
                'should_upgrade': False,
                'reason': 'Your usage is within comfortable limits',
                'recommended_plan': None,
                'upgrade_url': None
            }
        
        # Recommend next tier
        plan_hierarchy = ['Free', 'Basic', 'Pro', 'Premium']
        current_index = plan_hierarchy.index(current_plan) if current_plan in plan_hierarchy else 0
        
        if current_index < len(plan_hierarchy) - 1:
            recommended_plan = plan_hierarchy[current_index + 1]
            logger.info(
                f"💡 Upgrade recommended for user {user.email} - "
                f"From {current_plan} to {recommended_plan}, "
                f"High usage scopes: {', '.join(high_usage_scopes)}"
            )
            return {
                'should_upgrade': True,
                'reason': f'You are approaching limits on: {", ".join(high_usage_scopes)}',
                'recommended_plan': recommended_plan,
                'upgrade_url': '/core/plans/',
                'high_usage_scopes': high_usage_scopes
            }
        
        logger.debug(f"User {user.email} is on highest plan (Premium) - no upgrade available")
        return {
            'should_upgrade': False,
            'reason': 'You are on the highest plan',
            'recommended_plan': None,
            'upgrade_url': None
        }