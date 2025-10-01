from django.db import models
from django.core.exceptions import ValidationError
import stripe

class Plan(models.Model):
    name = models.CharField(max_length=50, unique=True)
    stripe_price_id_monthly = models.CharField(max_length=100, blank=True, null=True)
    stripe_price_id_yearly = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    order = models.PositiveIntegerField(default=10)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def clean(self):
        errors = {}

        # 1. Ensure at least one price ID is provided
        if not self.stripe_price_id_monthly and not self.stripe_price_id_yearly:
            errors['stripe_price_id_monthly'] = "At least one Stripe Price ID (monthly or yearly) must be provided."

        # 2. Validate monthly/yearly price IDs with Stripe
        stripe.api_key = "YOUR_STRIPE_SECRET_KEY"  # ضع هنا الـ key الخاص بك أو من settings
        for field, price_id in {
            'stripe_price_id_monthly': self.stripe_price_id_monthly,
            'stripe_price_id_yearly': self.stripe_price_id_yearly,
        }.items():
            if price_id:
                try:
                    stripe.Price.retrieve(price_id)
                except Exception:
                    errors[field] = f"Invalid Stripe Price ID: {price_id}"

        # 3. Validate unique order
        if Plan.objects.exclude(pk=self.pk).filter(order=self.order).exists():
            errors['order'] = "Another plan with this order already exists."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.clean()  # enforce validation on save
        super().save(*args, **kwargs)
