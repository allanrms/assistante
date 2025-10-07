from django.urls import path
from . import views
from .webhook_views import ConfigureWebhookView

app_name = 'whatsapp_connector'

urlpatterns = [
    # Messages
    path('messages/', views.MessageHistoryListView.as_view(), name='message_list'),
    
    # Gerenciamento de instâncias
    path('instances/', views.InstanceListView.as_view(), name='instance_list'),
    path('instances/create/', views.InstanceCreateView.as_view(), name='instance_create'),
    path('instances/<uuid:pk>/', views.InstanceDetailView.as_view(), name='instance_detail'),
    path('instances/<uuid:pk>/edit/', views.InstanceUpdateView.as_view(), name='instance_edit'),
    path('instances/<uuid:pk>/delete/', views.InstanceDeleteView.as_view(), name='instance_delete'),

    # Ações das instâncias
    path('instances/<uuid:pk>/connect/', views.connect_instance, name='instance_connect'),
    path('instances/<uuid:pk>/logout/', views.logout_instance, name='instance_logout'),

    # APIs AJAX
    path('instances/<uuid:pk>/qr-code/', views.get_qr_code, name='instance_qr_code'),
    path('instances/<uuid:pk>/status/', views.instance_status, name='instance_status'),
    path('instances/<uuid:pk>/update-info/', views.update_connection_info, name='instance_update_info'),
    path('instances/<uuid:pk>/toggle-ignore-own/', views.toggle_ignore_own_messages, name='instance_toggle_ignore_own'),
    path('instances/<uuid:pk>/toggle-active/', views.toggle_instance_active, name='instance_toggle_active'),

    # Sincronização
    path('instances/sync/', views.sync_instances, name='instance_sync'),
    path('instances/sync-numbers/', views.sync_phone_numbers, name='instance_sync_numbers'),

    # Webhook configuration
    path('instances/<uuid:pk>/webhook/', ConfigureWebhookView.as_view(), name='instance_webhook'),
    path('instances/<uuid:pk>/webhook/config/', views.configure_webhook, name='instance_webhook_config'),
    
    # Contact configuration
    path('instances/<uuid:pk>/contacts/', views.configure_contacts, name='instance_contacts_config'),
]