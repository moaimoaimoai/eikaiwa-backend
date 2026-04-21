from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Category(models.Model):
    name = models.CharField(max_length=50)
    name_ja = models.CharField(max_length=50)
    icon = models.CharField(max_length=10, default='💬')
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name


class Phrase(models.Model):
    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='phrases')
    english = models.CharField(max_length=300)
    japanese = models.CharField(max_length=300)
    pronunciation_hint = models.CharField(max_length=300, blank=True)
    example_context = models.CharField(max_length=500, blank=True)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='beginner')
    audio_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.english


class Word(models.Model):
    PART_OF_SPEECH_CHOICES = [
        ('noun', 'Noun'),
        ('verb', 'Verb'),
        ('adjective', 'Adjective'),
        ('adverb', 'Adverb'),
        ('phrase', 'Phrase'),
        ('idiom', 'Idiom'),
    ]

    word = models.CharField(max_length=100)
    definition = models.CharField(max_length=300)
    definition_ja = models.CharField(max_length=300)
    part_of_speech = models.CharField(max_length=20, choices=PART_OF_SPEECH_CHOICES, default='noun')
    example_sentence = models.CharField(max_length=500)
    example_sentence_ja = models.CharField(max_length=500, blank=True)
    level = models.CharField(max_length=20, default='beginner')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.word


class UserPhraseProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='phrase_progress')
    phrase = models.ForeignKey(Phrase, on_delete=models.CASCADE)
    practiced_count = models.IntegerField(default=0)
    is_mastered = models.BooleanField(default=False)
    last_practiced = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'phrase']


class AIWarmupSession(models.Model):
    """AIが生成したウォームアップフレーズの履歴（重複防止用）"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_warmup_sessions')
    phrases_shown = models.JSONField(default=list, help_text='表示したフレーズのハッシュリスト（重複防止）')
    phrases_data = models.JSONField(default=list, help_text='生成したフレーズの全データ（上限到達時の再表示用）')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'AIWarmup {self.user.email} @ {self.created_at.date()}'


class AIWordSession(models.Model):
    """AIが生成した単語の履歴（重複防止・1日上限管理用）"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_word_sessions')
    words_shown = models.JSONField(default=list, help_text='表示した単語のハッシュリスト（重複防止）')
    words_data = models.JSONField(default=list, help_text='生成した単語の全データ（上限到達時の再表示用）')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'AIWord {self.user.email} @ {self.created_at.date()}'


class SavedPhrase(models.Model):
    """会話中のコーチング・サマリーから自動保存される便利フレーズ帳"""
    SOURCE_CHOICES = [
        ('coaching', '会話中コーチング'),
        ('summary',  '会話サマリー'),
        ('correction', '添削フレーズ'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_phrases')
    session = models.ForeignKey(
        'conversation.ConversationSession',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='saved_phrases',
    )
    english = models.CharField(max_length=500)
    japanese = models.CharField(max_length=500)
    context_ja = models.TextField(blank=True)    # 使える場面メモ
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='coaching')
    session_topic = models.CharField(max_length=50, blank=True)
    is_mastered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.english[:40]} ({self.user.email})'
