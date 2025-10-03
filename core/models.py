from django.contrib.auth.models import AbstractUser
from django.db import models
from .validators import validate_email_with_suggestions

class User(AbstractUser):
    date_of_birth = models.DateField(blank=True, null=True)
    plan = models.ForeignKey('Plan', on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_subscription_status = models.CharField(max_length=50, blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField('email address', blank=False, null=False, unique=True, validators=[validate_email_with_suggestions])



    class Meta:
        ordering = ['date_joined']
        verbose_name = 'User'
        verbose_name_plural = 'Users'

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
    name = models.CharField(max_length=50, unique=True)
    stripe_price_id_monthly = models.CharField(max_length=100, blank=True, null=True)
    stripe_price_id_yearly = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    order = models.PositiveIntegerField(default=10)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} Plan"