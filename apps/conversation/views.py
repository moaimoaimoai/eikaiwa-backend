import base64
import io
import random
from datetime import datetime
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from .models import ConversationSession, ConversationMessage
from .serializers import ConversationSessionSerializer, ConversationMessageSerializer
from .openai_service import chat_with_ai, generate_conversation_summary, transcribe_audio, transcribe_audio_ja, text_to_speech, update_user_memory, japanese_to_english
from apps.mistakes.models import Mistake
from apps.accounts.models import UserMemory
from apps.phrases.models import SavedPhrase

# 1セッションあたりのユーザー発言上限（フロントエンドの MAX_TURNS と合わせる）
MAX_TURNS_PER_SESSION = 10

# ── 内部テーマリスト（フリー会話の多様性確保用）──
# daily_topic_label が指定されていない通常会話でも毎回違う話題から始まるようにするための内部ヒント集。
# (opening_question_seed, conversation_hint) のタプル形式。ユーザーには表示されない。
INTERNAL_TOPICS = [
    # 日常生活
    ("your morning routine and what makes it feel good or terrible", "morning habits"),
    ("your favorite local restaurants or hidden food spots nearby", "local food"),
    ("how you usually spend your evenings after work or study", "evening routine"),
    ("the most annoying and best things about commuting", "commuting life"),
    ("your go-to comfort food and why it makes you feel better", "comfort food"),
    ("what your home or room says about your personality", "home and space"),
    ("how you handle a rainy day — do you love it or hate it?", "weather and mood"),
    ("your relationship with your smartphone — can you go a day without it?", "digital habits"),
    ("your shopping style — do you browse for hours or go straight for what you need?", "shopping habits"),
    ("how you usually wind down before bed", "bedtime routine"),
    # 旅行・場所
    ("a trip or destination that surprised you in an unexpected way", "travel surprises"),
    ("a place on your bucket list and why it calls to you", "dream destinations"),
    ("the best and worst things about living in Japan compared to other places", "Japan life"),
    ("a small town or lesser-known spot you would recommend to a traveler", "hidden travel gems"),
    ("if you could live in any city in the world for one year, where would it be?", "city life"),
    ("how traveling changes the way you see things back home", "travel perspective"),
    ("your ideal type of holiday — relaxing beach, adventure, or cultural exploration?", "holiday style"),
    # エンタメ・趣味
    ("a movie, drama, or anime that has stayed with you long after watching it", "memorable stories"),
    ("music you listen to when you need energy versus when you want to relax", "music moods"),
    ("a book, manga, or podcast that completely changed how you think", "mind-changing media"),
    ("your relationship with video games — casual player, hardcore gamer, or non-player?", "gaming life"),
    ("if you could master any creative skill instantly, what would you choose?", "creative skills"),
    ("a hobby you have tried and abandoned, and why", "abandoned hobbies"),
    ("your favorite season and what you most love doing in it", "seasons"),
    ("what you do when you need a creative outlet", "creativity"),
    # 食・料理
    ("a dish you can cook really well and are proud of", "cooking pride"),
    ("the weirdest food combination you secretly enjoy", "unusual food"),
    ("your coffee or tea preferences — and whether you could survive without it", "coffee and tea"),
    ("a cuisine from another country you could eat every day", "world cuisine"),
    ("what cooking at home means to you — is it relaxing or a chore?", "home cooking"),
    # 健康・ライフスタイル
    ("your approach to exercise — do you love it, hate it, or find balance somewhere?", "exercise habits"),
    ("how you manage stress and what actually works for you", "stress management"),
    ("sleep — are you a night owl, early bird, or somewhere in between?", "sleep habits"),
    ("small habits that have made a big difference in your life", "life-changing habits"),
    ("your thoughts on social media — helpful tool, time sink, or both?", "social media life"),
    # 仕事・学び
    ("what you enjoy most and least about your current job or studies", "work and study"),
    ("a skill you are currently trying to improve and how it's going", "current goals"),
    ("how you stay motivated when things get difficult", "motivation"),
    ("the best lesson you have learned from a mistake", "learning from mistakes"),
    ("what an ideal workday looks like for you", "ideal work"),
    ("if you could switch careers for a year with no risk, what would you try?", "career dreams"),
    # 人間関係
    ("what qualities you value most in a close friend", "friendship values"),
    ("how you handle disagreements — do you speak up or avoid conflict?", "conflict style"),
    ("a compliment someone gave you that you still think about", "memorable compliments"),
    ("how technology has changed the way you stay in touch with people", "staying connected"),
    ("what your relationship with social media says about modern friendship", "digital friendship"),
    # 思考・価値観
    ("something you believed strongly as a kid but now think differently about", "changed beliefs"),
    ("what success means to you — and whether that definition has changed", "definition of success"),
    ("if you could give your younger self one piece of advice, what would it be?", "advice to self"),
    ("a decision you made that turned out better than you expected", "good decisions"),
    ("what you think about when you cannot sleep", "late night thoughts"),
    ("what happiness looks like in your day-to-day life", "everyday happiness"),
    # テクノロジー・未来
    ("how AI is already changing your daily life, even in small ways", "AI in daily life"),
    ("a technology you are excited about and one you are worried about", "tech hopes and fears"),
    ("what you think the world will look like in 20 years", "future world"),
    ("how you feel about remote work or online study — pro or con?", "remote life"),
    # 季節・文化
    ("your favorite Japanese tradition or seasonal event and what it means to you", "Japanese traditions"),
    ("how you celebrate your birthday — big party, quiet day, or skip it entirely?", "birthdays"),
    ("what summer means to you beyond just the heat", "summer vibes"),
    ("a cultural difference between Japan and other countries that fascinates you", "cultural differences"),
    # 動物・自然
    ("your relationship with animals — do you have or want a pet?", "pets and animals"),
    ("the most beautiful natural place you have ever seen", "nature beauty"),
    ("how spending time in nature makes you feel", "nature and mood"),
    # ユニーク・おもしろい
    ("a superpower you would choose and how you would actually use it in real life", "superpowers"),
    ("the best and worst trends you have seen come and go", "trends"),
    ("if you could have dinner with anyone — living or historical — who would it be?", "dinner with anyone"),
    ("the strangest or funniest thing that has happened to you recently", "funny moments"),
    ("if you could instantly speak any language fluently, which one and why?", "language dreams"),
    ("your hidden talent that most people do not know about", "hidden talents"),
    ("what you would do with a completely free day with no obligations", "perfect free day"),
]


class SessionListView(generics.ListAPIView):
    serializer_class = ConversationSessionSerializer

    def get_queryset(self):
        return ConversationSession.objects.filter(user=self.request.user)


@api_view(['POST'])
def start_session(request):
    """Start a new conversation session."""
    user = request.user

    # ── 使用量制限チェック ──
    user.reset_monthly_if_needed()
    if not user.can_start_session():
        return Response({
            'error': 'monthly_limit_reached',
            'message': '今月の会話上限に達しました。プレミアムプランにアップグレードするか、来月をお待ちください。',
            'monthly_used': user.monthly_sessions_used,
            'monthly_limit': user.monthly_limit,
        }, status=status.HTTP_402_PAYMENT_REQUIRED)

    topic = request.data.get('topic', 'free')
    avatar_name = request.data.get('avatar_name', 'Emma')
    avatar_accent = request.data.get('avatar_accent', 'American')
    # 今日のトピック（任意）
    daily_topic_label = request.data.get('daily_topic_label', '')
    daily_topic_hint  = request.data.get('daily_topic_hint', '')

    # Close any existing active sessions
    ConversationSession.objects.filter(
        user=user, is_active=True
    ).update(is_active=False, ended_at=timezone.now())

    session = ConversationSession.objects.create(
        user=user,
        topic=topic,
        avatar_name=avatar_name,
        avatar_accent=avatar_accent,
    )

    # ── ユーザー記憶を取得 ──
    memory, _ = UserMemory.objects.get_or_create(user=user)
    memory_context = memory.to_context_string()

    # Generate opening message from AI
    if daily_topic_label:
        # デイリートピック指定あり: シナリオに引き込む開幕メッセージを生成
        opening_prompt = (
            f'Please start the conversation by setting up the following specific scenario: "{daily_topic_label}". '
            f'Hint for the scenario: {daily_topic_hint}. '
            f'Immediately place the user IN the situation with a natural, immersive opening line '
            f'(e.g. pretend you are a hotel receptionist, a barista, a colleague, etc. as appropriate). '
            f'Keep it to 2-3 sentences and end with a question that naturally continues the scenario.'
        )
    else:
        # 内部テーマをランダム選択して会話の多様性を確保（ユーザーには表示されない）
        internal_seed, internal_hint = random.choice(INTERNAL_TOPICS)
        opening_prompt = (
            f'Please start our conversation with a warm, natural greeting and ONE engaging opening question about '
            f'{internal_seed}. '
            f'Be conversational and friendly — like chatting with a curious friend, not a formal interview. '
            f'Keep it to 2-3 sentences max.'
        )

    opening_messages = [{'role': 'user', 'content': opening_prompt}]

    result = chat_with_ai(
        opening_messages,
        avatar_name=avatar_name,
        accent=avatar_accent,
        topic=topic,
        level=user.level,
        memory_context=memory_context,
        daily_topic_label=daily_topic_label,
        daily_topic_hint=daily_topic_hint,
    )

    # Save AI opening message
    ai_message = ConversationMessage.objects.create(
        session=session,
        role='assistant',
        content=result['clean_response'],
    )
    session.message_count = 1
    session.save()

    # 使用量カウントアップ
    user.monthly_sessions_used += 1
    user.save(update_fields=['monthly_sessions_used'])

    return Response({
        'session_id': session.id,
        'message': ConversationMessageSerializer(ai_message).data,
        'monthly_used': user.monthly_sessions_used,
        'monthly_limit': user.monthly_limit,
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def send_message(request, session_id):
    """Send a message and get AI response."""
    try:
        session = ConversationSession.objects.get(id=session_id, user=request.user)
    except ConversationSession.DoesNotExist:
        return Response({'error': 'Session not found.'}, status=404)

    user_content = request.data.get('content', '').strip()
    if not user_content:
        return Response({'error': 'Message content is required.'}, status=400)

    # ── セッション内10ターン上限チェック（サーバーサイド強制） ──
    user_turns = session.messages.filter(role='user').count()
    if user_turns >= MAX_TURNS_PER_SESSION:
        return Response({
            'error': 'session_turn_limit_reached',
            'message': f'1セッションの発言上限（{MAX_TURNS_PER_SESSION}回）に達しました。新しいセッションを開始してください。',
            'turns_used': user_turns,
            'turns_limit': MAX_TURNS_PER_SESSION,
        }, status=status.HTTP_400_BAD_REQUEST)

    # Save user message
    user_message = ConversationMessage.objects.create(
        session=session,
        role='user',
        content=user_content,
    )

    # Build message history for OpenAI
    history = []
    for msg in session.messages.all():
        history.append({'role': msg.role, 'content': msg.content})

    # ── ユーザー記憶を取得 ──
    memory, _ = UserMemory.objects.get_or_create(user=request.user)
    memory_context = memory.to_context_string()

    # Get AI response
    result = chat_with_ai(
        history,
        avatar_name=session.avatar_name,
        accent=session.avatar_accent,
        topic=session.topic,
        level=request.user.level,
        memory_context=memory_context,
    )

    # Handle correction
    correction = result.get('correction')
    has_mistake = False

    if correction and correction.get('has_mistake'):
        has_mistake = True
        user_message.has_mistake = True
        user_message.corrected_content = correction.get('corrected', '')
        user_message.save()

        # Save to mistakes collection
        Mistake.objects.create(
            user=request.user,
            session=session,
            original_text=correction.get('original', user_content),
            corrected_text=correction.get('corrected', ''),
            explanation=correction.get('explanation', ''),
            advice_ja=correction.get('advice_ja', ''),
            level_up=correction.get('level_up', ''),
            useful_phrases=correction.get('useful_phrases', []),
            mistake_type=correction.get('mistake_type', 'grammar'),
            is_unnatural_only=bool(correction.get('is_unnatural_only', False)),
            context=user_content,
        )
        session.mistake_count += 1

    # Save AI response
    ai_message = ConversationMessage.objects.create(
        session=session,
        role='assistant',
        content=result['clean_response'],
    )

    # Update session stats
    session.message_count += 2
    session.save()

    # Generate TTS audio if requested
    audio_data = None
    if request.data.get('include_audio', False):
        try:
            voice_map = {'American': 'nova', 'British': 'onyx', 'Australian': 'shimmer'}
            voice = voice_map.get(session.avatar_accent, 'nova')
            audio_bytes = text_to_speech(result['clean_response'], voice=voice)
            audio_data = base64.b64encode(audio_bytes).decode('utf-8')
        except Exception:
            pass

    coaching = result.get('coaching')

    # coaching の便利フレーズをフレーズ帳に自動保存
    try:
        if coaching and coaching.get('useful_phrases'):
            for p in coaching['useful_phrases']:
                english = p.get('english', '').strip()
                if english and not SavedPhrase.objects.filter(user=request.user, english__iexact=english).exists():
                    SavedPhrase.objects.create(
                        user=request.user,
                        session=session,
                        english=english,
                        japanese=p.get('japanese', ''),
                        context_ja=coaching.get('tip_ja', ''),
                        source='coaching',
                        session_topic=session.topic,
                    )
    except Exception:
        pass  # フレーズ保存の失敗が会話レスポンス全体を壊さないようにする

    return Response({
        'user_message': ConversationMessageSerializer(user_message).data,
        'ai_message': ConversationMessageSerializer(ai_message).data,
        'correction': correction if has_mistake else None,
        'coaching': coaching,
        'audio_base64': audio_data,
    })


@api_view(['POST'])
def end_session(request, session_id):
    """End a session and generate summary."""
    try:
        session = ConversationSession.objects.get(id=session_id, user=request.user)
    except ConversationSession.DoesNotExist:
        return Response({'error': 'Session not found.'}, status=404)

    # Calculate duration
    duration = int((timezone.now() - session.created_at).total_seconds() / 60)
    session.duration_minutes = max(1, duration)
    session.is_active = False
    session.ended_at = timezone.now()
    session.save()

    # Update user stats
    user = request.user
    user.total_conversations += 1
    user.total_minutes += session.duration_minutes

    # Update streak
    today = timezone.now().date()
    if user.last_active_date:
        days_diff = (today - user.last_active_date).days
        if days_diff == 1:
            user.streak_days += 1
        elif days_diff > 1:
            user.streak_days = 1
    else:
        user.streak_days = 1
    user.last_active_date = today
    user.save()

    # Generate summary
    messages = [
        {'role': msg.role, 'content': msg.content}
        for msg in session.messages.all()
    ]
    # ミスデータを渡して客観的採点を可能にする
    mistake_qs = Mistake.objects.filter(session=session)
    mistake_data = [
        {
            'mistake_type': m.mistake_type,
            'is_unnatural_only': m.is_unnatural_only,
        }
        for m in mistake_qs
    ]
    summary = generate_conversation_summary(messages, mistake_data)

    # ── ユーザー記憶を非同期的に更新（失敗しても無視） ──
    try:
        memory, _ = UserMemory.objects.get_or_create(user=user)
        updates = update_user_memory(messages, memory)
        if updates:
            for field, value in updates.items():
                if value and hasattr(memory, field):
                    setattr(memory, field, value)
            # トピックを記録
            topics = list(memory.topics_discussed) if memory.topics_discussed else []
            topic_label = session.topic
            if topic_label not in topics:
                topics.append(topic_label)
            memory.topics_discussed = topics[-20:]  # 最新20件のみ保持
            memory.session_count += 1
            memory.save()
    except Exception:
        pass

    # ── サマリーの便利フレーズをフレーズ帳に自動保存 ──
    try:
        if summary.get('useful_phrases'):
            for p in summary['useful_phrases']:
                english = p.get('english', '').strip()
                if english and not SavedPhrase.objects.filter(user=user, english__iexact=english).exists():
                    SavedPhrase.objects.create(
                        user=user,
                        session=session,
                        english=english,
                        japanese=p.get('japanese', ''),
                        context_ja=p.get('context_ja', ''),
                        source='summary',
                        session_topic=session.topic,
                    )
    except Exception:
        pass

    return Response({
        'session': ConversationSessionSerializer(session).data,
        'summary': summary,
    })


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def transcribe_audio_view(request):
    """Transcribe audio file using Whisper. language param: 'en' (default) or 'ja'."""
    audio_file = request.FILES.get('audio')
    if not audio_file:
        return Response({'error': 'Audio file is required.'}, status=400)

    language = request.data.get('language', 'en')

    try:
        audio_io = io.BytesIO(audio_file.read())
        audio_io.name = audio_file.name or 'recording.m4a'
        if language == 'ja':
            text = transcribe_audio_ja(audio_io)
        else:
            text = transcribe_audio(audio_io)
        return Response({'text': text})
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
def translate_japanese_to_english(request):
    """日本語テキストを英語に翻訳してアドバイスを返す。"""
    japanese_text = request.data.get('text', '').strip()
    if not japanese_text:
        return Response({'error': 'テキストを入力してください。'}, status=400)
    try:
        result = japanese_to_english(japanese_text)
        return Response(result)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
def synthesize_speech(request):
    """Convert text to speech."""
    text = request.data.get('text', '')
    voice = request.data.get('voice', 'nova')

    if not text:
        return Response({'error': 'Text is required.'}, status=400)

    try:
        audio_bytes = text_to_speech(text, voice=voice)
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        return Response({'audio_base64': audio_base64, 'format': 'mp3'})
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def session_detail(request, session_id):
    try:
        session = ConversationSession.objects.get(id=session_id, user=request.user)
        return Response(ConversationSessionSerializer(session).data)
    except ConversationSession.DoesNotExist:
        return Response({'error': 'Not found.'}, status=404)
