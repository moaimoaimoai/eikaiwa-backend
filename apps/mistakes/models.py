from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Mistake(models.Model):
    MISTAKE_TYPE_CHOICES = [
        ('grammar',     '文法'),
        ('vocabulary',  '語彙'),
        ('preposition', '前置詞'),
        ('collocation', '語の組み合わせ'),
        ('unnatural',   '不自然な表現'),
        ('word_order',  '語順'),
        ('article',     '冠詞'),
        ('pronunciation', '発音'),
        ('spelling',    'スペリング'),
        ('other',       'その他'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mistakes')
    session = models.ForeignKey(
        'conversation.ConversationSession',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='mistakes'
    )
    original_text = models.CharField(max_length=500)
    corrected_text = models.CharField(max_length=500)
    explanation = models.TextField(blank=True)
    advice_ja = models.TextField(blank=True)
    level_up = models.TextField(blank=True)          # より上級・ネイティブらしい表現の提案
    useful_phrases = models.JSONField(default=list, blank=True)
    mistake_type = models.CharField(max_length=30, choices=MISTAKE_TYPE_CHOICES, default='grammar')
    is_unnatural_only = models.BooleanField(default=False)  # 文法的には正しいが不自然な場合
    context = models.TextField(blank=True)
    is_mastered = models.BooleanField(default=False)
    quiz_count = models.IntegerField(default=0)
    correct_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.original_text} → {self.corrected_text}'

    @property
    def accuracy_rate(self):
        if self.quiz_count == 0:
            return 0
        return round(self.correct_count / self.quiz_count * 100)
