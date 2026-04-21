from rest_framework import serializers
from .models import Category, Phrase, Word, UserPhraseProgress, SavedPhrase


class CategorySerializer(serializers.ModelSerializer):
    phrase_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'name_ja', 'icon', 'phrase_count']

    def get_phrase_count(self, obj):
        return obj.phrases.filter(is_active=True).count()


class PhraseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name_ja', read_only=True)
    is_practiced = serializers.SerializerMethodField()

    class Meta:
        model = Phrase
        fields = ['id', 'english', 'japanese', 'pronunciation_hint',
                  'example_context', 'level', 'category_name', 'audio_url', 'is_practiced']

    def get_is_practiced(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return UserPhraseProgress.objects.filter(
                user=request.user, phrase=obj
            ).exists()
        return False


class WordSerializer(serializers.ModelSerializer):
    class Meta:
        model = Word
        fields = ['id', 'word', 'definition', 'definition_ja', 'part_of_speech',
                  'example_sentence', 'example_sentence_ja', 'level']


class SavedPhraseSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedPhrase
        fields = ['id', 'english', 'japanese', 'context_ja', 'source',
                  'session_topic', 'is_mastered', 'created_at']
