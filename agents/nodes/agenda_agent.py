# dialog_test/nodes/agenda_agent.py
"""
Agente de Agenda - Gerenciamento de Agendamentos

Responsável por:
- Listar eventos do calendário
- Verificar disponibilidade de horários
- Criar novos agendamentos
- Buscar próximas datas disponíveis
"""

from typing import TYPE_CHECKING
from datetime import datetime, timedelta
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langgraph.graph import END

from google_calendar.services import GoogleCalendarService

if TYPE_CHECKING:
    from core.models import Contact
    from dialog_test.conversation_graph import State

# Configuração do LLM
agenda_llm = ChatOpenAI(model="gpt-4o", temperature=0.3)

# Carregar prompt base
PROMPT_AGENDA_BASE = (Path(__file__).parent.parent / "prompts" / "agenda.md").read_text()


def get_prompt_agenda(contact: "Contact") -> str:
    """Retorna o prompt de agenda com a data atual e informações do contato injetadas."""
    hoje = datetime.now()
    data_formatada = hoje.strftime("%d/%m/%Y")
    dia_semana = hoje.strftime("%A")

    # Traduzir dia da semana para português
    dias_pt = {
        "Monday": "segunda-feira",
        "Tuesday": "terça-feira",
        "Wednesday": "quarta-feira",
        "Thursday": "quinta-feira",
        "Friday": "sexta-feira",
        "Saturday": "sábado",
        "Sunday": "domingo"
    }
    dia_semana_pt = dias_pt.get(dia_semana, dia_semana)

    # Contexto temporal
    contexto_data = f"\n\n---\n\n## 📅 Contexto Temporal\n\n**Data de hoje:** {data_formatada} ({dia_semana_pt})\n\nUse esta data como referência para calcular \"amanhã\", \"próximas quintas\", etc.\n"

    # Contexto do contato
    contexto_contato = "\n\n## 👤 Informações do Contato\n\n"
    contexto_contato += f"**Telefone:** {contact.phone_number}\n"

    if contact.name:
        contexto_contato += f"**Nome:** {contact.name}\n"

    return PROMPT_AGENDA_BASE + contexto_data + contexto_contato


def create_agenda_tools(contact: "Contact", client=None):
    """Cria as ferramentas de agenda com o número WhatsApp do usuário e client"""

    @tool
    def listar_eventos() -> str:
        """Lista os próximos eventos agendados no calendário"""
        try:
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
            return f"❌ Erro: {str(e)}"

    @tool
    def verificar_disponibilidade(data: str) -> str:
        """
        Verifica disponibilidade de horários em uma data específica.
        Formato: DD/MM/YYYY
        Retorna slots de 30 minutos entre 09h-12h e 13h-17h
        """
        try:
            calendar_service = GoogleCalendarService()
            success, events = calendar_service.list_events(contact.id, max_results=50)

            if not success:
                return f"❌ Erro: {events}"

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
            return f"❌ Erro: {str(e)}"

    @tool
    def buscar_proximas_datas(dia_semana: str) -> str:
        """
        Busca as próximas 5 datas de um dia da semana específico.
        Parâmetros:
        - dia_semana: 'terça' ou 'quinta' (ou 'tue', 'thu' em inglês)
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
            return f"❌ Erro: {str(e)}"

    @tool
    def criar_evento(titulo: str, data: str, hora: str, tipo: str = "consulta") -> str:
        """
        Cria um evento no Google Calendar.
        Parâmetros:
        - titulo: Título do evento (ex: nome do paciente)
        - data: Data no formato DD/MM/YYYY
        - hora: Horário no formato HH:MM
        - tipo: Tipo de consulta (convênio ou particular)
        """
        print(f"🔧 [TOOL CALL] criar_evento - Titulo: {titulo}, Data: {data}, Hora: {hora}, Tipo: {tipo}")
        try:
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

            success, result = calendar_service.create_event(contact.id, event_data)

            if success:
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
                    print(f"✅ [TOOL] Appointment #{appointment.id} criado com sucesso")
                    print(f"   Calendar Event ID salvo: {appointment.calendar_event_id}")

                except Exception as db_error:
                    print(f"⚠️ [TOOL] Evento criado no Calendar, mas erro ao salvar no banco: {db_error}")
                    # Não falha a operação se o Calendar foi criado com sucesso

                return f"""✅ Agendamento criado com sucesso!
📅 Data: {data}
⏰ Horário: {hora}
👤 Paciente: {titulo}
📋 Tipo: {tipo}"""
            else:
                return f"❌ Erro ao criar evento: {result}"
        except Exception as e:
            return f"❌ Erro: {str(e)}"

    return [listar_eventos, verificar_disponibilidade, buscar_proximas_datas, criar_evento]


def create_agenda_node(contact: "Contact", client=None):
    """Cria o nó de agenda com o contact injetado - cria suas próprias tools internamente"""

    # Criar tools internamente
    agenda_tools = create_agenda_tools(contact, client)

    # Criar agente de agenda com as ferramentas
    agenda_agent = create_react_agent(agenda_llm, agenda_tools)

    def agenda_node(state: "State") -> dict:
        """Processa requisições de agenda usando agente com ferramentas do Google Calendar"""
        print("🗓️ [AGENDA NODE] Iniciando processamento...")

        # Gerar prompt com data atual e informações do contato
        prompt_atual = get_prompt_agenda(contact)
        messages = [SystemMessage(content=prompt_atual)] + list(state["history"])

        print(f"📝 [AGENDA NODE] Última mensagem recebida: {state['history'][-1].content if state['history'] else 'Nenhuma'}")

        # Executar agente com ferramentas
        result = agenda_agent.invoke({"messages": messages})
        print(f"✅ [AGENDA NODE] Resultado do agente recebido")

        # Debug: mostrar todas as mensagens do resultado
        print(f"🔍 [AGENDA NODE] Total de mensagens no resultado: {len(result['messages'])}")
        for i, msg in enumerate(result["messages"]):
            msg_type = type(msg).__name__
            content_preview = str(msg.content)[:100] if hasattr(msg, 'content') else str(msg)[:100]
            print(f"   {i+1}. {msg_type}: {content_preview}")

        # Extrair mensagens AI do resultado
        ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
        print(f"💬 [AGENDA NODE] Total de mensagens AI: {len(ai_messages)}")

        if ai_messages:
            last_response = ai_messages[-1].content

            # Verificar se houve criação de evento (agendamento confirmado)
            confirmed = "✅ Agendamento criado" in last_response

            if confirmed:
                print("✅ [AGENDA NODE] Agendamento CONFIRMADO na resposta")
            else:
                print("⏳ [AGENDA NODE] Resposta de consulta/verificação (não é confirmação de agendamento)")

            # Se criou agendamento, finaliza. Caso contrário, volta para recepção apresentar dados
            next_agent = END if confirmed else "recepcao"

            # Adicionar prefixo para que a recepção saiba que é resposta da agenda
            formatted_response = f"[AGENDA_RESPONSE] {last_response}"

            return {
                "history": [AIMessage(content=formatted_response)],
                "agent": next_agent,
                "confirmed": confirmed
            }
        else:
            return {
                "history": [AIMessage(content="[AGENDA_RESPONSE] Erro ao processar solicitação de agenda")],
                "agent": "recepcao"
            }

    return agenda_node
