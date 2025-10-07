from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    # EvolutionInstanceViewSet,
    EvolutionWebhookView, 
    MessageListView, 
    MessageDetailView,
)

# Configuração do router para ViewSets
router = DefaultRouter()
# router.register(r'instances', EvolutionInstanceViewSet, basename='instances')

urlpatterns = [
    # API REST com ViewSet (CRUD completo + actions customizadas)
    path('api/', include(router.urls)),
    
    # Webhooks
    path('evolution/webhook/receiver', EvolutionWebhookView.as_view(), name='evolution_webhook_receiver'),
    
    # APIs de mensagens (podem ser migradas para ViewSet futuramente)
    path('messages', MessageListView.as_view(), name='message_list'),
    path('messages/<str:message_id>', MessageDetailView.as_view(), name='message_detail'),
    
]
