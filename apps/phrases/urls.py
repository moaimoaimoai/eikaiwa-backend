from django.urls import path
from . import views

urlpatterns = [
    path('categories/', views.CategoryListView.as_view(), name='categories'),
    path('warmup/', views.WarmupPhrasesView.as_view(), name='warmup-phrases'),
    path('list/', views.PhraseListView.as_view(), name='phrase-list'),
    path('words/', views.WordListView.as_view(), name='word-list'),
    path('<int:phrase_id>/practiced/', views.mark_phrase_practiced, name='mark-practiced'),
    path('quiz/phrases/', views.quiz_phrases, name='quiz-phrases'),
    path('quiz/words/', views.quiz_words, name='quiz-words'),
    path('ai-warmup/', views.ai_warmup, name='ai-warmup'),
    path('ai-words/', views.ai_words, name='ai-words'),
    # フレーズ帳
    path('saved/', views.saved_phrases_list, name='saved-phrases-list'),
    path('saved/bulk/', views.saved_phrases_bulk_create, name='saved-phrases-bulk'),
    path('saved/<int:phrase_id>/delete/', views.saved_phrase_delete, name='saved-phrase-delete'),
    path('saved/<int:phrase_id>/mastered/', views.saved_phrase_toggle_mastered, name='saved-phrase-mastered'),
]
