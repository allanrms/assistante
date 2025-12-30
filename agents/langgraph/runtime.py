"""
Runtime para gerenciamento de conversas e mensagens

Este módulo encapsula as operações de envio de mensagens e
acesso ao contexto da conversa.
"""

from agents.models import Message


class SecretaryRuntime:
    """
    Runtime que encapsula operações de conversa.

    Attributes:
        conversation: Objeto Conversation do Django
        evolution_instance: Instância Evolution para envio de mensagens
        channel: Canal de comunicação ('whatsapp' ou 'direct')
        messages_buffer: Buffer de mensagens para canal 'direct'
    """

    def __init__(self, conversation, channel='whatsapp', messages_buffer=None):
        """
        Inicializa o runtime com uma conversa existente.

        Args:
            conversation: Objeto Conversation do Django
            channel: Canal de comunicação ('whatsapp' ou 'direct')
            messages_buffer: Lista para acumular mensagens (para canal 'direct')
        """
        self.conversation = conversation
        self.evolution_instance = self.conversation.evolution_instance
        self.channel = channel
        self.messages_buffer = messages_buffer if messages_buffer is not None else []

    def send_message(self, text: str):
        """
        Envia uma mensagem de texto para o usuário.

        Args:
            text: Texto da mensagem a ser enviada

        Returns:
            str: Texto enviado (para canal 'direct') ou True/False (para whatsapp)

        Regras:
            - NUNCA enviar se Conversation.status != 'ai'
            - Para canal 'whatsapp': envia via Evolution API
            - Para canal 'direct': acumula no buffer e retorna o texto
        """
        # Verificar se pode enviar (guard)
        if self.conversation.status != 'ai':
            print(f"⚠️ Bloqueado: Conversa {self.conversation.id} não está em modo AI (status: {self.conversation.status})")
            return False

        # Canal DIRECT: apenas acumular mensagem
        if self.channel == 'direct':
            self.messages_buffer.append(text)
            return text

        # Canal WHATSAPP: enviar via Evolution API
        try:
            if self.evolution_instance:
                from whatsapp_connector.utils import send_whatsapp_message

                send_whatsapp_message(
                    instance=self.evolution_instance,
                    to_number=self.conversation.from_number,
                    message=text
                )

                print(f"✅ Mensagem enviada via WhatsApp para {self.conversation.from_number}")
                return True
            else:
                print(f"⚠️ Nenhuma instância Evolution configurada para a conversa {self.conversation.id}")
                return False

        except Exception as e:
            print(f"❌ Erro ao enviar mensagem via WhatsApp: {e}")
            return False

    def get_conversation_history(self, limit: int = 10):
        """
        Retorna histórico recente da conversa.

        Args:
            limit: Número máximo de mensagens a retornar

        Returns:
            QuerySet: Mensagens ordenadas por data
        """
        return Message.objects.filter(
            conversation=self.conversation
        ).order_by('-created_at')[:limit]

    def get_contact(self):
        """
        Retorna o contato da conversa.

        Returns:
            Contact: Objeto contato ou None
        """
        return self.conversation.contact

    def is_ai_allowed(self):
        """
        Verifica se a IA pode responder nesta conversa.

        Returns:
            bool: True se status == 'ai'
        """
        return self.conversation.status == 'ai'