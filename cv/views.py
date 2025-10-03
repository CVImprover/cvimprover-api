from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
import markdown2
from weasyprint import HTML
from django.core.files.base import ContentFile
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.exceptions import ValidationError
from .models import CVQuestionnaire, AIResponse
from .serializers import CVQuestionnaireSerializer, AIResponseSerializer
from openai import OpenAI
from openai import APIError, RateLimitError, APIConnectionError, AuthenticationError
import os
import PyPDF2
import logging

logger = logging.getLogger(__name__)


class CVQuestionnaireViewSet(viewsets.ModelViewSet):
    queryset = CVQuestionnaire.objects.all()
    serializer_class = CVQuestionnaireSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only return the current user's questionnaires
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        instance = serializer.save(user=self.request.user)
        try:
            instance.full_clean()
        except ValidationError as e:
            instance.delete()
            raise e




class AIResponseViewSet(mixins.ListModelMixin,
                        mixins.RetrieveModelMixin,
                        mixins.CreateModelMixin,
                        viewsets.GenericViewSet):

    @action(
        detail=True,
        methods=['post'],
        url_path='generate-pdf',
        url_name='generate-pdf',
        description='Generate a PDF from the AI response and update the questionnaire resume. Returns the PDF URL.'
    )
    def generate_pdf(self, request, pk=None):
        """
        Generate a PDF from the AI response and update the questionnaire resume. Returns the PDF URL.
        """
        ai_response = self.get_object()
        questionnaire = ai_response.questionnaire
        # Convert markdown to HTML
        html_content = markdown2.markdown(ai_response.response_text)
        # Generate PDF from HTML
        pdf_file = HTML(string=html_content).write_pdf()
        # Save PDF to the questionnaire's resume field
        filename = f"ai_cv_{questionnaire.id}.pdf"
        questionnaire.resume.save(filename, ContentFile(pdf_file), save=True)
        return Response({
            'pdf_url': questionnaire.resume.url
        })
    
    queryset = AIResponse.objects.all()
    serializer_class = AIResponseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(questionnaire__user=self.request.user)

    def create(self, request, *args, **kwargs):
        questionnaire_id = request.data.get('questionnaire')
        user_prompt = request.data.get('prompt')

        # Basic input validation
        if not questionnaire_id or not user_prompt:
            logger.warning(f"Missing required fields in AI response request. User: {request.user.id}")
            return Response({
                'error': 'Both questionnaire ID and prompt are required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate prompt length
        if len(user_prompt.strip()) < 10:
            logger.warning(f"Prompt too short for user {request.user.id}: {len(user_prompt)} characters")
            return Response({
                'error': 'Prompt must be at least 10 characters long.'
            }, status=status.HTTP_400_BAD_REQUEST)

        if len(user_prompt) > 5000:
            logger.warning(f"Prompt too long for user {request.user.id}: {len(user_prompt)} characters")
            return Response({
                'error': 'Prompt must be less than 5000 characters.'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            questionnaire = CVQuestionnaire.objects.get(id=questionnaire_id, user=request.user)
        except CVQuestionnaire.DoesNotExist:
            logger.warning(f"Questionnaire {questionnaire_id} not found for user {request.user.id}")
            return Response({
                'error': 'Questionnaire not found or you do not have permission to access it.'
            }, status=status.HTTP_404_NOT_FOUND)

        # Extract text from uploaded PDF CV if present with file size validation
        cv_text = ""
        if questionnaire.resume:
            try:
                # Check file size (limit to 10MB)
                if questionnaire.resume.size > 10 * 1024 * 1024:
                    logger.error(f"CV file too large for user {request.user.id}: {questionnaire.resume.size} bytes")
                    return Response({
                        'error': 'CV file is too large. Please upload a file smaller than 10MB.'
                    }, status=status.HTTP_400_BAD_REQUEST)

                logger.info(f"Processing CV file for user {request.user.id}, size: {questionnaire.resume.size} bytes")
                
                with questionnaire.resume.open('rb') as pdf_file:
                    reader = PyPDF2.PdfReader(pdf_file)
                    
                    if len(reader.pages) == 0:
                        logger.warning(f"Empty PDF uploaded by user {request.user.id}")
                        cv_text = "[CV file appears to be empty or corrupted]"
                    else:
                        for page in reader.pages:
                            cv_text += page.extract_text() or ""
                        
                        if not cv_text.strip():
                            logger.warning(f"No text extracted from PDF for user {request.user.id}")
                            cv_text = "[No text could be extracted from the CV file]"
                        else:
                            logger.info(f"Successfully extracted {len(cv_text)} characters from CV for user {request.user.id}")
                            
            except PyPDF2.errors.PdfReadError as e:
                logger.error(f"PDF read error for user {request.user.id}: {str(e)}")
                return Response({
                    'error': 'Unable to read CV file. Please ensure it is a valid PDF format.'
                }, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                logger.error(f"Unexpected error reading CV for user {request.user.id}: {str(e)}")
                return Response({
                    'error': 'An error occurred while processing your CV file. Please try again or contact support.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Get user info
        user = request.user
        prompt = (
            f"Full Name: {user.get_full_name()}\n"
            f"Username: {user.username}\n"
            f"Email: {user.email}\n"
            f"Date of Birth: {getattr(user, 'date_of_birth', '')}\n"            
            f"Position: {questionnaire.position}\n"
            f"Industry: {questionnaire.industry}\n"
            f"Experience Level: {questionnaire.experience_level}\n"
            f"Company Size: {questionnaire.company_size}\n"
            f"Location: {questionnaire.location}\n"
            f"Application Timeline: {questionnaire.application_timeline}\n"
            f"Job Description: {questionnaire.job_description}\n\n"
            f"CV Text: {cv_text}\n\n"
            f"{user_prompt}"
        )

        # OpenAI API call with comprehensive error handling
        try:
            logger.info(f"Making OpenAI API request for user {request.user.id}")
            
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.error("OpenAI API key not configured")
                return Response({
                    'error': 'AI service is currently unavailable. Please try again later.'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a professional CV optimization assistant. Improve and rewrite the following CV to maximize hiring chances, keeping all details accurate:"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4000,
                temperature=0.7
            )
            
            ai_text = response.choices[0].message.content
            if not ai_text or not ai_text.strip():
                logger.error(f"Empty response from OpenAI for user {request.user.id}")
                return Response({
                    'error': 'AI service returned an empty response. Please try again.'
                }, status=status.HTTP_502_BAD_GATEWAY)
                
            logger.info(f"Successfully received OpenAI response for user {request.user.id}, length: {len(ai_text)} characters")

        except AuthenticationError as e:
            logger.error(f"OpenAI authentication error: {str(e)}")
            return Response({
                'error': 'AI service authentication failed. Please contact support.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
        except RateLimitError as e:
            logger.warning(f"OpenAI rate limit exceeded for user {request.user.id}: {str(e)}")
            return Response({
                'error': 'AI service is currently busy. Please wait a moment and try again.'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
        except APIConnectionError as e:
            logger.error(f"OpenAI connection error for user {request.user.id}: {str(e)}")
            return Response({
                'error': 'Unable to connect to AI service. Please check your internet connection and try again.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
        except APIError as e:
            logger.error(f"OpenAI API error for user {request.user.id}: {str(e)}")
            if "insufficient_quota" in str(e).lower():
                return Response({
                    'error': 'AI service quota exceeded. Please contact support.'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            return Response({
                'error': 'AI service encountered an error. Please try again later.'
            }, status=status.HTTP_502_BAD_GATEWAY)
            
        except Exception as e:
            logger.error(f"Unexpected error during OpenAI API call for user {request.user.id}: {str(e)}")
            return Response({
                'error': 'An unexpected error occurred while processing your request. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Save the AI response
        try:
            ai_response = AIResponse.objects.create(
                questionnaire=questionnaire,
                response_text=ai_text
            )
            ai_response.full_clean()
            logger.info(f"Successfully created AI response {ai_response.id} for user {request.user.id}")
            
            serializer = self.get_serializer(ai_response)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except ValidationError as e:
            logger.error(f"Validation error saving AI response for user {request.user.id}: {str(e)}")
            return Response({
                'error': f'Validation error: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error saving AI response for user {request.user.id}: {str(e)}")
            return Response({
                'error': 'Failed to save AI response. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
