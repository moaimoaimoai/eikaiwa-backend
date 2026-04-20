import random
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Mistake
from .serializers import MistakeSerializer


class MistakeListView(generics.ListAPIView):
    serializer_class = MistakeSerializer

    def get_queryset(self):
        qs = Mistake.objects.filter(user=self.request.user)
        mistake_type = self.request.query_params.get('type')
        is_mastered = self.request.query_params.get('mastered')

        if mistake_type:
            qs = qs.filter(mistake_type=mistake_type)
        if is_mastered is not None:
            qs = qs.filter(is_mastered=is_mastered == 'true')
        return qs


class MistakeDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MistakeSerializer

    def get_queryset(self):
        return Mistake.objects.filter(user=self.request.user)


@api_view(['POST'])
def mark_mastered(request, pk):
    try:
        mistake = Mistake.objects.get(id=pk, user=request.user)
        mistake.is_mastered = not mistake.is_mastered
        mistake.save()
        return Response({'is_mastered': mistake.is_mastered})
    except Mistake.DoesNotExist:
        return Response({'error': 'Not found.'}, status=404)


@api_view(['GET'])
def mistakes_quiz(request):
    """Generate quiz questions from user's mistakes."""
    user = request.user
    count = int(request.query_params.get('count', 5))
    mistake_type = request.query_params.get('type')

    qs = Mistake.objects.filter(user=user, is_mastered=False)
    if mistake_type:
        qs = qs.filter(mistake_type=mistake_type)

    mistakes = list(qs)
    if not mistakes:
        return Response({'error': 'No mistakes to quiz on yet.', 'questions': []})

    selected = random.sample(mistakes, min(count, len(mistakes)))
    questions = []

    all_corrected = [m.corrected_text for m in mistakes]

    for mistake in selected:
        # Generate wrong options
        wrong_options = [t for t in all_corrected if t != mistake.corrected_text]
        if len(wrong_options) >= 3:
            wrong_options = random.sample(wrong_options, 3)
        else:
            # Pad with generic wrong options
            generic_wrongs = [
                "I am go to the store.",
                "She don't like coffee.",
                "They was happy yesterday.",
                "He have three cats.",
                "We was studying hard.",
            ]
            wrong_options += [w for w in generic_wrongs if w != mistake.corrected_text]
            wrong_options = wrong_options[:3]

        options = [mistake.corrected_text] + wrong_options
        random.shuffle(options)

        questions.append({
            'id': mistake.id,
            'question': mistake.original_text,
            'context': mistake.context,
            'correct_answer': mistake.corrected_text,
            'options': options,
            'explanation': mistake.explanation,
            'mistake_type': mistake.mistake_type,
        })

    return Response({'questions': questions})


@api_view(['POST'])
def submit_quiz_answer(request):
    """Submit a quiz answer and update mistake stats."""
    mistake_id = request.data.get('mistake_id')
    is_correct = request.data.get('is_correct', False)

    try:
        mistake = Mistake.objects.get(id=mistake_id, user=request.user)
        mistake.quiz_count += 1
        if is_correct:
            mistake.correct_count += 1
        # Mark as mastered if answered correctly 3 times in a row (simplified: 80%+ accuracy after 5+ attempts)
        if mistake.quiz_count >= 5 and mistake.accuracy_rate >= 80:
            mistake.is_mastered = True
        mistake.save()
        return Response({
            'quiz_count': mistake.quiz_count,
            'correct_count': mistake.correct_count,
            'accuracy_rate': mistake.accuracy_rate,
            'is_mastered': mistake.is_mastered,
        })
    except Mistake.DoesNotExist:
        return Response({'error': 'Not found.'}, status=404)


@api_view(['GET'])
def mistakes_summary(request):
    """Summary statistics for mistakes."""
    user = request.user
    mistakes = Mistake.objects.filter(user=user)

    by_type = {}
    for choice_key, choice_label in Mistake.MISTAKE_TYPE_CHOICES:
        count = mistakes.filter(mistake_type=choice_key).count()
        by_type[choice_key] = {'label': choice_label, 'count': count}

    return Response({
        'total': mistakes.count(),
        'mastered': mistakes.filter(is_mastered=True).count(),
        'by_type': by_type,
    })
