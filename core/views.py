from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from dj_rest_auth.views import UserDetailsView
from .serializers import CustomUserDetailsSerializer


class CustomUserDetailsView(UserDetailsView):
    serializer_class = CustomUserDetailsSerializer
    permission_classes = [IsAuthenticated]
