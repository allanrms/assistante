"""
URLs do WebApp
Define todas as rotas para gerenciamento de instâncias Evolution API
"""

from django.urls import path
from . import views

app_name = 'agents'

urlpatterns = [
    # Gerenciamento de Agents/IA
    path('', views.AgentListView.as_view(), name='agent_list'),
    path('create/', views.AgentCreateView.as_view(), name='agent_create'),
    path('<uuid:pk>/', views.AgentDetailView.as_view(), name='agent_detail'),
    path('<uuid:pk>/edit/', views.AgentUpdateView.as_view(), name='agent_edit'),
    path('<uuid:pk>/delete/', views.AgentDeleteView.as_view(), name='agent_delete'),

    # Gerenciamento de Arquivos de Contexto
    path('<uuid:agent_id>/files/', views.AgentFileListView.as_view(), name='agent_file_list'),
    path('<uuid:agent_id>/files/upload/', views.AgentFileUploadView.as_view(), name='agent_file_upload'),
    path('files/<uuid:pk>/edit/', views.AgentFileUpdateView.as_view(), name='agent_file_edit'),
    path('files/<uuid:pk>/delete/', views.AgentFileDeleteView.as_view(), name='agent_file_delete'),
]