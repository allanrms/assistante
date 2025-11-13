from typing import Annotated, Sequence, Optional, Any
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from dataclasses import dataclass


@dataclass
class State:
    """
    Estado compartilhado para processamento de mensagens com LangGraph.

    Attributes:
        history: Histórico de mensagens da conversa (HumanMessage, AIMessage, SystemMessage)
        contact: Objeto Contact do usuário
        evolution_instance: Instância Evolution do WhatsApp
    """

    # --- Campos obrigatórios (sem default) ---
    history: Annotated[Sequence[BaseMessage], add_messages]

    # --- Campos opcionais / com valores padrão ---
    user_message: str = ""                  # mensagem atual do usuário
    conversation_id: Optional[int] = None   # ID da conversa
    contact: Optional[Any] = None           # objeto Contact (Django)
    client: Optional[Any] = None            # instância do cliente / empresa
    evolution_instance: Optional[Any] = None  # instância Evolution do WhatsApp