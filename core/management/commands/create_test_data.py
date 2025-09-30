"""
Django Management Command: create_test_data

DESCRIPTION:
    Create test data for testing the cleanup_old_data command.
    This utility command generates old AI responses and questionnaires
    that can be used to verify the cleanup functionality works correctly.

PURPOSE:
    - Generate test data with backdated timestamps
    - Create realistic test scenarios for cleanup testing
    - Verify cleanup command behavior without affecting real data
    - Help developers test and debug the cleanup functionality

USAGE EXAMPLES:

    1. Create 5 test records (default):
       python manage.py create_test_data

    2. Create 10 test records:
       python manage.py create_test_data --count=10

    3. Create test data for specific testing:
       python manage.py create_test_data --count=20

DOCKER USAGE:
    Run inside Docker container:
    docker-compose exec web python manage.py create_test_data --count=10

WHAT IT CREATES:
    - Test user account (cleanup_test_user) if it doesn't exist
    - CVQuestionnaire records with test data
    - AIResponse records linked to questionnaires
    - All records are backdated to 100 days ago for cleanup testing

TESTING WORKFLOW:
    1. Run this command to create test data:
       python manage.py create_test_data --count=10

    2. Test cleanup with dry-run to see what would be deleted:
       python manage.py cleanup_old_data --days=90 --dry-run

    3. Run actual cleanup to verify it works:
       python manage.py cleanup_old_data --days=90 --force

    4. Verify test data was cleaned up properly

SAFETY NOTES:
    - Only creates test data, doesn't delete anything
    - Uses dedicated test user to avoid mixing with real data
    - Test records are clearly marked with "Test" prefixes
    - Safe to run multiple times (will create additional test data)

TEST DATA STRUCTURE:
    - Username: cleanup_test_user
    - Email: test@example.com
    - Positions: "Test Position 1", "Test Position 2", etc.
    - Job descriptions: "Test job description 1", etc.
    - All timestamps: 100 days in the past
"""

from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from cv.models import CVQuestionnaire, AIResponse
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()


class Command(BaseCommand):
    help = "Create test data for cleanup command testing"

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=5,
            help='Number of old records to create (default: 5)'
        )

    def handle(self, *args, **options):
        count = options['count']
        
        self.stdout.write("🔧 Creating test data for cleanup testing...")
        
        # Get or create a test user
        user, created = User.objects.get_or_create(
            username='cleanup_test_user',
            defaults={
                'email': 'test@example.com',
                'first_name': 'Test',
                'last_name': 'User'
            }
        )
        
        if created:
            user.set_password('testpass123')
            user.save()
            self.stdout.write("   Created test user")
        
        # Create old questionnaires and AI responses
        old_date = timezone.now() - timedelta(days=100)
        
        for i in range(count):
            # Create questionnaire
            questionnaire = CVQuestionnaire.objects.create(
                user=user,
                position=f'Test Position {i+1}',
                industry='Technology',
                experience_level='3-5',
                company_size='medium',
                location='Remote',
                application_timeline='1-3 months',
                job_description=f'Test job description {i+1}'
            )
            
            # Create AI response with old date
            ai_response = AIResponse.objects.create(
                questionnaire=questionnaire,
                response_text=f'This is a test AI response {i+1} that should be cleaned up.'
            )
            
            # Manually update the created_at to be old
            AIResponse.objects.filter(id=ai_response.id).update(created_at=old_date)
            
            self.stdout.write(f"   Created test questionnaire and AI response {i+1}")
        
        self.stdout.write(
            self.style.SUCCESS(f"✅ Created {count} test records dated {old_date.strftime('%Y-%m-%d')}")
        )
        self.stdout.write(
            self.style.NOTICE("💡 You can now test the cleanup command with --dry-run")
        )