from django.urls import path
from . import views

urlpatterns = [
    path('sessions/', views.SessionListView.as_view(), name='sessions'),
    path('start/', views.start_session, name='start-session'),
    path('<int:session_id>/message/', views.send_message, name='send-message'),
    path('<int:session_id>/end/', views.end_session, name='end-session'),
    path('<int:session_id>/', views.session_detail, name='session-detail'),
    path('audio/transcribe/', views.transcribe_audio_view, name='transcribe'),
    path('audio/synthesize/', views.synthesize_speech, name='synthesize'),
    path('translate/', views.translate_japanese_to_english, name='translate-ja-en'),
]
