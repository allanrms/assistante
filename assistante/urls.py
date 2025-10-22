"""
URL configuration for assistante project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),  # Rotas de cadastro e conta de clientes
    path('whatsapp_connector/v1/', include('whatsapp_connector.api.v1.urls')),
    path('agents/', include('agents.urls')),  # Agent management URLs
    path('whatsapp/', include('whatsapp_connector.urls')),  # WhatsApp connector URLs
    path('google-calendar/', include('google_calendar.urls')),  # Google Calendar integration URLs
    path('dialog-test/', include('dialog_test.urls')),  # Dialog Test URLs
    # path('ai-assistant/', include('django_ai_assistant.urls')),  # AI Assistant URLs
    path('', include('webapp.urls')),  # WebApp como página inicial
]

# Servir arquivos de media em desenvolvimento (mesmo com DEBUG=False)
if settings.DEBUG or True:  # Força servir media em desenvolvimento
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += staticfiles_urlpatterns()

# swagger
urlpatterns += [
    # schema generation
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    # Swagger UI
    path('docs/loja/<str:slug>', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
