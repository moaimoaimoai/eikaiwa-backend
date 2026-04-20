from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=50, blank=True)
    level = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
        ],
        default='beginner'
    )
    total_conversations = models.IntegerField(default=0)
    total_minutes = models.IntegerField(default=0)
    streak_days = models.IntegerField(default=0)
    last_active_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # ── サブスクリプション ──
    SUBSCRIPTION_CHOICES = [
        ('free', 'Free'),
        ('premium', 'Premium'),
    ]
    subscription_tier = models.CharField(max_length=20, choices=SUBSCRIPTION_CHOICES, default='free')
    subscription_expires_at = models.DateTimeField(null=True, blank=True)

    # ── 月次使用量 ──
    monthly_sessions_used = models.IntegerField(default=0)
    monthly_reset_date = models.DateField(null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

    @property
    def name(self):
        return self.display_name or self.username

    @property
    def is_premium(self):
        if self.subscription_tier == 'premium':
            if self.subscription_expires_at and self.subscription_expires_at > timezone.now():
                return True
        return False

    @property
    def monthly_limit(self):
        return 100 if self.is_premium else 3  # freeは3回お試し

    def reset_monthly_if_needed(self):
        """月が変わったらカウンターをリセット"""
        today = timezone.now().date()
        if not self.monthly_reset_date or self.monthly_reset_date.month != today.month or self.monthly_reset_date.year != today.year:
            self.monthly_sessions_used = 0
            self.monthly_reset_date = today
            self.save(update_fields=['monthly_sessions_used', 'monthly_reset_date'])

    def can_start_session(self):
        self.reset_monthly_if_needed()
        return self.monthly_sessions_used < self.monthly_limit


class UserMemory(models.Model):
    """ユーザーごとの記憶：過去の会話から学習した情報を蓄積する"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='memory')
    interests = models.TextField(blank=True, help_text='ユーザーの趣味・関心（AI抽出）')
    occupation = models.CharField(max_length=200, blank=True, help_text='職業・仕事')
    personal_facts = models.TextField(blank=True, help_text='個人的な情報（家族、出身地など）')
    common_mistakes = models.TextField(blank=True, help_text='よくするミスのパターン')
    topics_discussed = models.JSONField(default=list, help_text='これまで話したトピック一覧')
    session_count = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Memory of {self.user.email}'

    def to_context_string(self):
        """AIへ渡す記憶コンテキスト文字列を生成"""
        parts = []
        if self.session_count > 0:
            parts.append(f"This user has had {self.session_count} conversation session(s) with you before.")
        if self.interests:
            parts.append(f"Their known interests: {self.interests}")
        if self.occupation:
            parts.append(f"Their occupation/background: {self.occupation}")
        if self.personal_facts:
            parts.append(f"Personal facts you've learned: {self.personal_facts}")
        if self.common_mistakes:
            parts.append(f"Common mistakes to watch for: {self.common_mistakes}")
        if self.topics_discussed:
            recent = self.topics_discussed[-5:]  # 直近5トピック
            parts.append(f"Topics recently discussed: {', '.join(recent)}")
        return '\n'.join(parts) if parts else ''
