from .models import Plan

def seed_plans():
    plans = [
        {
            'name': 'Free',
            'stripe_price_id_monthly': None,
            'stripe_price_id_yearly': None,
            'order': 1,
        },
        {
            'name': 'Basic',
            'stripe_price_id_monthly': 'price_1RQoEVIAtbOFVSqcKAsoIYRD',
            'stripe_price_id_yearly': 'price_1RQoEVIAtbOFVSqcte2Ntd6x',
            'order': 2,
        },
        {
            'name': 'Pro',
            'stripe_price_id_monthly': 'price_1RRCHSIAtbOFVSqcqTbZ0Ep4',
            'stripe_price_id_yearly': 'price_1RRCHyIAtbOFVSqcDTMWhwfC',
            'order': 3,
        },
        {
            'name': 'Premium',
            'stripe_price_id_monthly': 'price_1RRCJtIAtbOFVSqc5jkDXk1q',
            'stripe_price_id_yearly': 'price_1RRCKcIAtbOFVSqcrNDlYeEz',
            'order': 4,
        },
    ]

    for p in plans:
        plan, created = Plan.objects.get_or_create(
            name=p['name'],
            defaults={
                'stripe_price_id_monthly': p['stripe_price_id_monthly'],
                'stripe_price_id_yearly': p['stripe_price_id_yearly'],
            }
        )

        if created:
            print(f"✅ Created plan: {plan.name}")
        else:
            print(f"⏩ Plan '{plan.name}' already exists. Skipping.")