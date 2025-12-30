from agents.langgraph.graph import build_secretary_graph
from agents.langgraph.state import SecretaryState
from agents.models import LLMUsage, Message, Agent
from langchain_core.messages import HumanMessage, AIMessage
import time

SECRETARY_GRAPH = build_secretary_graph()

def load_chat_history(conversation):
    """
    Carrega o histórico de mensagens da conversa do banco de dados.

    Args:
        conversation: Objeto Conversation do Django

    Returns:
        list: Lista de mensagens LangChain (HumanMessage, AIMessage)
    """
    messages = Message.objects.filter(
        conversation=conversation
    ).order_by("created_at")

    chat_history = []
    for msg in messages:
        if msg.content:
            chat_history.append(HumanMessage(content=msg.content))
        if msg.response:
            chat_history.append(AIMessage(content=msg.response))

    return chat_history


def ask_secretary(message: Message, agent_model: Agent, channel: str = 'whatsapp') -> dict:
    """
    Processa uma mensagem usando o grafo LangGraph da Secretária Virtual.

    Args:
        message: Objeto Message do Django
        agent_model: Configuração do agente LLM
        channel: Canal de comunicação ('whatsapp' ou 'direct')

    Returns:
        dict: Resultado com answer, sources e usage
            - Para 'whatsapp': answer é a última resposta (enviada via WhatsApp)
            - Para 'direct': answer contém TODAS as mensagens acumuladas (saudação + resposta)
    """
    conversation = message.conversation

    # Carregar histórico da conversa
    chat_history = load_chat_history(conversation)

    # Criar estado inicial usando Pydantic model
    state = SecretaryState(
        conversation=conversation,
        message=message,
        user_input=message.content or "",
        agent=agent_model,
        channel=channel,
        chat_history=chat_history,  # Passar histórico para o grafo
        messages_sent=[],  # Buffer para acumular mensagens (canal 'direct')
    )

    start = time.time()

    # Invocar grafo (LangGraph aceita Pydantic model diretamente)
    result = SECRETARY_GRAPH.invoke(state)

    response_time_ms = int((time.time() - start) * 1000)

    # Para canal 'direct': retornar TODAS as mensagens enviadas concatenadas
    if channel == 'direct':
        messages_sent = result.get("messages_sent", [])
        answer = "\n\n".join(messages_sent) if messages_sent else ""
    else:
        # Para canal 'whatsapp': retornar apenas a última resposta
        answer = result.get("response", "")

    # Persistir resposta
    message.response = answer
    message.processing_status = "completed"
    message.save(update_fields=["response", "processing_status"])

    # Métrica mínima (intenção)
    LLMUsage.objects.create(
        conversation=conversation,
        message=message,
        agent=agent_model,
        provider=agent_model.name,
        model_name=agent_model.model,
        input_tokens=len(message.content)//4,
        output_tokens=len(answer)//4,
        response_time_ms=response_time_ms,
    )

    return {
        "answer": answer,
        "sources": [],
        "usage": {
            "response_time_ms": response_time_ms
        }
    }
