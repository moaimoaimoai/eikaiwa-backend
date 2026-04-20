from django.contrib import admin
from .models import Category, Phrase, Word, UserPhraseProgress

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'name_ja', 'icon', 'order']

@admin.register(Phrase)
class PhraseAdmin(admin.ModelAdmin):
    list_display = ['english', 'japanese', 'level', 'category']
    list_filter = ['level', 'category']

@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    list_display = ['word', 'definition_ja', 'level', 'part_of_speech']
    list_filter = ['level']
