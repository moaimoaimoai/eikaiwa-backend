import random
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import Category, Phrase, Word, UserPhraseProgress
from .serializers import CategorySerializer, PhraseSerializer, WordSerializer


class CategoryListView(generics.ListAPIView):
    serializer_class = CategorySerializer
    queryset = Category.objects.all()


class WarmupPhrasesView(generics.ListAPIView):
    """Returns 10 warmup phrases for the session. Prioritizes unpracticed ones."""
    serializer_class = PhraseSerializer

    def get_queryset(self):
        user = self.request.user
        level = self.request.query_params.get('level', user.level)
        category_id = self.request.query_params.get('category', None)

        qs = Phrase.objects.filter(is_active=True, level=level)
        if category_id:
            qs = qs.filter(category_id=category_id)

        # Get practiced phrase IDs for this user
        practiced_ids = UserPhraseProgress.objects.filter(
            user=user
        ).values_list('phrase_id', flat=True)

        unpracticed = list(qs.exclude(id__in=practiced_ids))
        practiced = list(qs.filter(id__in=practiced_ids))

        # Prefer unpracticed, then fill with practiced
        result = unpracticed[:10]
        if len(result) < 10:
            result += practiced[:10 - len(result)]

        random.shuffle(result)
        return result[:10]


class PhraseListView(generics.ListAPIView):
    serializer_class = PhraseSerializer

    def get_queryset(self):
        qs = Phrase.objects.filter(is_active=True)
        level = self.request.query_params.get('level')
        category = self.request.query_params.get('category')
        if level:
            qs = qs.filter(level=level)
        if category:
            qs = qs.filter(category_id=category)
        return qs


class WordListView(generics.ListAPIView):
    serializer_class = WordSerializer

    def get_queryset(self):
        qs = Word.objects.filter(is_active=True)
        level = self.request.query_params.get('level')
        if level:
            qs = qs.filter(level=level)
        return qs


@api_view(['POST'])
def mark_phrase_practiced(request, phrase_id):
    phrase = Phrase.objects.get(id=phrase_id)
    progress, created = UserPhraseProgress.objects.get_or_create(
        user=request.user, phrase=phrase
    )
    progress.practiced_count += 1
    progress.is_mastered = progress.practiced_count >= 3
    progress.save()
    return Response({'practiced_count': progress.practiced_count, 'is_mastered': progress.is_mastered})


@api_view(['GET'])
def quiz_phrases(request):
    """Generate phrase quiz questions."""
    user = request.user
    level = request.query_params.get('level', user.level)
    count = int(request.query_params.get('count', 5))

    phrases = list(Phrase.objects.filter(is_active=True, level=level))
    if len(phrases) < 4:
        return Response({'error': 'Not enough phrases for quiz.'}, status=400)

    selected = random.sample(phrases, min(count, len(phrases)))
    questions = []

    for phrase in selected:
        # Wrong options (3 random phrases different from correct)
        wrong_choices = random.sample(
            [p for p in phrases if p.id != phrase.id], min(3, len(phrases) - 1)
        )
        options = [phrase.japanese] + [p.japanese for p in wrong_choices]
        random.shuffle(options)

        questions.append({
            'id': phrase.id,
            'question': phrase.english,
            'correct_answer': phrase.japanese,
            'options': options,
            'pronunciation_hint': phrase.pronunciation_hint,
        })

    return Response({'questions': questions})


@api_view(['GET'])
def quiz_words(request):
    """Generate word quiz questions."""
    user = request.user
    level = request.query_params.get('level', user.level)
    count = int(request.query_params.get('count', 5))

    words = list(Word.objects.filter(is_active=True, level=level))
    if len(words) < 4:
        return Response({'error': 'Not enough words for quiz.'}, status=400)

    selected = random.sample(words, min(count, len(words)))
    questions = []

    for word in selected:
        wrong_choices = random.sample(
            [w for w in words if w.id != word.id], min(3, len(words) - 1)
        )
        options = [word.definition_ja] + [w.definition_ja for w in wrong_choices]
        random.shuffle(options)

        questions.append({
            'id': word.id,
            'question': word.word,
            'question_detail': word.example_sentence,
            'correct_answer': word.definition_ja,
            'options': options,
        })

    return Response({'questions': questions})
