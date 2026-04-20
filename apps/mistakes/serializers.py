from rest_framework import serializers
from .models import Mistake


class MistakeSerializer(serializers.ModelSerializer):
    accuracy_rate = serializers.ReadOnlyField()
    session_topic = serializers.CharField(source='session.topic', read_only=True, allow_null=True)
    session_date = serializers.DateTimeField(source='session.created_at', read_only=True, allow_null=True)

    class Meta:
        model = Mistake
        fields = ['id', 'original_text', 'corrected_text', 'explanation', 'mistake_type',
                  'context', 'is_mastered', 'quiz_count', 'correct_count', 'accuracy_rate',
                  'session_topic', 'session_date', 'created_at']
        read_only_fields = ['id', 'created_at', 'quiz_count', 'correct_count']
