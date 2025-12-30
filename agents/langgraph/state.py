"""
States do LangGraph para Secretária Virtual

Este módulo define os estados que serão passados entre os nós dos grafos.

Arquitetura:
- BaseSecretaryState: Estado base com campos comuns a todos os fluxos
- SecretaryState: Estado específico para agendamento de consultas
- [Futuro] SupportSecretaryState: Estado para suporte técnico
- [Futuro] SalesSecretaryState: Estado para vendas
"""

from typing import Optional, Any
from pydantic import BaseModel


class BaseSecretaryState(BaseModel):
    """
    Estado base para todos os fluxos de secretária virtual.

    Campos comuns compartilhados por todos os tipos de fluxo.

    Attributes:
        conversation: Objeto Conversation do Django
        message: Objeto Message do Django
        user_input: Texto enviado pelo usuário
        agent: Objeto Agent (modelo Django) com configurações do LLM
        channel: Canal de comunicação ('whatsapp' ou 'direct')
        chat_history: Histórico de mensagens da conversa
        response: Resposta a ser enviada ao usuário
        messages_sent: Lista de mensagens enviadas (para canal 'direct')
    """
    conversation: Any  # Objeto Conversation do Django
    message: Any  # Objeto Message do Django
    user_input: str
    agent: Any  # Objeto Agent do Django
    channel: str = 'whatsapp'  # 'whatsapp' ou 'direct'
    chat_history: list = []  # Histórico de mensagens (HumanMessage, AIMessage)
    response: Optional[str] = None
    messages_sent: list = []  # Lista de mensagens enviadas (para acumular)

    class Config:
        arbitrary_types_allowed = True


class SecretaryState(BaseSecretaryState):
    """
    Estado específico para o fluxo de agendamento de consultas.

    Herda campos base e adiciona campos específicos para o domínio
    de agendamento médico.

    Attributes:
        intent: Intenção detectada (AGENDAR, CONSULTAR, CANCELAR, REAGENDAR, HUMANO, OUTRO)
        step: Etapa atual do fluxo (ex: AGUARDANDO_ID_CANCELAR, AGUARDANDO_ID_REAGENDAR)
        appointment: Objeto Appointment sendo manipulado (opcional)
    """
    intent: Optional[str] = None
    step: Optional[str] = None
    appointment: Optional[Any] = None


