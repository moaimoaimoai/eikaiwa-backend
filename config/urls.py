from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.accounts.urls')),
    path('api/phrases/', include('apps.phrases.urls')),
    path('api/conversation/', include('apps.conversation.urls')),
    path('api/mistakes/', include('apps.mistakes.urls')),
    path('api/analysis/', include('apps.analysis.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
