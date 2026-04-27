from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class ConversationSession(models.Model):
    TOPIC_CHOICES = [
        ('free', 'Free Conversation'),
        ('daily_life', 'Daily Life'),
        ('travel', 'Travel'),
        ('business', 'Business'),
        ('school', 'School'),
        ('hobby', 'Hobbies'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    topic = models.CharField(max_length=50, choices=TOPIC_CHOICES, default='free')
    avatar_name = models.CharField(max_length=50, default='Emma')
    avatar_accent = models.CharField(max_length=20, default='American')
    is_active = models.BooleanField(default=True)
    duration_minutes = models.IntegerField(default=0)
    message_count = models.IntegerField(default=0)
    mistake_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.email} - {self.topic} - {self.created_at.date()}'


class ConversationMessage(models.Model):
    ROLE_CHOICES = [('user', 'User'), ('assistant', 'Assistant')]

    session = models.ForeignKey(ConversationSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    corrected_content = models.TextField(blank=True)  # If there's a grammar correction
    has_mistake = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.role}: {self.content[:50]}'
