"""
URLs do WebApp
Define todas as rotas para gerenciamento de instâncias Evolution API
"""

from django.urls import path
from . import views

app_name = 'agents'

urlpatterns = [
    # Gerenciamento de Assistants/IA
    path('assistants/', views.AssistantListView.as_view(), name='assistant_list'),
    path('assistants/create/', views.AssistantCreateView.as_view(), name='assistant_create'),
    path('assistants/<uuid:pk>/', views.AssistantDetailView.as_view(), name='assistant_detail'),
    path('assistants/<uuid:pk>/edit/', views.AssistantUpdateView.as_view(), name='assistant_edit'),
    path('assistants/<uuid:pk>/delete/', views.AssistantDeleteView.as_view(), name='assistant_delete'),

    # Gerenciamento de Arquivos de Contexto
    path('assistants/<uuid:llm_config_id>/context-files/', views.AssistantContextFileListView.as_view(), name='context_file_list'),
    path('assistants/<uuid:llm_config_id>/context-files/upload/', views.AssistantContextFileUploadView.as_view(), name='context_file_upload'),
    path('context-files/<uuid:pk>/edit/', views.AssistantContextFileUpdateView.as_view(), name='context_file_edit'),
    path('context-files/<uuid:pk>/delete/', views.AssistantContextFileDeleteView.as_view(), name='context_file_delete'),
]