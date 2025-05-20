from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import CVQuestionnaire, AIResponse
from django.urls import reverse
from rest_framework.authtoken.models import Token

User = get_user_model()

class AIResponseAPITest(APITestCase):
    def setUp(self):
        """
        Create user, authenticate, and create associated questionnaire and AI response.
        """
        self.user = User.objects.create_user(
            username='apitestuser',
            email='apiuser@example.com',
            password='securepass123'
        )

        self.client.force_authenticate(user=self.user)

        # Create a CVQuestionnaire for testing AI responses
        self.questionnaire = CVQuestionnaire.objects.create(
            user=self.user,
            position='Product Manager',
            industry='Tech',
            experience_level='5-7',
            company_size='large',
            location='On-site',
            application_timeline='ASAP',
            job_description='Oversee product development and launch strategies.'
        )

        # Create an AI response associated with the questionnaire
        self.ai_response = AIResponse.objects.create(
            questionnaire=self.questionnaire,
            response_text='Here is a great product-focused CV tailored for your needs.'
        )

    def test_get_ai_response_list(self):
        """
        Ensure the authenticated user can retrieve their AI responses.
        """
        url = reverse('ai-response-list')  # DRF auto-generates this from basename
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['response_text'], self.ai_response.response_text)

    def test_get_single_ai_response(self):
        """
        Ensure the user can retrieve a single AI response by ID.
        """
        url = reverse('ai-response-detail', kwargs={'pk': self.ai_response.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['response_text'], self.ai_response.response_text)


class CVQuestionnaireAPITest(APITestCase):
    def setUp(self):
        """
        Set up the test data: create a user and a CV questionnaire.
        """
        self.user = User.objects.create_user(
            username='apitestuser',
            email='apiuser@example.com',
            password='securepass123'
        )
        self.client.force_authenticate(user=self.user)

        # Create a CVQuestionnaire instance for testing
        self.questionnaire = CVQuestionnaire.objects.create(
            user=self.user,
            position='Product Manager',
            industry='Tech',
            experience_level='5-7',
            company_size='large',
            location='On-site',
            application_timeline='ASAP',
            job_description='Oversee product development and launch strategies.'
        )

    # test patch
    def test_patch_cv_questionnaire(self):
        """
        Ensure the authenticated user can partially update their CVQuestionnaire.
        """
        url = reverse('questionnaire-detail', kwargs={'pk': self.questionnaire.pk})

        # Only updating the 'position' field, leaving others unchanged
        data = {
            'position': 'Senior Product Manager',  # Updated position
        }

        response = self.client.patch(url, data, format='json')

        # Check the response status code
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify the updated 'position' field
        self.assertEqual(response.data['position'], 'Senior Product Manager')

        # Refresh the questionnaire object from the database and check the changes
        self.questionnaire.refresh_from_db()
        self.assertEqual(self.questionnaire.position, 'Senior Product Manager')
