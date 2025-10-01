from django.test import TestCase
from django.core.exceptions import ValidationError
from unittest.mock import patch
from .models import Plan

class PlanModelTests(TestCase):

    @patch('stripe.Price.retrieve')
    def test_plan_requires_at_least_one_price_id(self, mock_stripe):
        mock_stripe.return_value = {}  # Mock Stripe response
        plan = Plan(name="Test Plan", order=1)
        with self.assertRaises(ValidationError) as cm:
            plan.clean()
        self.assertIn('stripe_price_id_monthly', cm.exception.message_dict)

    @patch('stripe.Price.retrieve')
    def test_plan_duplicate_order_not_allowed(self, mock_stripe):
        mock_stripe.return_value = {}
        Plan.objects.create(name="Plan A", order=1, stripe_price_id_monthly="price_123")
        plan_b = Plan(name="Plan B", order=1, stripe_price_id_monthly="price_456")
        with self.assertRaises(ValidationError) as cm:
            plan_b.clean()
        self.assertIn('order', cm.exception.message_dict)

    @patch('stripe.Price.retrieve')
    def test_plan_valid_with_monthly_price(self, mock_stripe):
        mock_stripe.return_value = {}  # valid response
        plan = Plan(name="Valid Plan", order=2, stripe_price_id_monthly="price_valid")
        try:
            plan.clean()
        except ValidationError:
            self.fail("Plan.clean() raised ValidationError unexpectedly!")

    @patch('stripe.Price.retrieve')
    def test_plan_invalid_stripe_price_id(self, mock_stripe):
        mock_stripe.side_effect = Exception("Invalid price")
        plan = Plan(name="Invalid Stripe Plan", order=3, stripe_price_id_monthly="wrong_id")
        with self.assertRaises(ValidationError) as cm:
            plan.clean()
        self.assertIn('stripe_price_id_monthly', cm.exception.message_dict)
