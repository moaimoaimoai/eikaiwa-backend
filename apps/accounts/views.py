from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from .serializers import RegisterSerializer, UserSerializer, CustomTokenObtainPairSerializer

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({
            'message': 'Registration successful.',
            'user': UserSerializer(user).data,
        }, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [permissions.AllowAny]


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class StatsView(APIView):
    def get(self, request):
        user = request.user
        from apps.mistakes.models import Mistake
        from apps.conversation.models import ConversationSession

        recent_sessions = ConversationSession.objects.filter(
            user=user
        ).order_by('-created_at')[:7]

        mistake_count = Mistake.objects.filter(user=user).count()
        mastered_count = Mistake.objects.filter(user=user, is_mastered=True).count()

        return Response({
            'total_conversations': user.total_conversations,
            'total_minutes': user.total_minutes,
            'streak_days': user.streak_days,
            'mistake_count': mistake_count,
            'mastered_count': mastered_count,
            'level': user.level,
            'recent_activity': [
                {
                    'date': s.created_at.date().isoformat(),
                    'duration': s.duration_minutes,
                    'message_count': s.message_count,
                }
                for s in recent_sessions
            ],
        })
