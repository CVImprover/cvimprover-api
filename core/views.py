# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import User  # Replace with your actual model
from .serializers import UserProfileSerializer  # Replace with your actual serializer

# This is your existing protected view
class ProtectedView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'message': f'Hello, {request.user.username}!'})

# This is the new UserProfile view to list and create profiles
class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]  # Optional: Secure this API

    def get(self, request):
        profiles = User.objects.all()  # Fetch all profiles (you can filter this)
        serializer = UserProfileSerializer(profiles, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = UserProfileSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
