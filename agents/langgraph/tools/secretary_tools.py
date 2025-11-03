from uuid import UUID

from langchain_core.tools import tool

from core.models import Contact


def create_secretary_tools(contact_id: UUID):
    """
    Cria ferramentas da secretária com contact_id injetado via closure.
    Isso evita que a IA precise adivinhar o contact_id.
    """

    @tool
    def consultar_agendamentos() -> str:
        """
        Consulta as consultas/agendamentos marcados para este paciente.
        Retorna lista de consultas futuras e passadas.
        Não precisa de parâmetros - o sistema já sabe quem você é.
        """
        print(f"🔧 [TOOL CALL] consultar_agendamentos (contact_id={contact_id})")
        try:
            from datetime import datetime, date
            from core.models import Appointment

            # Buscar todos os agendamentos do contato ordenados por data
            appointments = Contact.objects.get(id=contact_id).appointments.all().order_by('date', 'time')

            # ✅ Se não encontrar, retorna imediatamente
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

            # ✅ Retorna sem loop adicional
            return "\n".join(resultado) if resultado else "📅 Você não possui consultas marcadas no momento."

        except Exception as e:
            print(f"❌ [TOOL] Erro ao consultar agendamentos: {e}")
            return f"❌ Erro ao consultar agendamentos: {str(e)}"

    @tool
    def cancelar_agendamento(data: str, hora: str) -> str:
        """
        Cancela uma consulta/agendamento marcado do paciente.
        Remove do Google Calendar e do sistema.

        Parâmetros:
        - data: Data do agendamento no formato DD/MM/YYYY
        - hora: Horário do agendamento no formato HH:MM
        """
        print("\n" + "="*80)
        print(f"🔧 [TOOL CALL] cancelar_agendamento (contact_id={contact_id})")
        print(f"   📅 Data: {data}")
        print(f"   ⏰ Hora: {hora}")
        print("="*80)
        try:
            from datetime import datetime
            from core.models import Appointment
            from google_calendar.services import GoogleCalendarService

            contact = Contact.objects.get(id=contact_id)
            # Parse data e hora
            try:
                data_obj = datetime.strptime(data, '%d/%m/%Y').date()
                hora_obj = datetime.strptime(hora, '%H:%M').time()
                print(f"✅ [TOOL] Data/hora parseadas: {data_obj} {hora_obj}")
            except ValueError as e:
                print(f"❌ [TOOL] Erro ao fazer parse de data/hora: {e}")
                return "❌ Formato de data ou hora inválido. Use DD/MM/YYYY para data e HH:MM para hora."

            # Buscar o agendamento
            print(f"🔍 [TOOL] Buscando agendamento para data={data_obj}, time={hora_obj}")
            try:
                appointment = contact.appointments.get(date=data_obj, time=hora_obj)
                print(f"✅ [TOOL] Agendamento encontrado: #{appointment.id}")
            except Appointment.DoesNotExist:
                print(f"❌ [TOOL] Nenhum agendamento encontrado")
                return f"❌ Não encontrei nenhuma consulta marcada para {data} às {hora}."
            except Appointment.MultipleObjectsReturned:
                print(f"⚠️ [TOOL] Múltiplos agendamentos encontrados")
                return f"❌ Encontrei múltiplas consultas para {data} às {hora}. Por favor, entre em contato com a clínica."

            # Guardar informações para a mensagem de confirmação
            data_formatada = appointment.date.strftime('%d/%m/%Y')
            hora_formatada = appointment.time.strftime('%H:%M')

            # Deletar do Google Calendar se tiver event_id
            calendar_deleted = False
            if appointment.calendar_event_id:
                print(f"📅 [TOOL] Deletando evento do Google Calendar: {appointment.calendar_event_id}")
                try:
                    calendar_service = GoogleCalendarService()
                    success, message = calendar_service.delete_event(contact.id, appointment.calendar_event_id)

                    if success:
                        print(f"✅ [TOOL] Evento deletado do Google Calendar")
                        calendar_deleted = True
                    else:
                        print(f"⚠️ [TOOL] Erro ao deletar do Calendar: {message}")
                        # Continua mesmo se falhar no Calendar
                except Exception as cal_error:
                    print(f"⚠️ [TOOL] Erro ao acessar Google Calendar: {cal_error}")
                    # Continua mesmo se falhar no Calendar
            else:
                print(f"ℹ️ [TOOL] Agendamento não tem event_id do Google Calendar")

            # Deletar o Appointment do banco
            appointment_id = appointment.id
            appointment.delete()
            print(f"✅ [TOOL] Appointment #{appointment_id} deletado do banco de dados")

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

        except Exception as e:
            print(f"❌ [TOOL] Erro ao cancelar agendamento: {e}")
            import traceback
            traceback.print_exc()
            return f"❌ Erro ao cancelar agendamento: {str(e)}"

    @tool
    def gerar_link_agendamento() -> str:
        """
        Gera um link de auto-agendamento para o paciente escolher dia e horário da consulta.
        O link é válido por 48 horas e permite que o paciente selecione entre os horários disponíveis.
        Retorna o link que deve ser enviado ao paciente.
        """
        print(f"🔧 [TOOL CALL] gerar_link_agendamento (contact_id={contact_id})")
        try:
            from datetime import datetime, timedelta
            from django.utils import timezone
            from core.models import Appointment, AppointmentToken
            from django.conf import settings
            import secrets

            contact = Contact.objects.get(id=contact_id)

            # Cria um appointment em rascunho (sem data/hora definida)
            appointment = Appointment.objects.create(
                contact=contact,
                status='draft'
            )
            print(f"✅ [TOOL] Appointment #{appointment.id} criado com status=draft")

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
            print(f"✅ [TOOL] Token criado: {token}")

            # Gera a URL pública
            base_url = settings.BACKEND_BASE_URL.rstrip('/')
            public_url = f"{base_url}/agendar/{token}/"

            print(f"📤 [TOOL] Link gerado: {public_url}")

            expires_formatted = expires_at.strftime('%d/%m/%Y às %H:%M')

            return f"""✅ Link de agendamento gerado com sucesso!

Acesse o link abaixo para escolher o melhor dia e horário:

{public_url}

⏰ Válido até: {expires_formatted}

Você poderá ver todos os horários disponíveis e escolher o que for melhor para você!"""

        except Exception as e:
            print(f"❌ [TOOL] Erro ao gerar link de agendamento: {e}")
            import traceback
            traceback.print_exc()
            return f"❌ Erro ao gerar link de agendamento: {str(e)}"

    return [consultar_agendamentos, cancelar_agendamento, gerar_link_agendamento]