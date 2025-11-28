"""
Service Layer para gerenciamento de agendamentos.

Centraliza lógica de negócio relacionada a Appointments,
seguindo o princípio Single Responsibility das best practices LangChain.
"""

from datetime import datetime, date, timedelta
from typing import Optional, Tuple
from uuid import UUID

from django.utils import timezone
from django.conf import settings
import secrets

from core.models import Contact, Appointment, AppointmentToken


class AppointmentService:
    """
    Service para operações com agendamentos.

    Attributes:
        contact_id: UUID do contato
        contact: Instância do Contact (lazy loading)
    """

    def __init__(self, contact_id: UUID):
        """
        Args:
            contact_id: UUID do contato
        """
        self.contact_id = contact_id
        self._contact = None

    @property
    def contact(self) -> Contact:
        """Lazy loading do contato."""
        if self._contact is None:
            self._contact = Contact.objects.get(id=self.contact_id)
        return self._contact

    def list_appointments(self) -> str:
        """
        Lista agendamentos do contato (futuros e passados).

        Returns:
            String formatada com lista de agendamentos
        """
        # Buscar todos os agendamentos do contato ordenados por data
        appointments = self.contact.appointments.filter(
            scheduled_for__isnull=False
        ).order_by('date', 'time')

        # Se não encontrar, retorna imediatamente
        if not appointments.exists():
            return "📅 Você não possui consultas marcadas no momento."

        hoje = date.today()
        agora = datetime.now().time()

        future_appointments = []
        past_appointments = []

        for apt in appointments:
            if apt.date > hoje or (apt.date == hoje and apt.time >= agora):
                future_appointments.append(apt)
            else:
                past_appointments.append(apt)

        resultado = []

        # Futuras
        if future_appointments:
            resultado.append("📅 Consultas Agendadas (Próximas):\n")
            for i, apt in enumerate(future_appointments, 1):
                data_formatada = f"{apt.date.strftime('%d/%m/%Y')} às {apt.time.strftime('%H:%M')}"
                dia_semana_pt = {
                    'Monday': 'segunda-feira',
                    'Tuesday': 'terça-feira',
                    'Wednesday': 'quarta-feira',
                    'Thursday': 'quinta-feira',
                    'Friday': 'sexta-feira',
                    'Saturday': 'sábado',
                    'Sunday': 'domingo'
                }.get(apt.date.strftime('%A'), apt.date.strftime('%A'))
                resultado.append(f"{i}. {data_formatada} ({dia_semana_pt})")

        # Passadas (últimas 3)
        if past_appointments:
            if future_appointments:
                resultado.append("")  # linha em branco
            resultado.append("📋 Consultas Anteriores (Histórico):\n")
            for i, apt in enumerate(list(reversed(past_appointments))[:3], 1):
                data_formatada = f"{apt.date.strftime('%d/%m/%Y')} às {apt.time.strftime('%H:%M')}"
                resultado.append(f"{i}. {data_formatada}")

        return "\n".join(resultado) if resultado else "📅 Você não possui consultas marcadas no momento."

    def cancel_appointment(self, data: str, hora: str) -> str:
        """
        Cancela um agendamento.

        Args:
            data: Data no formato DD/MM/YYYY
            hora: Hora no formato HH:MM

        Returns:
            Mensagem de sucesso ou erro
        """
        # Parse data e hora
        try:
            data_obj = datetime.strptime(data, '%d/%m/%Y').date()
            hora_obj = datetime.strptime(hora, '%H:%M').time()
            print(f"✅ [Service] Data/hora parseadas: {data_obj} {hora_obj}")
        except ValueError as e:
            print(f"❌ [Service] Erro ao fazer parse de data/hora: {e}")
            return "❌ Formato de data ou hora inválido. Use DD/MM/YYYY para data e HH:MM para hora."

        # Buscar o agendamento
        print(f"🔍 [Service] Buscando agendamento para data={data_obj}, time={hora_obj}")
        try:
            appointment = self.contact.appointments.get(date=data_obj, time=hora_obj)
            print(f"✅ [Service] Agendamento encontrado: #{appointment.id}")
        except Appointment.DoesNotExist:
            print(f"❌ [Service] Nenhum agendamento encontrado")
            return f"❌ Não encontrei nenhuma consulta marcada para {data} às {hora}."
        except Appointment.MultipleObjectsReturned:
            print(f"⚠️ [Service] Múltiplos agendamentos encontrados")
            return f"❌ Encontrei múltiplas consultas para {data} às {hora}. Por favor, entre em contato com a clínica."

        # Guardar informações para a mensagem de confirmação
        data_formatada = appointment.date.strftime('%d/%m/%Y')
        hora_formatada = appointment.time.strftime('%H:%M')

        # Deletar do Google Calendar se tiver event_id
        calendar_deleted = self._delete_from_calendar(appointment)

        # Deletar o Appointment do banco
        appointment_id = appointment.id
        appointment.delete()
        print(f"✅ [Service] Appointment #{appointment_id} deletado do banco de dados")

        # Mensagem de sucesso
        if calendar_deleted:
            return f"""✅ Consulta cancelada com sucesso!
📅 Data: {data_formatada}
⏰ Horário: {hora_formatada}

O agendamento foi removido do sistema e do Google Calendar."""
        else:
            return f"""✅ Consulta cancelada!
📅 Data: {data_formatada}
⏰ Horário: {hora_formatada}

O agendamento foi removido do sistema."""

    def _delete_from_calendar(self, appointment: Appointment) -> bool:
        """
        Deleta agendamento do Google Calendar.

        Args:
            appointment: Instância do Appointment

        Returns:
            True se deletado com sucesso, False caso contrário
        """
        if not appointment.calendar_event_id:
            print(f"ℹ️ [Service] Agendamento não tem event_id do Google Calendar")
            return False

        print(f"📅 [Service] Deletando evento do Google Calendar: {appointment.calendar_event_id}")
        try:
            from google_calendar.services import GoogleCalendarService

            calendar_service = GoogleCalendarService()
            success, message = calendar_service.delete_event(
                self.contact.id,
                appointment.calendar_event_id
            )

            if success:
                print(f"✅ [Service] Evento deletado do Google Calendar")
                return True
            else:
                print(f"⚠️ [Service] Erro ao deletar do Calendar: {message}")
                return False
        except Exception as cal_error:
            print(f"⚠️ [Service] Erro ao acessar Google Calendar: {cal_error}")
            return False

    def generate_appointment_link(self) -> str:
        """
        Gera link de auto-agendamento para o paciente.

        Returns:
            String com link e validade
        """
        # Cria um appointment em rascunho (sem data/hora definida)
        appointment = Appointment.objects.create(
            contact=self.contact,
            status='draft'
        )
        print(f"✅ [Service] Appointment #{appointment.id} criado com status=draft")

        # Gera token único
        token = secrets.token_urlsafe(32)

        # Define expiração para 48 horas
        expires_at = timezone.now() + timedelta(hours=48)

        # Cria o token de agendamento
        appointment_token = AppointmentToken.objects.create(
            appointment=appointment,
            token=token,
            expires_at=expires_at
        )
        print(f"✅ [Service] Token criado: {token}")

        # Gera a URL pública
        base_url = settings.BACKEND_BASE_URL.rstrip('/')
        public_url = f"{base_url}/agendar/{token}/"

        print(f"📤 [Service] Link gerado: {public_url}")

        expires_formatted = expires_at.strftime('%d/%m/%Y às %H:%M')

        # Retorna apenas as informações essenciais
        return f"""Link: {public_url}
Válido até: {expires_formatted}"""