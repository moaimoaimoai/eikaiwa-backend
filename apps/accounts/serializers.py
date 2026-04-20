from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'username', 'display_name', 'password', 'password_confirm', 'level']

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        return data

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    is_premium = serializers.ReadOnlyField()
    monthly_limit = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'display_name', 'level',
                  'total_conversations', 'total_minutes', 'streak_days', 'created_at',
                  'subscription_tier', 'subscription_expires_at',
                  'monthly_sessions_used', 'is_premium', 'monthly_limit']
        read_only_fields = ['id', 'email', 'total_conversations', 'total_minutes', 'streak_days',
                            'created_at', 'subscription_tier', 'subscription_expires_at',
                            'monthly_sessions_used', 'is_premium', 'monthly_limit']


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['display_name'] = user.name
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = UserSerializer(self.user).data
        return data
