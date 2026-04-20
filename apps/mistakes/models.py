from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Mistake(models.Model):
    MISTAKE_TYPE_CHOICES = [
        ('grammar', '文法'),
        ('vocabulary', '語彙'),
        ('pronunciation', '発音'),
        ('spelling', 'スペリング'),
        ('other', 'その他'),
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
    mistake_type = models.CharField(max_length=20, choices=MISTAKE_TYPE_CHOICES, default='grammar')
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
