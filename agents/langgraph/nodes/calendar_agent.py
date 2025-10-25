# dialog_test/nodes/calendar_agent.py
"""
Agente de Agenda - Gerenciamento de Agendamentos

Responsável por:
- Listar eventos do calendário
- Verificar disponibilidade de horários
- Criar novos agendamentos
- Buscar próximas datas disponíveis
"""

from datetime import datetime
from pathlib import Path
from uuid import UUID

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage
from langgraph.graph import END

# Importar a função factory de ferramentas
from agents.langgraph.tools.calendar_tools import create_calendar_tools

# Carregar prompt base
PROMPT_AGENDA_BASE = (Path(__file__).parent.parent / "prompts" / "agenda.md").read_text()


def build_calendar_agent(contact_id: UUID):
    """
    Cria o agente 'Aline Agenda', especializado em gerenciar agendamentos.
    Este agente é um ReAct Agent e pode raciocinar antes de usar as ferramentas.

    Args:
        contact_id: ID do contato para injetar nas ferramentas via closure
    """
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0.05)

    # Gerar prompt com data atual
    hoje = datetime.now()
    data_formatada = hoje.strftime("%d/%m/%Y")
    dia_semana = hoje.strftime("%A")
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
    system_prompt = PROMPT_AGENDA_BASE + contexto_data

    # Criar ferramentas com contact_id injetado via closure
    tools = create_calendar_tools(contact_id)

    # Criar agente ReAct moderno (LangChain 1.x)
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt
    )

    return agent


def create_agenda_node():
    """Cria o nó de agenda com todas as ferramentas e lógica de processamento."""

    def agenda_node(state) -> dict:
        """Processa requisições de agenda usando ferramentas do Google Calendar."""
        print("🗓️ [AGENDA NODE] Iniciando processamento...")

        # Criar agente com contact_id injetado nas ferramentas
        agenda_agent = build_calendar_agent(contact_id=state.contact.id)

        # Preparar mensagens com histórico completo
        messages = list(state.history)

        print(f"📚 [AGENDA NODE] Histórico: {len(messages)} mensagens")
        if messages:
            last_msg = messages[-1].content if hasattr(messages[-1], "content") else "Sem conteúdo"
            print(f"🗣️ [AGENDA NODE] Última mensagem: {last_msg[:150]}...")

        # Executar agente COM histórico
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

        # Adiciona prefixo APENAS quando rotear de volta para recepção
        # Quando vai para END, a mensagem vai direto ao usuário e não deve ter prefixo
        if next_agent == "recepcao":
            formatted_response = f"[AGENDA_RESPONSE] {last_response}"
        else:
            formatted_response = last_response

        print(f"🔚 [AGENDA NODE] Finalizando com agent={next_agent}")
        return {
            "history": [AIMessage(content=formatted_response)],
            "agent": next_agent,
            "confirmed": confirmed,
        }

    return agenda_node
