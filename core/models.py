from django.contrib.auth.models import AbstractUser
from django.db import models
from .validators import validate_email_with_suggestions

class User(AbstractUser):
    date_of_birth = models.DateField(blank=True, null=True)
    plan = models.ForeignKey('Plan', on_delete=models.SET_NULL, null=True, blank=True, related_name='users', db_index=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    stripe_subscription_status = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    email = models.EmailField('email address', blank=False, null=False, unique=True, validators=[validate_email_with_suggestions])

    class Meta:
        ordering = ['date_joined']
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['email'], name='user_email_idx'),
            models.Index(fields=['username'], name='user_username_idx'),
            models.Index(fields=['date_joined'], name='user_date_joined_idx'),
            models.Index(fields=['plan', 'stripe_subscription_status'], name='user_plan_status_idx'),
            models.Index(fields=['stripe_customer_id'], name='user_stripe_customer_idx'),
        ]

    def __str__(self):
        return f"{self.username} ({self.email})"
    
    def save(self, *args, **kwargs):
        if self._state.adding and not self.plan:
            try:
                self.plan = Plan.objects.get(name='Free')
            except Plan.DoesNotExist:
                pass
        super().save(*args, **kwargs)

class Plan(models.Model):
    name = models.CharField(max_length=50, unique=True, db_index=True)
    stripe_price_id_monthly = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    stripe_price_id_yearly = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    order = models.PositiveIntegerField(default=10, db_index=True)

    class Meta:
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['order', 'name'], name='plan_order_name_idx'),
        ]

    def __str__(self):
        return f"{self.name} Plan"