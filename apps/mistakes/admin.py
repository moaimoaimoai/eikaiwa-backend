from django.contrib import admin
from .models import Mistake

@admin.register(Mistake)
class MistakeAdmin(admin.ModelAdmin):
    list_display = ['original_text', 'corrected_text', 'mistake_type', 'user', 'is_mastered']
    list_filter = ['mistake_type', 'is_mastered']
