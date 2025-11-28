"""
URLs do Client Painel
Define rotas de autenticação e dashboard principal
"""

from django.urls import path
from . import views

app_name = 'client_painel'

urlpatterns = [
    # Autenticação
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboard principal
    path('', views.webapp_home, name='home'),
    path('home/', views.webapp_home, name='home_alt'),

    # Perfil do usuário
    path('perfil/', views.profile_view, name='profile'),

    # Agenda
    path('agenda/', views.AgendaView.as_view(), name='agenda'),
    path('agenda/configuracoes/', views.ScheduleSettingsView.as_view(), name='schedule_settings'),
    path('agenda/api/availability/', views.ScheduleAvailabilityView.as_view(), name='schedule_availability'),

    # Appointments (CRUD)
    path('appointments/create/', views.AppointmentCreateView.as_view(), name='appointment_create'),
    path('appointments/<int:appointment_id>/', views.AppointmentUpdateView.as_view(), name='appointment_update'),
    path('appointments/<int:appointment_id>/delete/', views.AppointmentDeleteView.as_view(), name='appointment_delete'),

    # API endpoints para idioma
    path('api/languages/', views.get_available_languages, name='api_available_languages'),
    path('api/language/', views.get_user_language, name='api_get_user_language'),
    path('api/language/set/', views.set_user_language, name='api_set_user_language'),

    # Services (CRUD) - usando django.views.generic
    path('servicos/', views.ServiceListView.as_view(), name='service_list'),
    path('servicos/create/', views.ServiceCreateView.as_view(), name='service_create'),
    path('servicos/<uuid:service_id>/', views.ServiceUpdateView.as_view(), name='service_edit'),
    path('servicos/<uuid:service_id>/delete/', views.ServiceDeleteView.as_view(), name='service_delete'),

    # API endpoints para conversas com atendimento humano
    path('human-conversations/', views.HumanConversationsListView.as_view(), name='api_human_conversations'),
    path('human-conversations/count/', views.HumanConversationsCountView.as_view(), name='api_human_conversations_count'),
    path('human-conversations/<int:conversation_id>/close/', views.CloseConversationView.as_view(), name='api_close_conversation'),

    # Contatos
    path('contatos/', views.ContactsView.as_view(), name='contacts'),
    path('api/contatos/<uuid:contact_id>/conversas/', views.ContactConversationsView.as_view(), name='api_contact_conversations'),
    path('api/conversas/<int:conversation_id>/mensagens/', views.ConversationMessagesView.as_view(), name='api_conversation_messages'),
]