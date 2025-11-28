from __future__ import annotations
from typing import Any, Dict, List
from langchain_classic.memory.chat_memory import BaseChatMemory
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from agents.models import Message


class DjangoConversationMemory(BaseChatMemory):
    """
    Memory que salva histórico de conversação usando models Django.

    Usa:
    - Conversation para identificar a conversa
    - Message para armazenar mensagens do usuário e respostas da IA
    """

    conversation: Any = None

    class Config:
        arbitrary_types_allowed = True

    @property
    def memory_variables(self) -> List[str]:
        return ["chat_history"]

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Carrega mensagens do banco e transforma em histórico para o LangChain.
        """

        msgs = Message.objects.filter(
            conversation=self.conversation
        ).order_by("created_at")

        langchain_messages: List[BaseMessage] = []

        for m in msgs:
            if m.content:
                langchain_messages.append(HumanMessage(content=m.content))
            if m.response:
                langchain_messages.append(AIMessage(content=m.response))

        return {"chat_history": langchain_messages}

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """
        Salva nova interação no banco (mensagem do usuário e resposta da IA).
        """

        Message.objects.create(
            conversation=self.conversation,
            content=inputs.get("input"),
            response=outputs.get("output"),
            message_type="text",
        )

    def clear(self) -> None:
        """
        Limpa o histórico da conversa.
        """
        Message.objects.filter(conversation=self.conversation).delete()