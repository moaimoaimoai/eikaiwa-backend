import base64
import io
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
    opening_messages = [{
        'role': 'user',
        'content': f'Please start our conversation with a friendly greeting and an opening question about {topic}.'
    }]

    result = chat_with_ai(
        opening_messages,
        avatar_name=avatar_name,
        accent=avatar_accent,
        topic=topic,
        level=user.level,
        memory_context=memory_context,
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
            useful_phrases=correction.get('useful_phrases', []),
            mistake_type=correction.get('mistake_type', 'grammar'),
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
    summary = generate_conversation_summary(messages)

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
