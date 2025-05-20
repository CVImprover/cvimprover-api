from .models import Plan

def seed_plans():
    plans = [
        {
            'name': 'Free',
            'stripe_price_id_monthly': None,
            'stripe_price_id_yearly': None,
        },
        {
            'name': 'Basic',
            'stripe_price_id_monthly': 'price_1RQoEVIAtbOFVSqcKAsoIYRD',
            'stripe_price_id_yearly': 'price_1RQoEVIAtbOFVSqcte2Ntd6x',
        },
        {
            'name': 'Pro',
            'stripe_price_id_monthly': None,
            'stripe_price_id_yearly': None,
        },
        {
            'name': 'Premium',
            'stripe_price_id_monthly': None,
            'stripe_price_id_yearly': None,
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