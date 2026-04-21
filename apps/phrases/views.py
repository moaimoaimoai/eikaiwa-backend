import random
import logging
import traceback
from datetime import timedelta
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import Category, Phrase, Word, UserPhraseProgress, AIWarmupSession
from .serializers import CategorySerializer, PhraseSerializer, WordSerializer
from .openai_service import generate_warmup_phrases
from apps.accounts.models import UserMemory

logger = logging.getLogger(__name__)


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


DAILY_AI_LIMIT = 5  # 1日あたりの生成上限回数


@api_view(['GET'])
def ai_warmup(request):
    """
    AIが毎回異なるウォームアップフレーズを10個生成して返す。
    直近7日間に表示したフレーズは除外（重複防止）。
    1日あたり DAILY_AI_LIMIT 回まで生成可能。
    """
    user = request.user
    level = request.query_params.get('level', user.level)

    # ── 1日の生成回数チェック ──
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_sessions = AIWarmupSession.objects.filter(user=user, created_at__gte=today_start).order_by('-created_at')
    today_count = today_sessions.count()
    if today_count >= DAILY_AI_LIMIT:
        # 今日生成済みのフレーズをすべて集めて返す（重複除去）
        seen_hashes: set = set()
        today_phrases = []
        for session in today_sessions:
            for phrase in (session.phrases_data or []):
                h = phrase.get('hash', '')
                if h and h not in seen_hashes:
                    seen_hashes.add(h)
                    today_phrases.append(phrase)
        return Response({
            'error': f'本日の生成上限（{DAILY_AI_LIMIT}回）に達しました。明日また挑戦してください！',
            'limit_reached': True,
            'remaining_today': 0,
            'daily_limit': DAILY_AI_LIMIT,
            'phrases': today_phrases,  # 今日生成済みのフレーズを返す
        }, status=429)

    # 直近7日間に表示したフレーズのハッシュを収集
    cutoff = timezone.now() - timedelta(days=7)
    recent_sessions = AIWarmupSession.objects.filter(user=user, created_at__gte=cutoff)
    excluded_hashes = []
    for s in recent_sessions:
        excluded_hashes.extend(s.phrases_shown or [])

    # ユーザー記憶コンテキストを取得
    memory_context = ''
    try:
        memory = UserMemory.objects.get(user=user)
        memory_context = memory.to_context_string()
    except UserMemory.DoesNotExist:
        pass

    try:
        phrases = generate_warmup_phrases(
            level=level,
            memory_context=memory_context,
            excluded_hashes=excluded_hashes,
            count=10,
        )
    except Exception as e:
        error_detail = traceback.format_exc()
        logger.error(f'[ai_warmup] OpenAI call failed: {e}\n{error_detail}')
        return Response({'error': f'AI生成に失敗しました: {str(e)}', 'detail': error_detail}, status=500)

    # 今回表示したハッシュとフレーズデータを履歴に保存
    shown_hashes = [p.get('hash', '') for p in phrases if p.get('hash')]
    if shown_hashes:
        AIWarmupSession.objects.create(
            user=user,
            phrases_shown=shown_hashes,
            phrases_data=phrases,  # フレーズ全データも保存（上限到達時の再表示用）
        )
        # 古い履歴を30件以上は削除
        old_ids = AIWarmupSession.objects.filter(user=user).order_by('-created_at').values_list('id', flat=True)[30:]
        if old_ids:
            AIWarmupSession.objects.filter(id__in=list(old_ids)).delete()

    used_today = today_count + 1
    remaining = max(0, DAILY_AI_LIMIT - used_today)
    return Response({
        'phrases': phrases,
        'count': len(phrases),
        'remaining_today': remaining,
        'used_today': used_today,
        'daily_limit': DAILY_AI_LIMIT,
    })


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
