import os
import json
import traceback
import uuid
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from .models import GoogleCalendarAuth, CalendarIntegrationRequest


class GoogleCalendarService:
    SCOPES = ['https://www.googleapis.com/auth/calendar']

    def __init__(self):
        self.client_id = settings.GOOGLE_OAUTH2_CLIENT_ID
        self.client_secret = settings.GOOGLE_OAUTH2_CLIENT_SECRET
        self.redirect_uri = settings.GOOGLE_OAUTH2_REDIRECT_URI

    def get_authorization_url(self, whatsapp_number, evolution_instance=None, user_id=None):
        """
        Gera URL de autorização do Google OAuth2 para um número do WhatsApp
        """
        request_token = str(uuid.uuid4())

        # Salva a solicitação de integração com evolution_instance e user_id
        CalendarIntegrationRequest.objects.create(
            whatsapp_number=whatsapp_number,
            request_token=request_token,
            evolution_instance=evolution_instance,
            user_id=user_id
        )

        # Configura o fluxo OAuth2
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uris": [self.redirect_uri],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            },
            scopes=self.SCOPES
        )
        flow.redirect_uri = self.redirect_uri

        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=request_token
        )

        return authorization_url

    def handle_oauth_callback(self, code, state):
        """
        Processa o callback do OAuth2 e salva as credenciais
        """
        try:
            # Busca a solicitação de integração
            integration_request = CalendarIntegrationRequest.objects.get(
                request_token=state,
                is_completed=False
            )

            # Configura o fluxo OAuth2
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "redirect_uris": [self.redirect_uri],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token"
                    }
                },
                scopes=self.SCOPES,
                state=state
            )
            flow.redirect_uri = self.redirect_uri

            # Troca o código por tokens
            flow.fetch_token(code=code)
            credentials = flow.credentials

            # Cria ou atualiza usuário (pode ser melhorado)
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user, created = User.objects.get_or_create(
                username=f"whatsapp_{integration_request.whatsapp_number}",
                defaults={'email': f"whatsapp_{integration_request.whatsapp_number}@example.com"}
            )

            # Usa a instância Evolution diretamente da solicitação
            evolution_instance = integration_request.evolution_instance

            # Salva as credenciais vinculando com a instância
            GoogleCalendarAuth.objects.update_or_create(
                user=user,
                defaults={
                    'access_token': credentials.token,
                    'refresh_token': credentials.refresh_token,
                    'expires_at': timezone.make_aware(datetime.fromtimestamp(credentials.expiry.timestamp())),
                    'whatsapp_number': integration_request.whatsapp_number,
                    'evolution_instance': evolution_instance,
                }
            )

            # Marca a solicitação como completada
            integration_request.is_completed = True
            integration_request.completed_at = timezone.now()
            integration_request.save()

            return True, "Integração com Google Calendar realizada com sucesso!"

        except CalendarIntegrationRequest.DoesNotExist:
            traceback.print_exc()
            return False, "Solicitação de integração não encontrada ou já processada."
        except Exception as e:
            traceback.print_exc()
            return False, f"Erro ao processar autenticação: {str(e)}"

    def get_calendar_service(self, whatsapp_number):
        """
        Retorna o serviço do Google Calendar para um número do WhatsApp
        """
        try:
            print(f'get_calendar_service {whatsapp_number}')

            calendar_auth = GoogleCalendarAuth.objects.get(whatsapp_number=whatsapp_number)

            # Verifica se o token precisa ser renovado
            if timezone.now() >= calendar_auth.expires_at:
                self._refresh_token(calendar_auth)

            credentials = Credentials(
                token=calendar_auth.access_token,
                refresh_token=calendar_auth.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            service = build('calendar', 'v3', credentials=credentials)
            return service

        except GoogleCalendarAuth.DoesNotExist:
            traceback.print_exc()
            return None

    def _refresh_token(self, calendar_auth):
        """
        Renova o token de acesso
        """
        credentials = Credentials(
            token=calendar_auth.access_token,
            refresh_token=calendar_auth.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret
        )

        credentials.refresh(Request())

        # Atualiza no banco de dados
        calendar_auth.access_token = credentials.token
        calendar_auth.expires_at = timezone.make_aware(datetime.fromtimestamp(credentials.expiry.timestamp()))
        calendar_auth.save()

    def create_event(self, whatsapp_number, event_data):
        """
        Cria um evento no Google Calendar
        """
        service = self.get_calendar_service(whatsapp_number)
        if not service:
            return False, "Usuário não autenticado com Google Calendar."

        try:
            event = service.events().insert(calendarId='primary', body=event_data).execute()
            return True, f"Evento criado com sucesso: {event.get('htmlLink')}"
        except Exception as e:
            traceback.print_exc()
            return False, f"Erro ao criar evento: {str(e)}"

    def list_events(self, whatsapp_number, max_results=100):
        """
        Lista eventos do Google Calendar
        """
        service = self.get_calendar_service(whatsapp_number)
        if not service:
            return False, "Usuário não autenticado com Google Calendar."

        try:
            now = datetime.utcnow().isoformat() + 'Z'
            events_result = service.events().list(
                calendarId='primary',
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])

            return True, events
        except Exception as e:
            traceback.print_exc()
            return False, f"Erro ao listar eventos: {str(e)}"

    def delete_event(self, whatsapp_number, event_id):
        """
        Deleta um evento do Google Calendar
        """
        service = self.get_calendar_service(whatsapp_number)
        if not service:
            return False, "Usuário não autenticado com Google Calendar."

        try:
            service.events().delete(calendarId='primary', eventId=event_id).execute()
            return True, f"Evento {event_id} deletado com sucesso."
        except Exception as e:
            traceback.print_exc()
            return False, f"Erro ao deletar evento {event_id}: {str(e)}"