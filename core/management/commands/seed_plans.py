from django.core.management.base import BaseCommand
from core.seeders import seed_plans  # import your seeder functions

class Command(BaseCommand):
    help = "Seed the database with initial data like plans"

    def handle(self, *args, **kwargs):
        self.stdout.write("🔧 Seeding plans...")
        seed_plans()
        self.stdout.write(self.style.SUCCESS("🎉 Plan seeding complete."))