from django.test import TestCase
from django.contrib.auth import get_user_model
from core.models import CVQuestionnaire

User = get_user_model()

class CVQuestionnaireModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )

    def test_create_questionnaire(self):
        questionnaire = CVQuestionnaire.objects.create(
            user=self.user,
            position='Software Engineer',
            industry='Tech',
            experience_level='3-5',
            company_size='medium',
            location='Remote',
            application_timeline='1-3 months',
            job_description='A backend-focused engineering role',
        )

        self.assertEqual(str(questionnaire), "testuser - Software Engineer")
