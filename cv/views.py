from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
import markdown2
from weasyprint import HTML
from django.core.files.base import ContentFile
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import CVQuestionnaire, AIResponse
from .serializers import CVQuestionnaireSerializer, AIResponseSerializer
from openai import OpenAI
import os
import PyPDF2


class CVQuestionnaireViewSet(viewsets.ModelViewSet):
    queryset = CVQuestionnaire.objects.all()
    serializer_class = CVQuestionnaireSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only return the current user's questionnaires
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)




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

        if not questionnaire_id or not user_prompt:
            return Response({'error': 'questionnaire and prompt required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            questionnaire = CVQuestionnaire.objects.get(id=questionnaire_id, user=request.user)
        except CVQuestionnaire.DoesNotExist:
            return Response({'error': 'Questionnaire not found'}, status=status.HTTP_404_NOT_FOUND)

        # Extract text from uploaded PDF CV if present
        cv_text = ""
        if questionnaire.resume:
            try:
                with questionnaire.resume.open('rb') as pdf_file:
                    reader = PyPDF2.PdfReader(pdf_file)
                    for page in reader.pages:
                        cv_text += page.extract_text() or ""
            except Exception as e:
                cv_text = f"[Error reading CV PDF: {str(e)}]"

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

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a professional CV optimization assistant. Improve and rewrite the following CV to maximize hiring chances, keeping all details accurate:"},
                {"role": "user", "content": prompt}
            ]
        )
        ai_text = response.choices[0].message.content

        ai_response = AIResponse.objects.create(
            questionnaire=questionnaire,
            response_text=ai_text
        )
        serializer = self.get_serializer(ai_response)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
