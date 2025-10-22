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

if TYPE_CHECKING:
    from core.models import Contact

# Configuração do LLM
recepcao_llm = ChatOpenAI(model="gpt-4o", temperature=0.6)

# Carregar prompt base
PROMPT_RECEPCAO_BASE = (Path(__file__).parent.parent / "prompts" / "recepcao.md").read_text()


def get_prompt_recepcao(contact: "Contact") -> str:
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

    # Contexto do contato
    contexto_contato = "\n\n## 👤 Informações do Contato\n\n"
    contexto_contato += f"**Telefone:** {contact.phone_number}\n"

    if contact.name:
        contexto_contato += f"**Nome:** {contact.name}\n"

    if contact.email:
        contexto_contato += f"**Email:** {contact.email}\n"

    # Agendamentos anteriores
    appointments_count = contact.appointments.count()
    if appointments_count > 0:
        contexto_contato += f"**Agendamentos anteriores:** {appointments_count}\n"
        last_appointment = contact.appointments.order_by('-scheduled_for').first()
        if last_appointment:
            contexto_contato += f"**Último agendamento:** {last_appointment.scheduled_for.strftime('%d/%m/%Y às %H:%M')}\n"

    return PROMPT_RECEPCAO_BASE + contexto_data + contexto_contato


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
    def atualizar_email_contato(email: str) -> str:
        """
        Atualiza o email do contato no sistema.
        Parâmetros:
        - email: Endereço de email válido
        """
        print(f"🔧 [TOOL CALL] atualizar_email_contato - Email: {email}")
        try:
            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError

            # Validar formato do email
            try:
                validate_email(email)
            except ValidationError:
                return "❌ Email inválido. Por favor, forneça um email válido."

            contact.email = email.strip().lower()
            contact.save(update_fields=['email', 'updated_at'])

            print(f"✅ [TOOL] Email atualizado: {contact.email}")
            return f"✅ Email atualizado com sucesso para: {contact.email}"
        except Exception as e:
            print(f"❌ [TOOL] Erro ao atualizar email: {e}")
            return f"❌ Erro ao atualizar email: {str(e)}"

    @tool
    def obter_informacoes_contato() -> str:
        """
        Obtém as informações atuais do contato cadastradas no sistema.
        """
        print(f"🔧 [TOOL CALL] obter_informacoes_contato")
        try:
            info = []
            info.append("📋 Informações do Contato:\n")
            info.append(f"📱 Telefone: {contact.phone_number}")

            if contact.name:
                info.append(f"👤 Nome: {contact.name}")
            else:
                info.append("👤 Nome: Não cadastrado")

            if contact.email:
                info.append(f"📧 Email: {contact.email}")
            else:
                info.append("📧 Email: Não cadastrado")

            if contact.profile_name:
                info.append(f"💬 Nome no WhatsApp: {contact.profile_name}")

            appointments_count = contact.appointments.count()
            if appointments_count > 0:
                info.append(f"📅 Agendamentos: {appointments_count}")

            return "\n".join(info)
        except Exception as e:
            print(f"❌ [TOOL] Erro ao obter informações: {e}")
            return f"❌ Erro ao obter informações: {str(e)}"

    @tool
    def consultar_agendamentos_contato() -> str:
        """
        Consulta as consultas/agendamentos marcados para este contato.
        Retorna lista de consultas futuras e passadas.
        """
        print(f"🔧 [TOOL CALL] consultar_agendamentos_contato")
        try:
            from datetime import datetime, date, time as dt_time
            from core.models import Appointment

            # Buscar todos os agendamentos do contato ordenados por data
            appointments = contact.appointments.all().order_by('date', 'time')

            if not appointments.exists():
                return "📅 Você não possui consultas marcadas no momento."

            # Separar agendamentos futuros e passados usando date e time
            hoje = date.today()
            agora = datetime.now().time()

            future_appointments = []
            past_appointments = []

            for apt in appointments:
                # Verifica se é futuro ou passado comparando date e time
                if apt.date > hoje or (apt.date == hoje and apt.time >= agora):
                    future_appointments.append(apt)
                else:
                    past_appointments.append(apt)

            # Montar resposta
            resultado = []

            # Agendamentos futuros (mais importantes)
            if future_appointments:
                resultado.append("📅 Consultas Agendadas (Próximas):\n")
                for i, apt in enumerate(future_appointments, 1):
                    # Usar diretamente os campos date e time (já estão no timezone correto)
                    data_formatada = f"{apt.date.strftime('%d/%m/%Y')} às {apt.time.strftime('%H:%M')}"
                    dia_semana = apt.date.strftime('%A')

                    # Traduzir dia da semana
                    dias_pt = {
                        'Monday': 'segunda-feira',
                        'Tuesday': 'terça-feira',
                        'Wednesday': 'quarta-feira',
                        'Thursday': 'quinta-feira',
                        'Friday': 'sexta-feira',
                        'Saturday': 'sábado',
                        'Sunday': 'domingo'
                    }
                    dia_semana_pt = dias_pt.get(dia_semana, dia_semana)

                    resultado.append(f"{i}. {data_formatada} ({dia_semana_pt})")

            # Agendamentos passados (histórico)
            if past_appointments:
                if future_appointments:
                    resultado.append("")  # Linha em branco
                resultado.append("📋 Consultas Anteriores (Histórico):\n")
                # Mostrar apenas as últimas 3 consultas passadas
                for i, apt in enumerate(list(reversed(past_appointments))[:3], 1):
                    # Usar diretamente os campos date e time
                    data_formatada = f"{apt.date.strftime('%d/%m/%Y')} às {apt.time.strftime('%H:%M')}"
                    resultado.append(f"{i}. {data_formatada}")

            if not resultado:
                return "📅 Você não possui consultas marcadas no momento."

            return "\n".join(resultado)

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
        print(f"🔧 [TOOL CALL] cancelar_agendamento_contato - Data: {data}, Hora: {hora}")
        try:
            from datetime import datetime
            from core.models import Appointment
            from google_calendar.services import GoogleCalendarService

            # Parse data e hora
            try:
                data_obj = datetime.strptime(data, '%d/%m/%Y').date()
                hora_obj = datetime.strptime(hora, '%H:%M').time()
            except ValueError:
                return "❌ Formato de data ou hora inválido. Use DD/MM/YYYY para data e HH:MM para hora."

            # Buscar o agendamento
            try:
                appointment = contact.appointments.get(date=data_obj, time=hora_obj)
            except Appointment.DoesNotExist:
                return f"❌ Não encontrei nenhuma consulta marcada para {data} às {hora}."
            except Appointment.MultipleObjectsReturned:
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
        atualizar_email_contato,
        obter_informacoes_contato,
        consultar_agendamentos_contato,
        cancelar_agendamento_contato
    ]


def create_recepcao_node(contact: "Contact"):
    """Cria o nó de recepção com o contact injetado - cria suas próprias tools internamente"""

    # Criar tools internamente
    recepcao_tools = create_recepcao_tools(contact)

    # Criar agente React com as tools
    recepcao_agent = create_react_agent(recepcao_llm, recepcao_tools)

    def recepcao_node(state: "State") -> dict:
        print("👋 [RECEPCAO NODE] Iniciando processamento...")

        # Gerar prompt com data atual e informações do contact
        prompt_atual = get_prompt_recepcao(contact)
        messages = [SystemMessage(content=prompt_atual)] + list(state["history"])

        print(f"📝 [RECEPCAO NODE] Última mensagem do histórico: {state['history'][-1].content if state['history'] else 'Nenhuma'}")

        # Executar agente com tools
        result = recepcao_agent.invoke({"messages": messages})

        # Extrair mensagens AI do resultado
        ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
        if ai_messages:
            msg = ai_messages[-1].content.strip()
        else:
            msg = "Erro ao processar mensagem"

        print(f"💬 [RECEPCAO NODE] Resposta da Aline Atendimento: {msg[:200]}...")

        # Detectar se deve rotear para a agenda
        if "[AGENDA_REQUEST]" in msg:
            print("🎯 [RECEPCAO NODE] Detectado [AGENDA_REQUEST] - roteando para agenda")
            # Extrair a requisição para a agenda
            agenda_request = msg.split("[AGENDA_REQUEST]")[1].strip()
            next_agent = "agenda"

            # Adicionar mensagem de requisição para a agenda (não para o usuário)
            return {
                "history": [HumanMessage(content=agenda_request)],
                "agent": next_agent
            }
        else:
            print("⚠️ [RECEPCAO NODE] NÃO detectado [AGENDA_REQUEST] - resposta direta ao usuário")

            # Remover o prefixo [AGENDA_RESPONSE] se existir (para não mostrar ao usuário)
            if "[AGENDA_RESPONSE]" in msg:
                print("✅ [RECEPCAO NODE] Detectado [AGENDA_RESPONSE] - formatando resposta para usuário")
                msg = msg.replace("[AGENDA_RESPONSE]", "").strip()

            # Resposta normal para o usuário
            next_agent = END
            return {
                "history": [AIMessage(content=msg)],
                "agent": next_agent
            }

    return recepcao_node
