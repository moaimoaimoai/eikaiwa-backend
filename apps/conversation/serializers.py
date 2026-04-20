from rest_framework import serializers
from .models import ConversationSession, ConversationMessage


class ConversationMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversationMessage
        fields = ['id', 'role', 'content', 'corrected_content', 'has_mistake', 'created_at']


class ConversationSessionSerializer(serializers.ModelSerializer):
    messages = ConversationMessageSerializer(many=True, read_only=True)

    class Meta:
        model = ConversationSession
        fields = ['id', 'topic', 'avatar_name', 'avatar_accent', 'is_active',
                  'duration_minutes', 'message_count', 'mistake_count', 'created_at', 'messages']
