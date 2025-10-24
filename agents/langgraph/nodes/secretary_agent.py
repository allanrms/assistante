# dialog_test/nodes/secretary_agent.py
"""
Agente de Recepção - Atendimento Inicial e Coleta de Dados

Responsável por:
- Receber o contato inicial
- Coletar informações do paciente (nome, email)
- Rotear para o agente de agenda quando necessário
"""
from datetime import datetime
from pathlib import Path
from uuid import UUID

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import END

from agents.langgraph.state import State
from agents.langgraph.tools.secretary_tools import create_secretary_tools

# Carregar prompt base
PROMPT_SECRETARY_BASE = (Path(__file__).parent.parent / "prompts" / "recepcao.md").read_text()


def build_secretary_agent(contact_id: UUID):
    """
    Cria o agente 'Aline Atendimento', especializado em recepcionar e auxiliar pacientes.
    Este agente é um ReAct Agent e pode raciocinar antes de usar as ferramentas.

    Args:
        contact_id: ID do contato para injetar nas ferramentas via closure
    """
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)

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
    contexto_data = f"\n\n---\n\n## 📅 Contexto Temporal\n\n**Data de hoje:** {data_formatada} ({dia_semana_pt})\n"
    system_prompt = PROMPT_SECRETARY_BASE + contexto_data

    # Criar ferramentas com contact_id injetado via closure
    tools = create_secretary_tools(contact_id)

    # Criar agente ReAct moderno (LangChain 1.x)
    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt
    )

    return agent


def create_recepcao_node():
    """Cria o nó de recepção com todas as ferramentas e lógica de processamento."""

    def secretary_node(state: State) -> dict:
        """Processa atendimento inicial e rotas para agenda quando necessário."""
        print("👋 [RECEPÇÃO NODE] Iniciando processamento...")

        # Criar agente com contact_id injetado nas ferramentas
        secretary_agent = build_secretary_agent(contact_id=state.contact.id)

        # Preparar mensagens com histórico completo
        messages = list(state.history)
        print(f"📚 [RECEPÇÃO NODE] Histórico: {len(messages)} mensagens")

        # Executar agente COM histórico
        result = secretary_agent.invoke({"messages": messages})

        # Extrair resposta das mensagens retornadas pelo agente
        ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
        output = ai_messages[-1].content if ai_messages else "Erro ao processar mensagem"

        print(f"💬 [RECEPÇÃO NODE] Resposta: {output[:200]}...")

        # Verificar se identificou intenção de agenda
        if "AGENDA" in output:
            print("🎯 [RECEPÇÃO NODE] Intenção de AGENDA detectada — roteando")
            return {
                "history": [HumanMessage(content=state.user_message)],
                "agent": "agenda"
            }

        # Resposta direta ao usuário
        return {
            "history": [AIMessage(content=output)],
            "agent": END
        }

    return secretary_node
