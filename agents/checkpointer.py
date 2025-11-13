"""
Django Checkpointer for LangGraph

Este módulo fornece um checkpointer customizado que usa os modelos Django
(Conversation e Message) como backend de persistência para o LangGraph.
"""

from typing import Optional, Iterator, Any, Sequence
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata, CheckpointTuple
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage, message_to_dict
from langchain_core.messages.utils import messages_from_dict
import json
from datetime import datetime


class DjangoCheckpointer(BaseCheckpointSaver):
    """
    Checkpointer que usa modelos Django (Conversation e Message) para persistência.

    Uso:
        from agents.checkpointer import DjangoCheckpointer
        from langchain.agents import create_agent

        checkpointer = DjangoCheckpointer()
        agent = create_agent(
            model="gpt-4o",
            tools=[...],
            checkpointer=checkpointer,
        )

        # Usar com thread_id = conversation.id
        result = agent.invoke(
            {"messages": [{"role": "user", "content": "Hello"}]},
            {"configurable": {"thread_id": str(conversation.id)}}
        )
    """

    def __init__(self):
        super().__init__(serde=JsonPlusSerializer())

    def _django_messages_to_langchain(self, conversation) -> list[BaseMessage]:
        """
        Converte mensagens do Django para o formato LangChain.

        Args:
            conversation: Instância do modelo Conversation

        Returns:
            Lista de mensagens LangChain
        """
        from agents.models import Message

        messages = []
        # Carregar apenas mensagens com resposta (evitar duplicação com webhook)
        # Mensagens sem resposta serão adicionadas via invoke()
        django_messages = Message.objects.filter(
            conversation=conversation,
            response__isnull=False  # Apenas mensagens com resposta
        ).order_by('received_at')

        for msg in django_messages:
            # Mensagem do usuário (HumanMessage)
            if msg.content:
                messages.append(HumanMessage(
                    content=msg.content,
                    id=msg.message_id,
                    additional_kwargs={
                        'message_type': msg.message_type,
                        'media_url': msg.media_url,
                        'sender_name': msg.sender_name,
                        'audio_transcription': msg.audio_transcription,
                        'created_at': msg.created_at.isoformat(),
                    }
                ))

            # Resposta da IA (AIMessage)
            if msg.response:
                # Gerar um ID único para a resposta
                response_id = f"{msg.message_id}_response"
                messages.append(AIMessage(
                    content=msg.response,
                    id=response_id,
                    additional_kwargs={
                        'original_message_id': msg.message_id,
                        'created_at': msg.updated_at.isoformat(),
                    }
                ))

        return messages

    def _langchain_messages_to_django(self, conversation, messages: Sequence[BaseMessage]):
        """
        Persiste mensagens LangChain no Django.

        Args:
            conversation: Instância do modelo Conversation
            messages: Lista de mensagens LangChain
        """
        from agents.models import Message
        import json

        # Rastrear a última HumanMessage processada para mapear a AIMessage correta
        last_human_msg = None

        for i, msg in enumerate(messages, 1):
            msg_dict = message_to_dict(msg)

            if isinstance(msg, HumanMessage):
                # Verificar se já existe mensagem criada pelo webhook (por conteúdo + conversation)
                # Isso evita criar duplicatas quando o webhook já criou a mensagem
                existing_by_content = Message.objects.filter(
                    conversation=conversation,
                    content=msg.content,
                    message_type='text'
                ).first()

                if existing_by_content:
                    # Rastrear esta mensagem para associar a próxima AIMessage
                    last_human_msg = existing_by_content
                    continue

                # Gerar message_id único se não existir
                import hashlib

                if hasattr(msg, 'id') and msg.id:
                    msg_id = msg.id
                else:
                    # Criar um ID único baseado no hash do conteúdo + conversation_id
                    content_hash = hashlib.md5(
                        f"{conversation.id}:{msg.content}".encode()
                    ).hexdigest()
                    msg_id = f"msg_{content_hash}"

                # Verificar se já existe por message_id
                existing_msg = Message.objects.filter(message_id=msg_id).first()
                if existing_msg:
                    # Rastrear esta mensagem para associar a próxima AIMessage
                    last_human_msg = existing_msg
                    continue

                # Criar nova mensagem de usuário
                new_msg = Message.objects.create(
                    conversation=conversation,
                    message_id=msg_id,
                    content=msg.content,
                    message_type='text',
                    processing_status='completed',
                    owner=conversation.contact.client if conversation.contact else None,
                )
                # Rastrear esta mensagem para associar a próxima AIMessage
                last_human_msg = new_msg

            elif isinstance(msg, AIMessage):
                # Extrair o conteúdo da resposta
                response_content = msg.content

                # Garantir que response_content é string
                if isinstance(response_content, list):
                    # Se for lista, concatenar os elementos
                    response_content = "\n".join([str(item) for item in response_content])
                elif response_content is None:
                    response_content = ""
                else:
                    response_content = str(response_content)

                # Se o content estiver vazio ou for JSON estruturado, tentar extrair
                if not response_content or response_content == "" or response_content.startswith("{"):
                    # Tentar extrair de tool_calls (structured output)
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            if 'args' in tool_call:
                                args = tool_call['args']
                                # Extrair punny_response se existir
                                if 'punny_response' in args:
                                    response_content = args['punny_response']
                                    # Adicionar weather_conditions se existir
                                    if 'weather_conditions' in args and args['weather_conditions']:
                                        response_content += f"\n\n{args['weather_conditions']}"
                                    break

                    # Se ainda não tem conteúdo, tentar parsear o msg.content como JSON
                    if (not response_content or response_content.startswith("{")) and msg.content and isinstance(msg.content, str):
                        try:
                            # Tentar parsear como JSON
                            content_json = json.loads(msg.content)
                            if 'arguments' in content_json:
                                args_json = json.loads(content_json['arguments'])
                                if 'punny_response' in args_json:
                                    response_content = args_json['punny_response']
                                    if 'weather_conditions' in args_json and args_json['weather_conditions']:
                                        response_content += f"\n\n{args_json['weather_conditions']}"
                        except (json.JSONDecodeError, KeyError):
                            # Se não conseguir parsear, usar o conteúdo como está
                            pass

                    # Verificar additional_kwargs
                    if not response_content or response_content.startswith("{"):
                        if hasattr(msg, 'additional_kwargs') and msg.additional_kwargs:
                            if 'structured_response' in msg.additional_kwargs:
                                structured = msg.additional_kwargs['structured_response']
                                if hasattr(structured, 'punny_response'):
                                    response_content = structured.punny_response
                                    if hasattr(structured, 'weather_conditions') and structured.weather_conditions:
                                        response_content += f"\n\n{structured.weather_conditions}"
                            elif 'function_call' in msg.additional_kwargs:
                                func_call = msg.additional_kwargs['function_call']
                                if 'arguments' in func_call:
                                    try:
                                        args_json = json.loads(func_call['arguments'])
                                        if 'punny_response' in args_json:
                                            response_content = args_json['punny_response']
                                            if 'weather_conditions' in args_json and args_json['weather_conditions']:
                                                response_content += f"\n\n{args_json['weather_conditions']}"
                                    except (json.JSONDecodeError, KeyError):
                                        pass

                # Debug: imprimir se não conseguiu extrair conteúdo
                if not response_content or response_content.startswith("{"):
                    # Usar o content original como fallback
                    response_content = msg.content if msg.content else "[Resposta vazia]"

                # Verificar se já existe uma mensagem com essa resposta (evitar duplicação)
                msg_id = msg.id if hasattr(msg, 'id') and msg.id else None

                if msg_id and Message.objects.filter(message_id=msg_id).exists():
                    # Mensagem já existe, apenas atualizar se necessário
                    existing_msg = Message.objects.get(message_id=msg_id)
                    if existing_msg.response != response_content:
                        existing_msg.response = response_content
                        existing_msg.processing_status = 'completed'
                        existing_msg.save()
                    continue

                # Usar a última HumanMessage rastreada no loop
                if last_human_msg and not last_human_msg.response:
                    # Atualizar com a resposta
                    last_human_msg.response = response_content
                    last_human_msg.processing_status = 'completed'
                    last_human_msg.save()
                    # Resetar para não reutilizar
                    last_human_msg = None
                elif last_human_msg and last_human_msg.response:
                    # Já tem resposta, não sobrescrever
                    last_human_msg = None
                else:
                    # Fallback: procurar a última mensagem sem resposta
                    last_message = Message.objects.filter(
                        conversation=conversation,
                        response__isnull=True
                    ).order_by('-received_at').first()

                    if last_message:
                        last_message.response = response_content
                        last_message.processing_status = 'completed'
                        last_message.save()
                    else:
                        # NÃO criar mensagem órfã - apenas logar
                        print(f"⚠️  AIMessage sem HumanMessage correspondente, pulando...")
                        print(f"   Resposta: {response_content[:100]}...")

    def get_tuple(self, config: dict) -> Optional[CheckpointTuple]:
        """
        Carrega o checkpoint do Django (método principal usado pelo LangGraph).

        Args:
            config: Configuração contendo thread_id (conversation.id)

        Returns:
            CheckpointTuple ou None
        """
        from agents.models import Conversation

        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return None

        try:
            conversation = Conversation.objects.get(id=thread_id)
        except Conversation.DoesNotExist:
            return None

        # Converter mensagens do Django para LangChain
        messages = self._django_messages_to_langchain(conversation)

        # Criar checkpoint
        checkpoint = Checkpoint(
            v=1,
            id=str(conversation.id),
            ts=conversation.updated_at.isoformat(),
            channel_values={
                "messages": messages,
                "conversation_status": conversation.status,
                "contact_summary": conversation.contact_summary,
            },
            channel_versions={},
            versions_seen={}
        )

        metadata = CheckpointMetadata(
            source="input",
            step=len(messages),
            writes={},
            parents={},
        )

        return CheckpointTuple(
            config=config,
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=None,
        )

    def get(self, config: dict) -> Optional[CheckpointTuple]:
        """
        Alias para get_tuple (compatibilidade).
        """
        return self.get_tuple(config)

    def put(self, config: dict, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: dict) -> dict:
        """
        Salva o checkpoint no Django.

        Args:
            config: Configuração contendo thread_id (conversation.id)
            checkpoint: Estado atual do agente
            metadata: Metadados do checkpoint
            new_versions: Versões dos canais (não usado no Django backend)

        Returns:
            Configuração atualizada
        """
        from agents.models import Conversation

        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            raise ValueError("thread_id não fornecido na configuração")

        try:
            conversation = Conversation.objects.get(id=thread_id)
        except Conversation.DoesNotExist:
            raise ValueError(f"Conversation com id {thread_id} não encontrada")

        # Extrair mensagens do checkpoint
        messages = checkpoint.get("channel_values", {}).get("messages", [])

        # Persistir mensagens no Django
        self._langchain_messages_to_django(conversation, messages)

        # Atualizar status da conversa se disponível
        if "conversation_status" in checkpoint.get("channel_values", {}):
            conversation.status = checkpoint["channel_values"]["conversation_status"]

        # Atualizar resumo do contato se disponível
        if "contact_summary" in checkpoint.get("channel_values", {}):
            conversation.contact_summary = checkpoint["channel_values"]["contact_summary"]

        conversation.save()

        return config

    def list(self, config: dict, filter: Optional[dict] = None, before: Optional[dict] = None, limit: Optional[int] = None) -> Iterator[CheckpointTuple]:
        """
        Lista checkpoints (não implementado para Django).
        """
        # Para simplicidade, retornar apenas o checkpoint atual
        checkpoint = self.get(config)
        if checkpoint:
            yield checkpoint

    def put_writes(self, config: dict, writes: Sequence[tuple], task_id: str) -> None:
        """
        Persiste writes intermediários (não implementado para Django).
        """
        pass


# Funções auxiliares de conversão
def conversation_to_messages(conversation) -> list[dict]:
    """
    Converte uma Conversation Django para lista de mensagens no formato LangChain.

    Args:
        conversation: Instância do modelo Conversation

    Returns:
        Lista de dicts com role e content
    """
    from agents.models import Message

    messages = []
    django_messages = Message.objects.filter(
        conversation=conversation
    ).order_by('received_at')

    for msg in django_messages:
        # Mensagem do usuário
        if msg.content:
            messages.append({
                "role": "user",
                "content": msg.content,
            })

        # Resposta da IA
        if msg.response:
            messages.append({
                "role": "assistant",
                "content": msg.response,
            })

    return messages


def save_message_to_conversation(conversation, role: str, content: str, message_id: Optional[str] = None):
    """
    Salva uma mensagem na Conversation Django.

    Args:
        conversation: Instância do modelo Conversation
        role: "user" ou "assistant"
        content: Conteúdo da mensagem
        message_id: ID único da mensagem (opcional)
    """
    from agents.models import Message

    if role == "user":
        Message.objects.create(
            conversation=conversation,
            message_id=message_id,
            content=content,
            message_type='text',
            processing_status='completed',
            owner=conversation.contact.client if conversation.contact else None,
        )
    elif role == "assistant":
        # Procurar a última mensagem sem resposta
        last_message = Message.objects.filter(
            conversation=conversation,
            response__isnull=True
        ).order_by('-received_at').first()

        if last_message:
            last_message.response = content
            last_message.processing_status = 'completed'
            last_message.save()
        else:
            # Criar nova mensagem se não encontrar
            Message.objects.create(
                conversation=conversation,
                message_id=message_id,
                response=content,
                message_type='text',
                processing_status='completed',
                owner=conversation.contact.client if conversation.contact else None,
            )