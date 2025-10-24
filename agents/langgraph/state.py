from typing import Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from dataclasses import dataclass, field
from typing import List, Optional, Any


@dataclass
class State:
    """
    Estado compartilhado entre os agentes do grafo LangGraph.

    Attributes:
        history: Histórico de mensagens da conversa (HumanMessage, AIMessage, SystemMessage)
        agent: Nome do próximo agente a ser executado ('recepcao', 'agenda', ou END)
        confirmed: Flag indicando se um agendamento foi confirmado
    """

    # --- Campos obrigatórios (sem default) ---
    history: Annotated[Sequence[BaseMessage], add_messages]

    # --- Campos opcionais / com valores padrão ---
    agent: str = "recepcao"                 # nome do nó atual ("recepcao" ou "agenda")
    user_message: str = ""                  # mensagem atual do usuário
    confirmed: bool = False                 # flag de confirmação de agendamento
    conversation_id: Optional[int] = None   # ID da conversa
    summary: Optional[str] = None           # resumo longo da conversa
    retrieved_facts: List[str] = field(default_factory=list)  # fatos relevantes do RAG
    output_text: Optional[str] = None       # resposta final do agente atual
    contact: Optional[Any] = None           # objeto Contact (Django)
    client: Optional[Any] = None            # instância do cliente / empresa
    from_agent: Optional[str] = None        # agente anterior ("agenda" ou "recepcao")
    last_result_msg: Optional[str] = None   # última mensagem retornada pelo agente anterior