# dialog_test/nodes/recepcao_agent.py
"""
Agente de Recepção - Atendimento Inicial e Coleta de Dados

Responsável por:
- Receber o contato inicial
- Coletar informações do paciente (nome, email)
- Rotear para o agente de agenda quando necessário
"""

from typing import TYPE_CHECKING
from datetime import datetime
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langgraph.graph import END

from agents.langgraph.nodes.utils import debug_langgraph_messages, validate_agenda_request, validate_agenda_response

if TYPE_CHECKING:
    from core.models import Contact

# Configuração do LLM
# Temperature reduzida de 0.6 para 0.1 para maior consistência nas respostas
recepcao_llm = ChatOpenAI(model="gpt-4o", temperature=0.1)

# Carregar prompt base
PROMPT_RECEPCAO_BASE = (Path(__file__).parent.parent / "prompts" / "recepcao.md").read_text()


def get_prompt_recepcao() -> str:
    """Retorna o prompt de recepção com a data atual e informações do contato injetadas."""
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
    contexto_data = f"\n\n---\n\n## 📅 Contexto Temporal\n\n**Data de hoje:** {data_formatada} ({dia_semana_pt})\n"

    return PROMPT_RECEPCAO_BASE + contexto_data


def create_recepcao_tools(contact: "Contact"):
    """Cria as ferramentas de recepção para atualizar informações do contato"""

    @tool
    def atualizar_nome_contato(nome: str) -> str:
        """
        Atualiza o nome do contato no sistema.
        Parâmetros:
        - nome: Nome completo do contato
        """
        print(f"🔧 [TOOL CALL] atualizar_nome_contato - Nome: {nome}")
        try:
            if not nome or len(nome.strip()) < 2:
                return "❌ Nome inválido. Por favor, forneça um nome válido."

            contact.name = nome.strip()
            contact.save(update_fields=['name', 'updated_at'])

            print(f"✅ [TOOL] Nome atualizado: {contact.name}")
            return f"✅ Nome atualizado com sucesso para: {contact.name}"
        except Exception as e:
            print(f"❌ [TOOL] Erro ao atualizar nome: {e}")
            return f"❌ Erro ao atualizar nome: {str(e)}"

    @tool
    def consultar_agendamentos_contato() -> str:
        """
        Consulta as consultas/agendamentos marcados para este contato.
        Retorna lista de consultas futuras e passadas.
        """
        print(f"🔧 [TOOL CALL] consultar_agendamentos_contato")
        try:
            from datetime import datetime, date
            from core.models import Appointment

            # Buscar todos os agendamentos do contato ordenados por data
            appointments = contact.appointments.all().order_by('date', 'time')

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
    def cancelar_agendamento_contato(data: str, hora: str) -> str:
        """
        Cancela uma consulta/agendamento marcado do contato.
        Remove do Google Calendar e do sistema.

        Parâmetros:
        - data: Data do agendamento no formato DD/MM/YYYY
        - hora: Horário do agendamento no formato HH:MM
        """
        print("\n" + "="*80)
        print(f"🔧 [TOOL CALL] cancelar_agendamento_contato")
        print(f"   📅 Data: {data}")
        print(f"   ⏰ Hora: {hora}")
        print(f"   📞 Contact: {contact.phone_number}")
        print("="*80)
        try:
            from datetime import datetime
            from core.models import Appointment
            from google_calendar.services import GoogleCalendarService

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

    return [
        atualizar_nome_contato,
        consultar_agendamentos_contato,
        cancelar_agendamento_contato
    ]


def create_recepcao_node():
    """Cria o nó de recepção — cada execução lê o contact e o client do state."""

    def recepcao_node(state: "State") -> dict:
        print("👋 [RECEPÇÃO NODE] Iniciando processamento...")

        # ⚙️ Pega o contato e o cliente do state
        contact = state.contact
        client = state.client

        # Criar tools dinamicamente com o contato atual
        recepcao_tools = create_recepcao_tools(contact)

        # Criar agente React com as tools
        recepcao_agent = create_react_agent(recepcao_llm, recepcao_tools)

        # Gerar prompt com data atual e informações do contact
        prompt_atual = get_prompt_recepcao()
        messages = [SystemMessage(content=prompt_atual)] + list(state.history)

        print(f"📝 [RECEPÇÃO NODE] Última mensagem do histórico: "
              f"{state.history[-1].content if state.history else 'Nenhuma'}")

        # Executar agente com tools
        result = recepcao_agent.invoke({"messages": messages})

        # Debug: Mostrar TODAS as mensagens do resultado (incluindo ToolMessages)
        debug_langgraph_messages(result["messages"], node_name="RECEPÇÃO NODE")

        # Verificar se alguma ToolMessage contém [AGENDA_REQUEST]
        from langchain_core.messages import ToolMessage
        for msg in result["messages"]:
            if isinstance(msg, ToolMessage) and "[AGENDA_REQUEST]" in msg.content:
                print("🎯 [RECEPÇÃO NODE] [AGENDA_REQUEST] detectado em ToolMessage — roteando para agenda")
                is_valid, agenda_request = validate_agenda_request(msg.content)
                if is_valid:
                    return {
                        "history": [HumanMessage(content=agenda_request)],
                        "agent": "agenda"
                    }

        # Extrair mensagens AI do resultado
        ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
        msg = ai_messages[-1].content.strip() if ai_messages else "Erro ao processar mensagem"

        print(f"💬 [RECEPÇÃO NODE] Resposta da Aline Atendimento: {msg[:200]}...")

        # Detectar se deve rotear para a agenda usando validação robusta (em AIMessage)
        is_valid_request, agenda_request = validate_agenda_request(msg)
        if is_valid_request:
            print("🎯 [RECEPÇÃO NODE] [AGENDA_REQUEST] válido detectado em AIMessage — roteando para agenda")
            next_agent = "agenda"
            return {
                "history": [HumanMessage(content=agenda_request)],
                "agent": next_agent
            }

        print("⚠️ [RECEPÇÃO NODE] Nenhum [AGENDA_REQUEST] válido detectado — resposta direta ao usuário")

        # Formatar resposta se vier de agenda usando validação robusta
        is_valid_response, clean_msg = validate_agenda_response(msg)
        if is_valid_response:
            print("✅ [RECEPÇÃO NODE] [AGENDA_RESPONSE] válido detectado — formatando para usuário")
            msg = clean_msg

        return {
            "history": [AIMessage(content=msg)],
            "agent": END
        }

    return recepcao_node
