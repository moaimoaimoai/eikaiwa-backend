from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Avg, Sum
from rest_framework.decorators import api_view
from rest_framework.response import Response
from apps.mistakes.models import Mistake
from apps.conversation.models import ConversationSession


@api_view(['GET'])
def trend_analysis(request):
    """Comprehensive trend analysis for the user."""
    user = request.user
    days = int(request.query_params.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)

    # Sessions over time
    sessions = ConversationSession.objects.filter(
        user=user, created_at__gte=start_date
    ).order_by('created_at')

    # Daily activity (last 30 days)
    daily_activity = []
    for i in range(days):
        date = (timezone.now() - timedelta(days=days - 1 - i)).date()
        day_sessions = sessions.filter(created_at__date=date)
        daily_activity.append({
            'date': date.isoformat(),
            'session_count': day_sessions.count(),
            'minutes': sum(s.duration_minutes for s in day_sessions),
            'mistakes': sum(s.mistake_count for s in day_sessions),
        })

    # Mistake type distribution
    mistakes = Mistake.objects.filter(user=user)
    mistake_distribution = {}
    for choice_key, choice_label in Mistake.MISTAKE_TYPE_CHOICES:
        count = mistakes.filter(mistake_type=choice_key).count()
        if count > 0:
            mistake_distribution[choice_key] = {
                'label': choice_label,
                'count': count,
                'percentage': round(count / max(mistakes.count(), 1) * 100),
            }

    # Recent mistakes with trends
    recent_mistakes = mistakes.filter(created_at__gte=start_date)
    total_recent = recent_mistakes.count()
    mastered_recent = recent_mistakes.filter(is_mastered=True).count()

    # Topic distribution
    topic_sessions = sessions.values('topic').annotate(count=Count('id')).order_by('-count')
    topic_distribution = [
        {'topic': t['topic'], 'count': t['count']}
        for t in topic_sessions
    ]

    # Weekly progress (last 4 weeks)
    weekly_progress = []
    for week in range(4):
        week_start = timezone.now() - timedelta(weeks=week + 1)
        week_end = timezone.now() - timedelta(weeks=week)
        week_sessions = sessions.filter(
            created_at__gte=week_start,
            created_at__lt=week_end
        )
        week_mistakes = mistakes.filter(
            created_at__gte=week_start,
            created_at__lt=week_end
        )
        weekly_progress.insert(0, {
            'week': week + 1,
            'sessions': week_sessions.count(),
            'minutes': sum(s.duration_minutes for s in week_sessions),
            'mistakes': week_mistakes.count(),
            'mastered': week_mistakes.filter(is_mastered=True).count(),
        })

    # Common mistake patterns (top 5 most frequent mistakes)
    common_mistakes = mistakes.values('mistake_type').annotate(
        count=Count('id')
    ).order_by('-count')[:5]

    # Improvement suggestions
    suggestions = generate_suggestions(user, mistakes, sessions)

    return Response({
        'overview': {
            'total_sessions': user.total_conversations,
            'total_minutes': user.total_minutes,
            'streak_days': user.streak_days,
            'total_mistakes': mistakes.count(),
            'mastered_mistakes': mistakes.filter(is_mastered=True).count(),
        },
        'daily_activity': daily_activity[-14:],  # Last 14 days
        'weekly_progress': weekly_progress,
        'mistake_distribution': mistake_distribution,
        'topic_distribution': topic_distribution,
        'suggestions': suggestions,
    })


def generate_suggestions(user, mistakes, sessions):
    suggestions = []

    total_grammar = mistakes.filter(mistake_type='grammar').count()
    total_vocab = mistakes.filter(mistake_type='vocabulary').count()
    total_mistakes = mistakes.count()

    if total_mistakes == 0:
        suggestions.append({
            'type': 'encouragement',
            'title': '会話を始めましょう！',
            'body': '最初の会話セッションを始めて、英語力を伸ばしましょう。',
        })
        return suggestions

    if total_grammar > total_vocab and total_grammar > 3:
        suggestions.append({
            'type': 'grammar',
            'title': '文法の強化が必要です',
            'body': f'文法ミスが{total_grammar}回あります。単語帳で復習しながら、文法に注意して会話練習しましょう。',
        })

    if total_vocab > total_grammar and total_vocab > 3:
        suggestions.append({
            'type': 'vocabulary',
            'title': '語彙力をアップしましょう',
            'body': f'語彙ミスが{total_vocab}回あります。毎日10分のフレーズ学習を続けましょう。',
        })

    unmastered = mistakes.filter(is_mastered=False).count()
    if unmastered > 5:
        suggestions.append({
            'type': 'review',
            'title': '復習クイズに挑戦！',
            'body': f'まだ{unmastered}個のミスをマスターしていません。クイズで集中的に復習しましょう。',
        })

    if user.streak_days < 3:
        suggestions.append({
            'type': 'streak',
            'title': '毎日練習する習慣を！',
            'body': '毎日少しでも練習することが上達の近道です。今日も会話セッションをやってみましょう！',
        })

    if not suggestions:
        suggestions.append({
            'type': 'encouragement',
            'title': '順調に成長中！',
            'body': '素晴らしい進歩です！このペースで練習を続けましょう。',
        })

    return suggestions
