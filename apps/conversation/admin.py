from django.contrib import admin
from .models import ConversationSession, ConversationMessage

@admin.register(ConversationSession)
class SessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'topic', 'message_count', 'mistake_count', 'created_at']

@admin.register(ConversationMessage)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['session', 'role', 'has_mistake', 'created_at']
