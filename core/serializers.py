from dj_rest_auth.serializers import UserDetailsSerializer
from rest_framework import serializers
from .models import User

class CustomUserDetailsSerializer(UserDetailsSerializer):
    email = serializers.EmailField(required=False)
    date_of_birth = serializers.DateField(required=False, allow_null=True)

    class Meta(UserDetailsSerializer.Meta):
        model = User
        fields = UserDetailsSerializer.Meta.fields + (
            'date_of_birth',
        )