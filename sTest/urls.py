from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    path('api/', include('user_manager.urls')),
    path('api/', include("course_manager.urls")),
    path('api/', include("test_manager.urls")),
    path('api/', include("system_manager.urls")),
    path('api/', include("notification_manager.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
