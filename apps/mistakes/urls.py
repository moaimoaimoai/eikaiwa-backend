from django.urls import path
from . import views

urlpatterns = [
    path('', views.MistakeListView.as_view(), name='mistakes-list'),
    path('<int:pk>/', views.MistakeDetailView.as_view(), name='mistake-detail'),
    path('<int:pk>/mastered/', views.mark_mastered, name='mark-mastered'),
    path('quiz/', views.mistakes_quiz, name='mistakes-quiz'),
    path('quiz/submit/', views.submit_quiz_answer, name='submit-quiz'),
    path('summary/', views.mistakes_summary, name='mistakes-summary'),
]
