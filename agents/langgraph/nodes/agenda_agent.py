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

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langgraph.graph import END

from google_calendar.services import GoogleCalendarService

if TYPE_CHECKING:
    from core.models import Contact

# Configuração do LLM
# Temperature reduzida de 0.3 para 0.05 para máxima consistência nas operações de agenda
agenda_llm = ChatOpenAI(model="gpt-4o", temperature=0.05)

# Carregar prompt base
PROMPT_AGENDA_BASE = (Path(__file__).parent.parent / "prompts" / "agenda.md").read_text()


def get_prompt_agenda() -> str:
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

    contexto_data = f"\n\n---\n\n## 📅 Contexto Temporal\n\n**Data de hoje:** {data_formatada} ({dia_semana_pt})\n\nUse esta data como referência para calcular \"amanhã\", \"próximas quintas\", etc.\n"

    return PROMPT_AGENDA_BASE + contexto_data


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
        print("\n" + "="*80)
        print(f"🔧 [TOOL CALL] criar_evento")
        print(f"   📝 Titulo: {titulo}")
        print(f"   📅 Data: {data}")
        print(f"   ⏰ Hora: {hora}")
        print(f"   🏥 Tipo: {tipo}")
        print(f"   📞 Contact: {contact.phone_number}")
        print("="*80)
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
                    print(f"⚠️ [TOOL] Evento criado no Calendar, mas erro ao salvar no banco: {db_error}")
                    # Não falha a operação se o Calendar foi criado com sucesso

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
            import traceback
            traceback.print_exc()
            return f"❌ Erro: {str(e)}"

    return [listar_eventos, verificar_disponibilidade, buscar_proximas_datas, criar_evento]


def create_agenda_node():
    """Cria o nó de agenda — cada execução lê o contact e o client do state."""

    def agenda_node(state: "State") -> dict:
        """Processa requisições de agenda usando ferramentas do Google Calendar."""
        print("🗓️ [AGENDA NODE] Iniciando processamento...")

        # ⚙️ Pega o contato e o cliente diretamente do state
        contact = state.contact
        client = state.client

        # Criar tools dinamicamente com o contato atual
        agenda_tools = create_agenda_tools(contact, client)

        # Criar agente React com ferramentas de agenda
        agenda_agent = create_agent(agenda_llm, agenda_tools)

        # Gerar prompt de contexto com data atual e informações do contato
        prompt_atual = get_prompt_agenda()
        messages = [SystemMessage(content=prompt_atual)] + list(state.history)

        print(f"📨 [AGENDA NODE] Mensagens enviadas ao agente: {len(messages)}")
        if messages:
            last_msg = messages[-1].content if hasattr(messages[-1], "content") else "Sem conteúdo"
            print(f"🗣️ [AGENDA NODE] Última mensagem: {last_msg[:150]}...")

        # Executar agente com ferramentas
        result = agenda_agent.invoke({"messages": messages})
        print("✅ [AGENDA NODE] Agente retornou resultado.")

        # Extrair mensagens AI do resultado
        ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]

        if not ai_messages:
            print("⚠️ [AGENDA NODE] Nenhuma mensagem AI retornada. Voltando à recepção com erro.")
            return {
                "history": [AIMessage(content="[AGENDA_RESPONSE] Erro ao processar solicitação de agenda.")],
                "agent": "recepcao",
                "confirmed": False,
            }

        # Pega a última resposta da IA
        last_response = ai_messages[-1].content.strip()
        print(f"💬 [AGENDA NODE] Resposta da Aline Agenda: {last_response[:200]}...")

        # Verificar se houve criação de evento (agendamento confirmado)
        confirmed = "✅ Agendamento criado" in last_response or "✅ Consulta agendada" in last_response

        if confirmed:
            print("🎉 [AGENDA NODE] Agendamento confirmado na resposta.")
        else:
            print("📅 [AGENDA NODE] Resposta de consulta/verificação (não é confirmação de agendamento).")

        # Define o próximo agente
        next_agent = END if confirmed else "recepcao"

        # Adiciona prefixo para que a recepção reconheça a origem
        formatted_response = f"[AGENDA_RESPONSE] {last_response}"

        print(f"🔚 [AGENDA NODE] Finalizando com agent={next_agent}")
        return {
            "history": [AIMessage(content=formatted_response)],
            "agent": next_agent,
            "confirmed": confirmed,
        }

    return agenda_node
