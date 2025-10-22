"""
Dialog Test URLs
"""
from django.urls import path
from . import views

app_name = 'dialog_test'

urlpatterns = [
    # Chat único
    path('', views.chat_view, name='chat'),
    path('send/', views.send_message, name='send_message'),
    path('client/<uuid:client_id>/llm-configs/', views.get_client_llm_configs, name='get_client_llm_configs'),
    path('clear/', views.clear_chat, name='clear_chat'),
]
