"""
Ferramentas da secretária para o agente.

Define ferramentas que permitem ao agente gerenciar agendamentos do paciente.
O contexto é passado via ToolRuntime para ser thread-safe.
"""
import traceback
from typing import TYPE_CHECKING
from langchain.tools import tool, ToolRuntime

if TYPE_CHECKING:
    from agents.models import Conversation


@tool
def consultar_agendamentos(runtime: ToolRuntime) -> str:
    """
    Consulta as consultas/agendamentos marcados para este paciente.

    Retorna lista de consultas futuras e passadas.
    Não precisa de parâmetros - o sistema já sabe quem é o paciente.

    Returns:
        str: Lista formatada de agendamentos ou mensagem se não houver
    """
    try:
        conversation = runtime.context["conversation"]
        if not conversation:
            return "❌ Erro: Conversa não encontrada no contexto."

        contact = conversation.contact
        if not contact:
            return "❌ Erro: Contato não encontrado."

        print(f"🔧 [TOOL CALL] consultar_agendamentos (contact_id={contact.id})")

        from datetime import datetime, date
        from core.models import Appointment

        # Buscar todos os agendamentos do contato ordenados por data
        appointments = contact.appointments.filter(scheduled_for__isnull=False).order_by('date', 'time')

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
                resultado.append(f"{i}. {data_formatada} ({dia_semana_pt}) [ID: {apt.id}]")

        # Passadas (últimas 3)
        if past_appointments:
            if future_appointments:
                resultado.append("")  # linha em branco
            resultado.append("📋 Consultas Anteriores (Histórico):\n")
            for i, apt in enumerate(list(reversed(past_appointments))[:3], 1):
                data_formatada = f"{apt.date.strftime('%d/%m/%Y')} às {apt.time.strftime('%H:%M')}"
                resultado.append(f"{i}. {data_formatada} [ID: {apt.id}]")

        # Retorna sem loop adicional
        return "\n".join(resultado) if resultado else "📅 Você não possui consultas marcadas no momento."

    except Exception as e:
        traceback.print_exc()
        print(f"❌ [TOOL] Erro ao consultar agendamentos: {e}")
        return f"❌ Erro ao consultar agendamentos: {str(e)}"


@tool
def cancelar_agendamento(appointment_id: int, runtime: ToolRuntime) -> str:
    """
    Cancela uma consulta/agendamento marcado do paciente.

    Remove do Google Calendar e do sistema.

    Args:
        appointment_id: ID da consulta que deseja cancelar (obtido via consultar_agendamentos)

    Returns:
        str: Mensagem de sucesso ou erro
    """
    try:
        conversation = runtime.context["conversation"]
        if not conversation:
            return "❌ Erro: Conversa não encontrada no contexto."

        contact = conversation.contact
        if not contact:
            return "❌ Erro: Contato não encontrado."

        print("\n" + "="*80)
        print(f"🔧 [TOOL CALL] cancelar_agendamento (contact_id={contact.id})")
        print(f"   🆔 Appointment ID: {appointment_id}")
        print("="*80)

        from core.models import Appointment
        from google_calendar.services import GoogleCalendarService

        # Buscar o agendamento pelo ID
        print(f"🔍 [TOOL] Buscando agendamento ID={appointment_id}")
        try:
            appointment = contact.appointments.get(id=appointment_id)
            print(f"✅ [TOOL] Agendamento encontrado: #{appointment.id}")
        except Appointment.DoesNotExist:
            print(f"❌ [TOOL] Nenhum agendamento encontrado")
            return f"❌ Não encontrei nenhuma consulta com ID {appointment_id} para este paciente."

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
        traceback.print_exc()
        return f"❌ Erro ao cancelar agendamento: {str(e)}"


@tool
def reagendar_consulta(appointment_id: int, runtime: ToolRuntime) -> str:
    """
    Reagenda uma consulta existente do paciente.

    Cancela a consulta atual e gera um novo link de agendamento para o paciente escolher
    uma nova data e horário disponível.

    FLUXO RECOMENDADO:
    1. Use consultar_agendamentos para listar as consultas do paciente
    2. Mostre as consultas e pergunte qual deseja reagendar
    3. Use esta ferramenta com o ID da consulta escolhida
    4. A ferramenta cancelará a consulta antiga e retornará um novo link

    Args:
        appointment_id: ID da consulta que deseja reagendar (obtido via consultar_agendamentos)

    Returns:
        str: Confirmação do cancelamento + link de agendamento novo
    """
    try:
        conversation = runtime.context["conversation"]
        if not conversation:
            return "❌ Erro: Conversa não encontrada no contexto."

        contact = conversation.contact
        if not contact:
            return "❌ Erro: Contato não encontrado."

        print("\n" + "="*80)
        print(f"🔧 [TOOL CALL] reagendar_consulta (contact_id={contact.id})")
        print(f"   🆔 Appointment ID: {appointment_id}")
        print("="*80)

        from core.models import Appointment
        from google_calendar.services import GoogleCalendarService
        from datetime import datetime, timedelta
        from django.utils import timezone
        from core.models import AppointmentToken
        from django.conf import settings
        import secrets

        # 1. BUSCAR E VALIDAR O AGENDAMENTO
        print(f"🔍 [TOOL] Buscando agendamento ID={appointment_id}")
        try:
            appointment = contact.appointments.get(id=appointment_id)
            print(f"✅ [TOOL] Agendamento encontrado: #{appointment.id}")
        except Appointment.DoesNotExist:
            print(f"❌ [TOOL] Nenhum agendamento encontrado")
            return f"❌ Não encontrei nenhuma consulta com ID {appointment_id} para este paciente."

        # Verificar se a consulta já passou
        from datetime import date
        hoje = date.today()
        agora = datetime.now().time()

        if appointment.date and appointment.time:
            if appointment.date < hoje or (appointment.date == hoje and appointment.time < agora):
                print(f"⚠️ [TOOL] Tentativa de reagendar consulta passada")
                return f"❌ Não é possível reagendar uma consulta que já passou. Esta consulta era para {appointment.date.strftime('%d/%m/%Y')} às {appointment.time.strftime('%H:%M')}."

        # Guardar informações para a mensagem de confirmação
        data_formatada = appointment.date.strftime('%d/%m/%Y') if appointment.date else "Data não definida"
        hora_formatada = appointment.time.strftime('%H:%M') if appointment.time else "Horário não definido"

        # 2. CANCELAR AGENDAMENTO ANTIGO
        print(f"🗑️ [TOOL] Iniciando cancelamento da consulta antiga...")

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
            except Exception as cal_error:
                print(f"⚠️ [TOOL] Erro ao acessar Google Calendar: {cal_error}")
        else:
            print(f"ℹ️ [TOOL] Agendamento não tem event_id do Google Calendar")

        # Deletar o Appointment do banco
        old_appointment_id = appointment.id
        appointment.delete()
        print(f"✅ [TOOL] Appointment #{old_appointment_id} deletado do banco de dados")

        # 3. GERAR NOVO LINK DE AGENDAMENTO
        print(f"🔗 [TOOL] Gerando novo link de agendamento...")

        # Verificar se já existe um token válido e não usado para este contato
        existing_token = AppointmentToken.objects.filter(
            appointment__contact=contact,
            appointment__status='draft',
            is_used=False,
            expires_at__gt=timezone.now()
        ).select_related('appointment').first()

        if existing_token:
            print(f"♻️ [TOOL] Link válido existente encontrado (Token #{existing_token.id})")

            # VALIDAÇÃO: Verifica se o token realmente existe e não foi usado
            if existing_token.is_used:
                print(f"⚠️ [TOOL] ATENÇÃO: Token #{existing_token.id} foi marcado como usado!")
                existing_token = None
            elif not existing_token.appointment:
                print(f"⚠️ [TOOL] ATENÇÃO: Token #{existing_token.id} não tem appointment associado!")
                existing_token = None

        if existing_token:
            # Reutiliza o token existente
            appointment_token = existing_token
            base_url = settings.BACKEND_BASE_URL.rstrip('/')
            public_url = f"{base_url}/agendar/{appointment_token.token}/"
            print(f"📤 [TOOL] Reutilizando link: {public_url}")
        else:
            # Limpar tokens antigos expirados ou usados
            old_tokens = AppointmentToken.objects.filter(
                appointment__contact=contact,
                appointment__status='draft'
            ).filter(
                is_used=True
            ) | AppointmentToken.objects.filter(
                appointment__contact=contact,
                appointment__status='draft',
                expires_at__lte=timezone.now()
            )

            old_count = old_tokens.count()
            if old_count > 0:
                print(f"🗑️ [TOOL] Removendo {old_count} token(s) expirado(s) ou usado(s)")
                old_appointment_ids = old_tokens.values_list('appointment_id', flat=True)
                old_appointments = Appointment.objects.filter(id__in=old_appointment_ids)
                deleted_count = old_appointments.delete()[0]
                print(f"✅ [TOOL] {deleted_count} appointment(s) draft antigo(s) deletado(s)")

            # Cria novo appointment draft
            new_appointment = Appointment.objects.create(
                contact=contact,
                status='draft'
            )
            print(f"✅ [TOOL] Novo Appointment #{new_appointment.id} criado com status=draft")

            # Gera token único
            token = secrets.token_urlsafe(32)
            print(f"🔑 [TOOL] Token gerado: {token[:16]}...")

            # Define expiração para 48 horas
            expires_at = timezone.now() + timedelta(hours=48)

            # Cria o token de agendamento
            appointment_token = AppointmentToken.objects.create(
                appointment=new_appointment,
                token=token,
                expires_at=expires_at
            )
            print(f"✅ [TOOL] AppointmentToken #{appointment_token.id} criado")

            # Gera a URL pública
            base_url = settings.BACKEND_BASE_URL.rstrip('/')
            public_url = f"{base_url}/agendar/{appointment_token.token}/"
            print(f"📤 [TOOL] Link NOVO gerado: {public_url}")

        # VALIDAÇÃO FINAL
        appointment_token.refresh_from_db()

        if appointment_token.is_used:
            print(f"❌ [TOOL] ERRO CRÍTICO: Token #{appointment_token.id} foi marcado como usado!")
            return "❌ Consulta cancelada, mas erro ao gerar novo link. Por favor, solicite um link de agendamento."

        if appointment_token.expires_at <= timezone.now():
            print(f"❌ [TOOL] ERRO CRÍTICO: Token #{appointment_token.id} está expirado!")
            return "❌ Consulta cancelada, mas erro ao gerar novo link. Por favor, solicite um link de agendamento."

        if not appointment_token.appointment:
            print(f"❌ [TOOL] ERRO CRÍTICO: Token #{appointment_token.id} não tem appointment associado!")
            return "❌ Consulta cancelada, mas erro ao gerar novo link. Por favor, solicite um link de agendamento."

        print(f"✅ [TOOL] Validação final OK - Link válido e disponível")

        expires_formatted = appointment_token.expires_at.strftime('%d/%m/%Y às %H:%M')

        # 4. RETORNAR CONFIRMAÇÃO COMPLETA
        resultado = f"""✅ Reagendamento iniciado com sucesso!

📅 Consulta cancelada:
   Data: {data_formatada}
   Horário: {hora_formatada}"""

        if calendar_deleted:
            resultado += "\n   (Removida do Google Calendar)"

        resultado += f"""

🔗 Novo link de agendamento:
   {public_url}

⏰ Link válido até: {expires_formatted}

Por favor, clique no link para escolher a nova data e horário da sua consulta."""

        return resultado

    except Exception as e:
        print(f"❌ [TOOL] Erro ao reagendar consulta: {e}")
        traceback.print_exc()
        return f"❌ Erro ao reagendar consulta: {str(e)}"


@tool
def gerar_link_agendamento(runtime: ToolRuntime) -> str:
    """
    Gera um link de auto-agendamento para o paciente escolher dia e horário da consulta.

    ⚠️ CRÍTICO - LEIA COM ATENÇÃO:
    Esta é a ÚNICA forma de criar links de agendamento. NUNCA invente ou construa URLs manualmente.

    REGRAS ABSOLUTAS:
    1. SEMPRE use esta ferramenta para gerar links de agendamento
    2. NUNCA construa URLs como "http://..." ou "https://..." manualmente
    3. NUNCA reutilize links antigos de mensagens anteriores
    4. NUNCA invente tokens ou IDs de agendamento
    5. Se o paciente pedir um novo link, SEMPRE chame esta ferramenta novamente

    QUANDO USAR:
    - Paciente pede link para agendar
    - Paciente pede novo link (link anterior expirou ou foi perdido)
    - Precisa enviar opções de horários disponíveis

    O QUE A FERRAMENTA FAZ:
    - Verifica se já existe um link válido e reutiliza se possível
    - Se não, cria um novo appointment em status 'draft'
    - Gera token único e seguro
    - Invalida links antigos expirados ou usados
    - VALIDA o link antes de retornar para garantir que existe e não foi usado
    - Retorna URL válida por 48 horas

    IMPORTANTE:
    - Reutiliza links válidos existentes para evitar poluir o banco
    - Links antigos expirados ou usados são automaticamente invalidados
    - O link permite que o paciente escolha data/hora disponível
    - Sempre valida que o link existe e está ativo antes de retornar

    Returns:
        str: Link de agendamento válido e data de validade no formato:
             "Link: https://...
              Válido até: DD/MM/YYYY às HH:MM"
    """
    try:
        conversation = runtime.context["conversation"]
        if not conversation:
            return "❌ Erro: Conversa não encontrada no contexto."

        contact = conversation.contact
        if not contact:
            return "❌ Erro: Contato não encontrado."

        print(f"🔧 [TOOL CALL] gerar_link_agendamento (contact_id={contact.id})")

        from datetime import datetime, timedelta
        from django.utils import timezone
        from core.models import Appointment, AppointmentToken
        from django.conf import settings
        import secrets

        # Primeiro, verifica se já existe um token válido e não usado para este contato
        existing_token = AppointmentToken.objects.filter(
            appointment__contact=contact,
            appointment__status='draft',
            is_used=False,
            expires_at__gt=timezone.now()
        ).select_related('appointment').first()

        if existing_token:
            print(f"♻️ [TOOL] Link válido existente encontrado (Token #{existing_token.id})")
            print(f"📋 [TOOL] Appointment ID: {existing_token.appointment.id}")
            print(f"⏰ [TOOL] Expira em: {existing_token.expires_at}")

            # VALIDAÇÃO: Verifica se o token realmente existe e não foi usado
            if existing_token.is_used:
                print(f"⚠️ [TOOL] ATENÇÃO: Token #{existing_token.id} foi marcado como usado!")
                existing_token = None
            elif not existing_token.appointment:
                print(f"⚠️ [TOOL] ATENÇÃO: Token #{existing_token.id} não tem appointment associado!")
                existing_token = None

        if existing_token:
            # Reutiliza o token existente
            appointment_token = existing_token
            base_url = settings.BACKEND_BASE_URL.rstrip('/')
            public_url = f"{base_url}/agendar/{appointment_token.token}/"
            print(f"📤 [TOOL] Reutilizando link: {public_url}")
        else:
            # Invalida tokens antigos expirados ou usados deste contato
            old_tokens = AppointmentToken.objects.filter(
                appointment__contact=contact,
                appointment__status='draft'
            ).filter(
                is_used=True
            ) | AppointmentToken.objects.filter(
                appointment__contact=contact,
                appointment__status='draft',
                expires_at__lte=timezone.now()
            )

            old_count = old_tokens.count()
            if old_count > 0:
                print(f"🗑️ [TOOL] Removendo {old_count} token(s) expirado(s) ou usado(s)")
                # Deleta appointments draft antigos e seus tokens
                old_appointment_ids = old_tokens.values_list('appointment_id', flat=True)
                old_appointments = Appointment.objects.filter(id__in=old_appointment_ids)
                deleted_count = old_appointments.delete()[0]
                print(f"✅ [TOOL] {deleted_count} appointment(s) draft antigo(s) deletado(s)")

            # Cria um appointment em rascunho (sem data/hora definida)
            appointment = Appointment.objects.create(
                contact=contact,
                status='draft'
            )
            print(f"✅ [TOOL] Appointment #{appointment.id} criado com status=draft")

            # Gera token único
            token = secrets.token_urlsafe(32)
            print(f"🔑 [TOOL] Token gerado: {token[:16]}...")

            # Define expiração para 48 horas
            expires_at = timezone.now() + timedelta(hours=48)

            # Cria o token de agendamento
            appointment_token = AppointmentToken.objects.create(
                appointment=appointment,
                token=token,
                expires_at=expires_at
            )
            print(f"✅ [TOOL] AppointmentToken #{appointment_token.id} criado")

            # Gera a URL pública
            base_url = settings.BACKEND_BASE_URL.rstrip('/')
            public_url = f"{base_url}/agendar/{appointment_token.token}/"

            print(f"📤 [TOOL] Link NOVO gerado: {public_url}")
            print(f"⏰ [TOOL] Expira em: {expires_at}")
            print(f"📋 [TOOL] Appointment ID: {appointment.id}")
            print(f"🔑 [TOOL] Token ID: {appointment_token.id}")

        # VALIDAÇÃO FINAL: Verifica se o token existe e não foi usado antes de retornar
        appointment_token.refresh_from_db()

        if appointment_token.is_used:
            print(f"❌ [TOOL] ERRO CRÍTICO: Token #{appointment_token.id} foi marcado como usado!")
            return "❌ Erro: O link de agendamento foi marcado como usado. Tente gerar um novo link."

        if appointment_token.expires_at <= timezone.now():
            print(f"❌ [TOOL] ERRO CRÍTICO: Token #{appointment_token.id} está expirado!")
            return "❌ Erro: O link de agendamento expirou. Tente gerar um novo link."

        if not appointment_token.appointment:
            print(f"❌ [TOOL] ERRO CRÍTICO: Token #{appointment_token.id} não tem appointment associado!")
            return "❌ Erro: O link de agendamento está inválido. Tente gerar um novo link."

        print(f"✅ [TOOL] Validação final OK - Link válido e disponível")

        expires_formatted = appointment_token.expires_at.strftime('%d/%m/%Y às %H:%M')

        # Retorna apenas as informações essenciais para o agent formatar a mensagem
        return f"""Link: {public_url}
Válido até: {expires_formatted}"""

    except Exception as e:
        print(f"❌ [TOOL] Erro ao gerar link de agendamento: {e}")
        traceback.print_exc()
        return f"❌ Erro ao gerar link de agendamento: {str(e)}"


def get_secretary_tools():
    """
    Retorna a lista de ferramentas da secretária disponíveis para o agente.

    Returns:
        Lista de ferramentas LangChain da secretária.
    """
    return [
        consultar_agendamentos,
        cancelar_agendamento,
        reagendar_consulta,
        gerar_link_agendamento,
    ]