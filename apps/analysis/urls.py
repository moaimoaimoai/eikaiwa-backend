from django.urls import path
from . import views

urlpatterns = [
    path('trends/', views.trend_analysis, name='trends'),
]
