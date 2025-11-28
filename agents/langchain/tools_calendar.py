"""
Ferramentas do Google Calendar para o agente.

Define ferramentas que permitem ao agente interagir com o Google Calendar.
O contexto é passado via ToolRuntime para ser thread-safe.
"""
from datetime import datetime, timedelta
import traceback
from typing import TYPE_CHECKING
from django.core.mail import mail_admins
from langchain.tools import tool, ToolRuntime
from django.conf import settings

from core.models import Contact
from google_calendar.services import GoogleCalendarService

if TYPE_CHECKING:
    from agents.models import Conversation


@tool
def listar_eventos(runtime: ToolRuntime) -> str:
    """Lista os próximos eventos agendados no calendário do contato.

    Esta ferramenta retorna os próximos 10 eventos do calendário associado ao contato atual.

    Returns:
        str: Lista formatada de eventos ou mensagem de erro
    """
    try:
        conversation = runtime.context["conversation"]
        if not conversation:
            return "❌ Erro: Conversa não encontrada no contexto."

        contact = conversation.contact
        if not contact:
            return "❌ Erro: Contato não encontrado."

        calendar_service = GoogleCalendarService()
        success, events = calendar_service.list_events(contact.id, max_results=10)

        if not success:
            return f"❌ Erro ao acessar calendário: {events}"

        if not events:
            return "📅 Nenhum evento agendado."

        resultado = ["📅 Próximos Eventos:\n"]
        for i, event in enumerate(events, 1):
            start = event['start'].get('dateTime', event['start'].get('date'))
            title = event.get('summary', 'Sem título')

            if 'T' in start:
                dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                formatted = dt.strftime('%d/%m/%Y às %H:%M')
            else:
                dt = datetime.fromisoformat(start)
                formatted = dt.strftime('%d/%m/%Y')

            resultado.append(f"{i}. {title} - {formatted}")

        return "\n".join(resultado)
    except Exception as e:
        traceback.print_exc()
        return f"❌ Erro ao listar eventos: {str(e)}"


@tool
def verificar_disponibilidade(data: str, runtime: ToolRuntime) -> str:
    """
    Verifica disponibilidade de horários em uma data específica.

    Args:
        data: Data no formato DD/MM/YYYY

    Returns:
        str: Slots de 30 minutos disponíveis entre 09h-12h e 13h-17h
    """
    try:
        conversation = runtime.context["conversation"]
        if not conversation:
            return "❌ Erro: Conversa não encontrada no contexto."

        contact = conversation.contact
        if not contact:
            return "❌ Erro: Contato não encontrado."

        calendar_service = GoogleCalendarService()
        success, events = calendar_service.list_events(contact.id, max_results=50)

        if not success:
            return f"❌ Erro ao acessar calendário: {events}"

        # Parse da data
        data_obj = datetime.strptime(data, '%d/%m/%Y')

        # Gerar slots de 30 minutos
        blocos = [
            (datetime.combine(data_obj.date(), datetime.min.time().replace(hour=9)),
             datetime.combine(data_obj.date(), datetime.min.time().replace(hour=12))),
            (datetime.combine(data_obj.date(), datetime.min.time().replace(hour=13)),
             datetime.combine(data_obj.date(), datetime.min.time().replace(hour=17)))
        ]

        # Filtrar eventos do dia
        eventos_do_dia = []
        for event in events:
            start = event['start'].get('dateTime')
            if start and 'T' in start:
                dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                if dt.tzinfo:
                    dt = dt.astimezone().replace(tzinfo=None)
                if dt.date() == data_obj.date():
                    end = event['end'].get('dateTime')
                    end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                    if end_dt.tzinfo:
                        end_dt = end_dt.astimezone().replace(tzinfo=None)
                    eventos_do_dia.append((dt, end_dt))

        resultado = [f"✅ Horários disponíveis para {data}:\n"]

        for bloco_inicio, bloco_fim in blocos:
            atual = bloco_inicio
            while atual < bloco_fim:
                fim_slot = atual + timedelta(minutes=30)
                if fim_slot <= bloco_fim:
                    # Verificar se está ocupado
                    ocupado = any(ini <= atual < fim for ini, fim in eventos_do_dia)

                    if not ocupado:
                        resultado.append(f"• {atual.strftime('%H:%M')} - {fim_slot.strftime('%H:%M')}")

                atual = fim_slot

        return "\n".join(resultado) if len(resultado) > 1 else "❌ Nenhum horário disponível"
    except Exception as e:
        traceback.print_exc()
        return f"❌ Erro ao verificar disponibilidade: {str(e)}"


@tool
def buscar_proximas_datas(dia_semana: str) -> str:
    """
    Busca as próximas 5 datas de um dia da semana específico.

    Args:
        dia_semana: Nome do dia da semana ('terça', 'quinta', 'tue', 'thu')

    Returns:
        str: Lista das próximas 5 datas do dia especificado
    """
    try:
        mapa_dias = {
            'terça': 1, 'terca': 1, 'tue': 1,
            'quinta': 3, 'thu': 3
        }

        dia_semana_lower = dia_semana.lower().strip()
        if dia_semana_lower not in mapa_dias:
            return "❌ Use 'terça' ou 'quinta'"

        target_weekday = mapa_dias[dia_semana_lower]
        hoje = datetime.now().date()

        # Encontrar próximas 5 ocorrências
        datas = []
        data_atual = hoje + timedelta(days=1)  # Começar de amanhã

        while len(datas) < 5:
            if data_atual.weekday() == target_weekday:
                datas.append(data_atual.strftime('%d/%m/%Y'))
            data_atual += timedelta(days=1)

        resultado = [f"📅 Próximas {dia_semana}s:\n"]
        for i, data in enumerate(datas, 1):
            resultado.append(f"{i}. {data}")

        return "\n".join(resultado)
    except Exception as e:
        traceback.print_exc()
        return f"❌ Erro ao buscar datas: {str(e)}"


@tool
def criar_evento(titulo: str, data: str, hora: str, runtime: ToolRuntime, tipo: str = "consulta") -> str:
    """
    Cria um evento no Google Calendar.

    Args:
        titulo: Título do evento (ex: nome do paciente)
        data: Data no formato DD/MM/YYYY
        hora: Horário no formato HH:MM
        tipo: Tipo de consulta (convênio ou particular)

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
        print(f"🔧 [TOOL CALL] criar_evento (contact_id={contact.id})")
        print(f"   📝 Titulo: {titulo}")
        print(f"   📅 Data: {data}")
        print(f"   ⏰ Hora: {hora}")
        print(f"   🏥 Tipo: {tipo}")
        print("="*80)

        calendar_service = GoogleCalendarService()

        # Parse data e hora
        data_obj = datetime.strptime(data, '%d/%m/%Y')
        hora_obj = datetime.strptime(hora, '%H:%M').time()
        start_datetime = datetime.combine(data_obj.date(), hora_obj)
        end_datetime = start_datetime + timedelta(minutes=29)

        # Montar título padronizado
        tipo_upper = tipo.upper() if tipo else "CONSULTA"
        titulo_formatado = f"[{tipo_upper}] +55{contact.phone_number} — {titulo}"

        event_data = {
            'summary': titulo_formatado,
            'description': f'Agendamento via WhatsApp\nPaciente: {titulo}\nTipo: {tipo}',
            'start': {
                'dateTime': start_datetime.isoformat(),
                'timeZone': 'America/Sao_Paulo',
            },
            'end': {
                'dateTime': end_datetime.isoformat(),
                'timeZone': 'America/Sao_Paulo',
            }
        }

        print(f"📡 [TOOL] Enviando evento para Google Calendar...")
        success, result = calendar_service.create_event(contact.id, event_data)

        print(f"📥 [TOOL] Resposta do Google Calendar: success={success}")
        if success:
            print(f"✅ [TOOL] Evento criado com sucesso no Calendar")
            # Criar registro Appointment no banco de dados
            try:
                from core.models import Appointment
                from django.utils import timezone
                import pytz

                print(f"💾 [TOOL] Criando registro Appointment no banco...")
                print(f"👤 [TOOL] Contact encontrado/criado: {contact.phone_number}")

                # Extrair o event_id do resultado
                event_id = result.get('id') if isinstance(result, dict) else None
                print(f"🔑 [TOOL] Event ID do Google Calendar: {event_id}")

                # Criar Appointment com timezone correto
                # Criar datetime timezone-aware diretamente no timezone de São Paulo
                sao_paulo_tz = pytz.timezone('America/Sao_Paulo')
                scheduled_datetime = sao_paulo_tz.localize(start_datetime)

                appointment = Appointment.objects.create(
                    contact=contact,
                    date=data_obj.date(),
                    time=hora_obj,
                    scheduled_for=scheduled_datetime,
                    calendar_event_id=event_id  # Salvar o ID do evento do Google Calendar
                )
                print(f"✅ [TOOL] Appointment #{appointment.id} criado com sucesso no banco")
                print(f"   📅 Data: {appointment.date}")
                print(f"   ⏰ Hora: {appointment.time}")
                print(f"   🔑 Calendar Event ID: {appointment.calendar_event_id}")

            except Exception as db_error:
                traceback.print_exc()
                print(f"⚠️ [TOOL] Evento criado no Calendar, mas erro ao salvar no banco: {db_error}")
                # Não falha a operação se o Calendar foi criado com sucesso
                if not settings.DEBUG:
                    subject = "[TOOL] Evento criado no Calendar, mas erro ao salvar no banco"
                    message = u'%s\n%s' % (traceback.format_exc(), locals())
                    mail_admins(subject, message)

            return f"""✅ Agendamento criado com sucesso!
📅 Data: {data}
⏰ Horário: {hora}
👤 Paciente: {titulo}
📋 Tipo: {tipo}"""
        else:
            print(f"❌ [TOOL] Falha ao criar evento no Calendar: {result}")
            return f"❌ Erro ao criar evento: {result}"
    except Exception as e:
        print(f"❌ [TOOL] Exceção ao criar evento: {e}")
        traceback.print_exc()
        if not settings.DEBUG:
            subject = "[TOOL] Exceção ao criar evento"
            message = u'%s\n%s' % (traceback.format_exc(), locals())
            mail_admins(subject, message)
        return f"❌ Erro ao criar evento: {str(e)}"


def get_calendar_tools():
    """
    Retorna a lista de ferramentas do calendário disponíveis para o agente.

    Returns:
        Lista de ferramentas LangChain do Google Calendar.
    """
    return [
        listar_eventos,
        verificar_disponibilidade,
        buscar_proximas_datas,
        criar_evento,
    ]