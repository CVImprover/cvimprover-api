from rest_framework import serializers
from .models import User, Plan
from dj_rest_auth.serializers import UserDetailsSerializer
from .validators import validate_email_with_suggestions
from django.core.exceptions import ValidationError as DjangoValidationError
from dj_rest_auth.registration.serializers import RegisterSerializer
from django.conf import settings
from django.core.cache import cache
from datetime import datetime

import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

class PlanSerializer(serializers.ModelSerializer):
    monthly_price = serializers.SerializerMethodField()
    yearly_price = serializers.SerializerMethodField()
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = ['id', 'name', 'description', 'monthly_price', 'yearly_price', 'is_current']

    def get_monthly_price(self, obj):
        return self.get_price_details(obj.stripe_price_id_monthly)

    def get_yearly_price(self, obj):
        return self.get_price_details(obj.stripe_price_id_yearly)

    def get_price_details(self, price_id):
        if not price_id:
            return {
                "amount": 0,
                "currency": "USD",
                "interval": 'None'
            }

        cache_key = f'stripe_price_{price_id}'
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            price = stripe.Price.retrieve(price_id)
            data = {
                'amount': price.unit_amount / 100,
                'currency': price.currency.upper(),
                'interval': price.recurring.interval,
            }
            cache.set(cache_key, data, timeout=60 * 120)
            return data
        except Exception:
            return None
        
    def get_is_current(self, obj):
        user = self.context['request'].user
        if user.is_authenticated and user.plan_id == obj.id:
            return True
        return False

import logging
logger = logging.getLogger(__name__)

class CustomUserDetailsSerializer(UserDetailsSerializer):
    email = serializers.EmailField(required=False)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    plan = PlanSerializer(read_only=True)
    stripe_subscription_id = serializers.CharField(read_only=True)
    stripe_customer_id = serializers.CharField(read_only=True)
    stripe_subscription_status = serializers.CharField(read_only=True)
    subscription_renewal_date = serializers.SerializerMethodField()
    subscription_interval = serializers.SerializerMethodField()    

    class Meta(UserDetailsSerializer.Meta):
        model = User
        fields = UserDetailsSerializer.Meta.fields + (
            'date_of_birth',
            'plan',
            'stripe_subscription_id',
            'stripe_subscription_status',
            'stripe_customer_id',
            'subscription_renewal_date',
            'subscription_interval',            
        )

    def _get_subscription_info(self, obj):
        if not obj.stripe_subscription_id:
            return None

        cache_key = f"stripe_subscription_info_{obj.stripe_subscription_id}"
        cached_info = cache.get(cache_key)
        if cached_info:
            return cached_info

        try:
            subscription = stripe.Subscription.retrieve(obj.stripe_subscription_id)
            item = subscription["items"]["data"][0]

            current_period_end = item["current_period_end"]
            interval = item["price"]["recurring"]["interval"]

            dt = datetime.fromtimestamp(current_period_end)
            info = {
                "renewal_date": dt,
                "interval": interval
            }

            cache.set(cache_key, info, timeout=60 * 120)
            return info
        except Exception as e:
            logger.error(f"❌ Error fetching subscription info: {e}")
            return None        

    def get_subscription_renewal_date(self, obj):
        info = self._get_subscription_info(obj)
        return info["renewal_date"] if info else None

    def get_subscription_interval(self, obj):
        info = self._get_subscription_info(obj)
        return info["interval"] if info else None
    
    def validate_email(self, value):
        """Enhanced email validation with typo detection and disposable email blocking."""
        if value:
            try:
                # Use our enhanced email validator
                validated_email = validate_email_with_suggestions(value)
                
                # Check if email already exists for other users (excluding current user if updating)
                if self.instance:
                    # Updating existing user - exclude current user from uniqueness check
                    if User.objects.filter(email=value).exclude(pk=self.instance.pk).exists():
                        raise serializers.ValidationError("A user with this email address already exists.")
                else:
                    # Creating new user - check if email exists
                    if User.objects.filter(email=value).exists():
                        raise serializers.ValidationError("A user with this email address already exists.")
                
                return validated_email
            except DjangoValidationError as e:
                # Convert Django ValidationError to DRF ValidationError
                raise serializers.ValidationError(str(e))
        return value
