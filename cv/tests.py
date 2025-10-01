from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import CVQuestionnaire, AIResponse
from django.urls import reverse
from rest_framework.authtoken.models import Token
from unittest.mock import patch, Mock, MagicMock
from openai import APIError, RateLimitError, APIConnectionError, AuthenticationError
from django.core.files.uploadedfile import SimpleUploadedFile
import PyPDF2

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


    def test_get_ai_response_list_paginated(self):
        """
        Ensure the authenticated user receives paginated AI responses.
        """
        # Create more responses to test pagination
        for i in range(15):
            AIResponse.objects.create(
                questionnaire=self.questionnaire,
                response_text=f"Response {i}"
            )
        url = reverse('ai-response-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertLessEqual(len(response.data['results']), 10)
        self.assertIn('count', response.data)
        self.assertGreaterEqual(response.data['count'], 16)

    def test_get_single_ai_response(self):
        """
        Ensure the user can retrieve a single AI response by ID.
        """
        url = reverse('ai-response-detail', kwargs={'pk': self.ai_response.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['response_text'], self.ai_response.response_text)


class CVQuestionnaireAPITest(APITestCase):

    def test_get_cv_questionnaire_list_paginated(self):
        """
        Ensure the authenticated user receives paginated CV questionnaires.
        """
        # Create more questionnaires to test pagination
        for i in range(15):
            CVQuestionnaire.objects.create(
                user=self.user,
                position=f"Position {i}",
                industry='Tech',
                experience_level='5-7',
                company_size='large',
                location='On-site',
                application_timeline='ASAP',
                job_description='Test job description.'
            )
        url = reverse('questionnaire-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertLessEqual(len(response.data['results']), 10)
        self.assertIn('count', response.data)
        self.assertGreaterEqual(response.data['count'], 16)
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


class AIResponseCreateErrorHandlingTest(APITestCase):
    def setUp(self):
        """
        Set up test data for error handling tests.
        """
        self.user = User.objects.create_user(
            username='erroruser',
            email='erroruser@example.com',
            password='securepass123'
        )
        self.client.force_authenticate(user=self.user)

        self.questionnaire = CVQuestionnaire.objects.create(
            user=self.user,
            position='Software Engineer',
            industry='Tech',
            experience_level='3-5',
            company_size='medium',
            location='Remote',
            application_timeline='1-2 weeks',
            job_description='Develop web applications using modern frameworks.'
        )

    def test_create_ai_response_missing_questionnaire(self):
        """
        Test that missing questionnaire ID returns appropriate error.
        """
        url = reverse('ai-response-list')
        data = {
            'prompt': 'Please improve my CV'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('questionnaire ID and prompt are required', response.data['error'])

    def test_create_ai_response_missing_prompt(self):
        """
        Test that missing prompt returns appropriate error.
        """
        url = reverse('ai-response-list')
        data = {
            'questionnaire': self.questionnaire.id
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('questionnaire ID and prompt are required', response.data['error'])

    def test_create_ai_response_prompt_too_short(self):
        """
        Test that prompt too short returns appropriate error.
        """
        url = reverse('ai-response-list')
        data = {
            'questionnaire': self.questionnaire.id,
            'prompt': 'short'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('at least 10 characters', response.data['error'])

    def test_create_ai_response_prompt_too_long(self):
        """
        Test that prompt too long returns appropriate error.
        """
        url = reverse('ai-response-list')
        data = {
            'questionnaire': self.questionnaire.id,
            'prompt': 'x' * 5001  # Over the 5000 character limit
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('less than 5000 characters', response.data['error'])

    def test_create_ai_response_questionnaire_not_found(self):
        """
        Test that non-existent questionnaire returns appropriate error.
        """
        url = reverse('ai-response-list')
        data = {
            'questionnaire': 99999,  # Non-existent ID
            'prompt': 'Please improve my CV for this position'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('not found or you do not have permission', response.data['error'])

    def test_create_ai_response_questionnaire_different_user(self):
        """
        Test that accessing another user's questionnaire returns appropriate error.
        """
        # Create another user and questionnaire
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='password123'
        )
        other_questionnaire = CVQuestionnaire.objects.create(
            user=other_user,
            position='Designer',
            industry='Design',
            experience_level='2-3',
            company_size='small',
            location='On-site',
            application_timeline='ASAP',
            job_description='Design user interfaces.'
        )

        url = reverse('ai-response-list')
        data = {
            'questionnaire': other_questionnaire.id,
            'prompt': 'Please improve my CV for this position'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('not found or you do not have permission', response.data['error'])

    @patch('cv.views.os.getenv')
    def test_create_ai_response_missing_api_key(self, mock_getenv):
        """
        Test that missing OpenAI API key returns appropriate error.
        """
        mock_getenv.return_value = None  # Simulate missing API key
        
        url = reverse('ai-response-list')
        data = {
            'questionnaire': self.questionnaire.id,
            'prompt': 'Please improve my CV for this position'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn('currently unavailable', response.data['error'])

    @patch('cv.views.OpenAI')
    @patch('cv.views.os.getenv')
    def test_create_ai_response_openai_authentication_error(self, mock_getenv, mock_openai):
        """
        Test OpenAI authentication error handling.
        """
        mock_getenv.return_value = "test-api-key"
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Create proper mock response for AuthenticationError
        mock_response = Mock()
        mock_response.status_code = 401
        auth_error = AuthenticationError(
            message="Invalid API key",
            response=mock_response,
            body={"error": {"message": "Invalid API key"}}
        )
        mock_client.chat.completions.create.side_effect = auth_error
        
        url = reverse('ai-response-list')
        data = {
            'questionnaire': self.questionnaire.id,
            'prompt': 'Please improve my CV for this position'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn('authentication failed', response.data['error'])

    @patch('cv.views.OpenAI')
    @patch('cv.views.os.getenv')
    def test_create_ai_response_openai_rate_limit_error(self, mock_getenv, mock_openai):
        """
        Test OpenAI rate limit error handling.
        """
        mock_getenv.return_value = "test-api-key"
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Create proper mock response for RateLimitError
        mock_response = Mock()
        mock_response.status_code = 429
        rate_limit_error = RateLimitError(
            message="Rate limit exceeded",
            response=mock_response,
            body={"error": {"message": "Rate limit exceeded"}}
        )
        mock_client.chat.completions.create.side_effect = rate_limit_error
        
        url = reverse('ai-response-list')
        data = {
            'questionnaire': self.questionnaire.id,
            'prompt': 'Please improve my CV for this position'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('currently busy', response.data['error'])

    @patch('cv.views.OpenAI')
    @patch('cv.views.os.getenv')
    def test_create_ai_response_openai_connection_error(self, mock_getenv, mock_openai):
        """
        Test OpenAI connection error handling.
        """
        mock_getenv.return_value = "test-api-key"
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Create proper APIConnectionError
        connection_error = APIConnectionError(request=Mock())
        mock_client.chat.completions.create.side_effect = connection_error
        
        url = reverse('ai-response-list')
        data = {
            'questionnaire': self.questionnaire.id,
            'prompt': 'Please improve my CV for this position'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn('Unable to connect', response.data['error'])

    @patch('cv.views.OpenAI')
    @patch('cv.views.os.getenv')
    def test_create_ai_response_openai_quota_error(self, mock_getenv, mock_openai):
        """
        Test OpenAI quota exceeded error handling.
        """
        mock_getenv.return_value = "test-api-key"
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Create proper mock response for quota error
        mock_response = Mock()
        mock_response.status_code = 429
        quota_error = APIError(
            message="insufficient_quota: You exceeded your current quota",
            request=Mock(),
            body={"error": {"message": "insufficient_quota: You exceeded your current quota"}}
        )
        mock_client.chat.completions.create.side_effect = quota_error
        
        url = reverse('ai-response-list')
        data = {
            'questionnaire': self.questionnaire.id,
            'prompt': 'Please improve my CV for this position'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn('quota exceeded', response.data['error'])

    @patch('cv.views.OpenAI')
    @patch('cv.views.os.getenv')
    def test_create_ai_response_openai_generic_error(self, mock_getenv, mock_openai):
        """
        Test OpenAI generic API error handling.
        """
        mock_getenv.return_value = "test-api-key"
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Create proper mock for generic API error
        generic_error = APIError(
            message="Some other API error",
            request=Mock(),
            body={"error": {"message": "Some other API error"}}
        )
        mock_client.chat.completions.create.side_effect = generic_error
        
        url = reverse('ai-response-list')
        data = {
            'questionnaire': self.questionnaire.id,
            'prompt': 'Please improve my CV for this position'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn('encountered an error', response.data['error'])

    @patch('cv.views.OpenAI')
    @patch('cv.views.os.getenv')
    def test_create_ai_response_empty_response(self, mock_getenv, mock_openai):
        """
        Test handling of empty OpenAI response.
        """
        mock_getenv.return_value = "test-api-key"
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = ""
        mock_client.chat.completions.create.return_value = mock_response
        
        url = reverse('ai-response-list')
        data = {
            'questionnaire': self.questionnaire.id,
            'prompt': 'Please improve my CV for this position'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn('empty response', response.data['error'])

    def test_create_ai_response_large_pdf_file(self):
        """
        Test that large PDF files are rejected with appropriate error.
        """
        # Create a mock large PDF file (simulate 11MB)
        large_content = b'x' * (11 * 1024 * 1024)  # 11MB
        large_pdf = SimpleUploadedFile(
            "large_cv.pdf",
            large_content,
            content_type="application/pdf"
        )
        
        # Update questionnaire with large resume
        self.questionnaire.resume = large_pdf
        self.questionnaire.save()
        
        url = reverse('ai-response-list')
        data = {
            'questionnaire': self.questionnaire.id,
            'prompt': 'Please improve my CV for this position'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('too large', response.data['error'])

    @patch('cv.views.PyPDF2.PdfReader')
    def test_create_ai_response_corrupted_pdf(self, mock_pdf_reader):
        """
        Test handling of corrupted PDF files.
        """
        # Create a small PDF file for testing
        pdf_content = b'%PDF-1.4 fake pdf content'
        pdf_file = SimpleUploadedFile(
            "test_cv.pdf",
            pdf_content,
            content_type="application/pdf"
        )
        
        self.questionnaire.resume = pdf_file
        self.questionnaire.save()
        
        # Mock PDF reader to raise PdfReadError
        mock_pdf_reader.side_effect = PyPDF2.errors.PdfReadError("Invalid PDF")
        
        url = reverse('ai-response-list')
        data = {
            'questionnaire': self.questionnaire.id,
            'prompt': 'Please improve my CV for this position'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('valid PDF format', response.data['error'])

    @patch('cv.views.OpenAI')
    @patch('cv.views.os.getenv')
    def test_create_ai_response_success(self, mock_getenv, mock_openai):
        """
        Test successful AI response creation with proper mocking.
        """
        mock_getenv.return_value = "test-api-key"
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Here is your improved CV content."
        mock_client.chat.completions.create.return_value = mock_response
        
        url = reverse('ai-response-list')
        data = {
            'questionnaire': self.questionnaire.id,
            'prompt': 'Please improve my CV for this position'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('response_text', response.data)
        self.assertEqual(response.data['response_text'], "Here is your improved CV content.")
        
        # Verify AI response was saved to database
        ai_response = AIResponse.objects.get(id=response.data['id'])
        self.assertEqual(ai_response.questionnaire, self.questionnaire)
        self.assertEqual(ai_response.response_text, "Here is your improved CV content.")
