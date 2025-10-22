# langgraph_app/runner.py
import uuid
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from core.models import Contact
from whatsapp_connector.models import ChatSession, MessageHistory
from agents.nodes import (
    create_recepcao_node,
    create_agenda_node,
)

class State(TypedDict):
    """
    Estado compartilhado entre os agentes do grafo LangGraph.

    Attributes:
        history: Histórico de mensagens da conversa (HumanMessage, AIMessage, SystemMessage)
        agent: Nome do próximo agente a ser executado ('recepcao', 'agenda', ou END)
        confirmed: Flag indicando se um agendamento foi confirmado
    """
    history: Annotated[Sequence[BaseMessage], add_messages]
    agent: str
    confirmed: bool


def create_app_for_number(contact: Contact, client=None):
    """Cria um app LangGraph personalizado para um número WhatsApp"""

    # Criar nós dos agentes (cada um cria suas próprias tools internamente)
    recepcao_node = create_recepcao_node(contact)
    agenda_node = create_agenda_node(contact, client)

    def router(state: State) -> str:
        """Routes to the next agent based on state["agent"]"""
        return state["agent"]

    # Criar grafo
    graph = StateGraph(State)
    graph.add_node("recepcao", recepcao_node)
    graph.add_node("agenda", agenda_node)

    # Set entry point
    graph.add_edge(START, "recepcao")

    # Conditional edges
    graph.add_conditional_edges(
        "recepcao",
        router,
        {
            "agenda": "agenda",
            END: END
        }
    )

    graph.add_conditional_edges(
        "agenda",
        router,
        {
            "recepcao": "recepcao",
            END: END
        }
    )

    return graph.compile()


def run_ai_turn(from_number, to_number, user_message, owner, evolution_instance=None):
    # Obtém ou cria contato
    from core.models import Contact
    contact, contact_created = Contact.get_or_create_from_whatsapp(
        phone_number=from_number,
        client=owner
    )
    print(f"👤 [Contact] {'Criado' if contact_created else 'Encontrado'}: {contact.phone_number}")

    # Obtém ou cria sessão
    session, created = ChatSession.get_or_create_active_session(
        contact=contact,
        from_number=from_number,
        to_number=to_number,
        evolution_instance=evolution_instance,
    )

    # Associar contato à sessão se ainda não tiver
    if not session.contact:
        session.contact = contact
        session.save(update_fields=['contact'])
        print(f"✅ [Session] Contato associado à sessão")

    # Monta histórico a partir das últimas mensagens
    messages = []
    last_msgs = session.messages.order_by("created_at").all()[:10]
    for msg in last_msgs:
        if msg.response:
            messages.append(AIMessage(content=msg.response))
        if msg.content:
            messages.append(HumanMessage(content=msg.content))

    # Adiciona nova mensagem do usuário ao histórico
    messages.append(HumanMessage(content=user_message))

    # Criar app personalizado para este número e client
    app = create_app_for_number(contact, owner)

    # Prepara o state inicial com o histórico
    initial_input = {
        "history": messages,
        "agent": "recepcao",
        "confirmed": False
    }

    # Executa o grafo LangGraph
    result = app.invoke(initial_input)

    # Extrai última mensagem AI
    ai_messages = [m for m in result["history"] if isinstance(m, AIMessage)]
    last_ai_message = ai_messages[-1].content if ai_messages else "Erro ao processar"

    # Salva no banco
    MessageHistory.objects.create(
        chat_session=session,
        owner=owner,
        message_id=f"msg_{str(uuid.uuid4())}",
        message_type="text",
        content=user_message,
        response=last_ai_message,
    )

    session.contact_summary = f"Última interação: {last_ai_message[:180]}..."
    session.save(update_fields=["contact_summary", "updated_at"])

    return last_ai_message, session
