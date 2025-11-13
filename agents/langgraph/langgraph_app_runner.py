# agents/langgraph/langgraph_app_runner.py
"""
Sistema de execução de agentes LangGraph com memória Django.

Este módulo fornece uma interface simplificada para executar agentes LangGraph
usando os modelos Django (Conversation e Message) como backend de memória.
"""

from dataclasses import dataclass
from typing import Optional
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, RemoveMessage
from langgraph.types import Command

from agents.checkpointer import DjangoCheckpointer
from agents.langgraph.tools.secretary_tools import create_secretary_tools
from agents.models import Conversation, Message, ConversationSummary
from core.models import Contact


@dataclass
class AgentContext:
    """
    Contexto runtime para os agentes.

    Attributes:
        contact_id: ID do contato
        client_id: ID do cliente/owner
        conversation_id: ID da conversa
        evolution_instance_id: ID da instância Evolution (opcional)
    """
    contact_id: str
    client_id: str
    conversation_id: str
    evolution_instance_id: Optional[str] = None


# Checkpointer compartilhado (singleton)
django_checkpointer = DjangoCheckpointer()


class LoggingMiddleware(AgentMiddleware):
    """Middleware para logging de chamadas do agente."""

    def before_model(self, state, runtime):
        """Log antes de cada chamada ao modelo."""
        message_count = len(state.get('messages', []))
        print(f"🤖 [Middleware] Chamando modelo com {message_count} mensagem(s)")
        return None

    def after_model(self, state, runtime):
        """Log após cada chamada ao modelo."""
        if state.get('messages'):
            last_msg = state['messages'][-1]
            msg_type = type(last_msg).__name__
            print(f"✅ [Middleware] Modelo respondeu com {msg_type}")
        return None


class MessageTrimmingMiddleware(AgentMiddleware):
    """
    Middleware para gerenciar tamanho do histórico de mensagens.

    Mantém apenas as últimas N mensagens para evitar exceder limites de contexto,
    preservando sempre a mensagem do sistema.
    """

    def __init__(self, max_messages: int = 20):
        """
        Args:
            max_messages: Número máximo de mensagens a manter (além do system prompt)
        """
        self.max_messages = max_messages

    def before_model(self, state, runtime):
        """Trimma mensagens antigas antes de enviar ao modelo."""
        messages = state.get('messages', [])

        if len(messages) <= self.max_messages:
            return None

        # Separar mensagem do sistema (geralmente a primeira)
        system_messages = [msg for msg in messages if isinstance(msg, SystemMessage)]
        other_messages = [msg for msg in messages if not isinstance(msg, SystemMessage)]

        # Manter apenas as últimas N mensagens (além do system)
        if len(other_messages) > self.max_messages:
            print(f"✂️ [Middleware] Trimming: {len(other_messages)} → {self.max_messages} mensagens")
            trimmed_messages = other_messages[-self.max_messages:]

            # Retornar nova lista com system + últimas N mensagens
            return Command(update={'messages': system_messages + trimmed_messages})

        return None


class ErrorHandlingMiddleware(AgentMiddleware):
    """Middleware para tratamento de erros em ferramentas."""

    def wrap_tool_call(self, request, handler):
        """Captura e trata erros em chamadas de ferramentas."""
        try:
            return handler(request)
        except Exception as e:
            error_msg = f"Erro ao executar ferramenta: {str(e)}"
            print(f"❌ [Middleware] {error_msg}")
            # Retornar mensagem de erro para o modelo processar
            from langchain_core.messages import ToolMessage
            return ToolMessage(
                content=error_msg,
                tool_call_id=request.tool_call.get("id", "unknown")
            )


def create_reception_agent(agent_config, contact, client, evolution_instance=None, additional_context=""):
    """
    Cria um agente de recepção usando LLMFactory e create_agent do LangChain.

    Usa LLMFactory para criar modelo com configurações robustas (timeout, retries).
    O factory também cria as ferramentas automaticamente.

    Args:
        agent_config: Configuração do Agent (agents.models.Agent)
        contact: Contato do usuário
        client: Cliente/owner
        evolution_instance: Instância Evolution (opcional)
        additional_context: Contexto adicional para adicionar ao prompt (RAG, resumo, etc)

    Returns:
        Agente LangChain configurado
    """
    # Usar LLMFactory para criar modelo e tools (aplica configurações robustas)
    from agents.patterns.factories.llm_factory import LLMFactory

    print(f"🏭 [Agent] Criando LLM e tools via Factory...")
    factory = LLMFactory(
        agent=agent_config,
        contact_id=contact.id,
        tools_factory=create_secretary_tools,
        evolution_instance=evolution_instance
    )

    # Usar modelo e tools do factory (já configurados com timeout/retries)
    model = factory.llm
    tools = factory.tools

    print(f"✅ [Agent] Modelo e {len(tools)} ferramenta(s) criadas")
    for tool in tools:
        print(f"   - {tool.name}")

    # Construir prompt do agente
    system_prompt = agent_config.build_prompt()

    # Adicionar contexto adicional ao prompt se fornecido
    if additional_context:
        system_prompt = f"{system_prompt}\n\n{additional_context}"

    # Criar middlewares para melhorar funcionamento do agente
    middlewares = [
        LoggingMiddleware(),  # Logging de chamadas
        MessageTrimmingMiddleware(max_messages=20),  # Trimming de mensagens
        ErrorHandlingMiddleware(),  # Tratamento de erros em ferramentas
    ]

    # Criar agente com DjangoCheckpointer e middlewares
    agent = create_agent(
        model=model,
        system_prompt=system_prompt,
        tools=tools,
        context_schema=AgentContext,
        checkpointer=django_checkpointer,
        middleware=middlewares,  # Adicionar middlewares
    )

    return agent


def run_ai_turn(from_number, to_number, user_message, owner, evolution_instance=None):
    """
    Executa um turno de IA usando o agente LangGraph com memória Django.

    Fluxo:
    1. Obtém ou cria Contact
    2. Obtém ou cria Conversation
    3. Adiciona contexto RAG (arquivos, resumo, etc)
    4. Executa o agente (que usa DjangoCheckpointer para gerenciar memória)
    5. Extrai e retorna resposta
    6. Atualiza resumos periodicamente

    Args:
        from_number: Número do remetente
        to_number: Número do destinatário
        user_message: Mensagem do usuário
        owner: Proprietário/cliente
        evolution_instance: Instância Evolution (opcional)

    Returns:
        tuple: (resposta_da_ia, contato)
    """

    # 1. Obter ou criar contato
    contact, _ = Contact.get_or_create_from_whatsapp(
        phone_number=from_number,
        client=owner,
    )

    # 2. Obter ou criar Conversation
    conversation, _ = Conversation.get_or_create_active_session(
        contact=contact,
        from_number=from_number,
        to_number=to_number,
        evolution_instance=evolution_instance
    )

    # 3. Verificar se há agent configurado
    if not evolution_instance or not evolution_instance.agent:
        # Criar mensagem de erro
        Message.objects.create(
            conversation=conversation,
            content=user_message,
            response="Desculpe, não foi possível processar sua mensagem. Nenhum agente configurado.",
            processing_status='error',
            owner=owner
        )
        return "Desculpe, não foi possível processar sua mensagem. Nenhum agente configurado.", contact

    # 4. Preparar contexto adicional (RAG + resumo + arquivos de contexto)
    agent_config = evolution_instance.agent

    # 4.1 Buscar arquivos de CONTEXTO (context_only e both) - SEMPRE incluídos
    context_files = []
    try:
        from agents.models import AgentFile

        # Buscar todos os arquivos ativos que são context_only ou both
        context_agent_files = AgentFile.objects.filter(
            agent=agent_config,
            is_active=True,
            usage_type__in=['context_only', 'both']
        ).order_by('-updated_at')

        for file_obj in context_agent_files:
            if file_obj.extracted_content:
                content = file_obj.extracted_content
                # Limitar tamanho para não exceder contexto
                if len(content) > 3000:
                    content = content[:3000] + "\n[... conteúdo truncado ...]"

                file_content = f"📋 {file_obj.name} (Contexto)\n{content.strip()}"
                context_files.append(file_content)

        if context_files:
            print(f"📋 Contexto: {len(context_files)} arquivo(s) de contexto carregado(s)")

    except Exception as e:
        print(f"⚠️ Erro ao buscar arquivos de contexto: {str(e)}")

    # 4.2 Buscar arquivos relevantes via RAG (busca por similaridade)
    relevant_files = []
    try:
        from agents.langgraph.knowledge.vectorstore import retrieve_similar_files

        similar_files = retrieve_similar_files(
            agent=agent_config,
            query=user_message,
            top_k=3,
            only_active=True
        )

        for file_obj in similar_files:
            content = file_obj.extracted_content
            if len(content) > 2000:
                content = content[:2000] + "\n[... conteúdo truncado ...]"

            file_content = f"📄 {file_obj.name}\n{content.strip()}"
            relevant_files.append(file_content)

        if relevant_files:
            print(f"📚 RAG: {len(relevant_files)} arquivo(s) relevante(s) encontrado(s)")

    except Exception as e:
        print(f"⚠️ Erro ao buscar arquivos via RAG: {str(e)}")

    # Construir contexto adicional para o system prompt
    additional_context_parts = []

    # 4.3 Adicionar arquivos de CONTEXTO (sempre incluídos primeiro)
    if context_files:
        context_section = "**Informações de Contexto (use estas informações como base para suas respostas):**\n"
        context_section += "\n\n---\n\n".join(context_files)
        additional_context_parts.append(context_section)

    # 4.4 Adicionar contexto RAG (busca por similaridade)
    if relevant_files:
        rag_context = "**Base de Conhecimento (documentos relevantes para a pergunta):**\n"
        rag_context += "\n\n---\n\n".join(relevant_files)
        additional_context_parts.append(rag_context)

    # 4.5 Buscar resumo da conversa
    summary_obj = ConversationSummary.objects.filter(conversation=conversation).first()
    if summary_obj and summary_obj.summary:
        summary_context = f"**Resumo da conversa anterior:**\n{summary_obj.summary}"
        additional_context_parts.append(summary_context)

    # Concatenar contexto adicional
    additional_context = "\n\n".join(additional_context_parts) if additional_context_parts else ""

    try:
        # 5. Criar agente de recepção (com contexto adicional)
        agent = create_reception_agent(
            agent_config=agent_config,
            contact=contact,
            client=owner,
            evolution_instance=evolution_instance,
            additional_context=additional_context  # Passar contexto adicional
        )

        # 6. Preparar contexto
        context = AgentContext(
            contact_id=str(contact.id),
            client_id=str(owner.id),
            conversation_id=str(conversation.id),
            evolution_instance_id=str(evolution_instance.id) if evolution_instance else None
        )

        # 7. Configurar thread_id = conversation.id
        config = {"configurable": {"thread_id": str(conversation.id)}}

        # 8. Executar agente (DjangoCheckpointer gerencia o histórico automaticamente)
        print(f"\n📞 Invocando agente...")
        print(f"   Mensagem: {user_message[:50]}...")
        print(f"   Thread ID: {conversation.id}")
        print(f"   Context: {context}")

        # Estruturar mensagem usando HumanMessage (melhor prática)
        result = agent.invoke(
            {"messages": [HumanMessage(content=user_message)]},
            config=config,
            context=context
        )

        print(f"\n📋 Resultado do agente:")
        print(f"   Total de mensagens: {len(result['messages'])}")
        for i, msg in enumerate(result['messages']):
            msg_type = type(msg).__name__
            content_preview = str(msg.content)[:100] if hasattr(msg, 'content') else 'N/A'
            print(f"   [{i}] {msg_type}: {content_preview}...")

        # 9. Extrair resposta da IA
        from langchain_core.messages import AIMessage

        ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]

        if ai_messages:
            last_ai_message = ai_messages[-1].content

            # Extrair texto se content for lista de dicts
            if isinstance(last_ai_message, list):
                # Formato: [{'type': 'text', 'text': '...'}]
                text_parts = []
                for item in last_ai_message:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        text_parts.append(item.get('text', ''))
                    elif isinstance(item, str):
                        text_parts.append(item)
                last_ai_message = '\n'.join(text_parts) if text_parts else str(last_ai_message)
        else:
            last_ai_message = "Erro ao processar mensagem"
            print("❌ Nenhuma resposta da IA encontrada")

        # 10. Remover formatação markdown se necessário
        from agents.utils import remove_markdown_formatting
        last_ai_message = remove_markdown_formatting(last_ai_message)

        print(f"✅ Resposta gerada: {last_ai_message[:100]}...")

    except TimeoutError as e:
        import traceback
        traceback.print_exc()
        last_ai_message = "Desculpe, o processamento da mensagem demorou muito tempo. Por favor, tente novamente."
        print(f"❌ Timeout ao processar mensagem: {str(e)}")

        # Salvar erro no banco
        Message.objects.create(
            conversation=conversation,
            content=user_message,
            response=last_ai_message,
            processing_status='error',
            owner=owner
        )

        return last_ai_message, contact

    except ValueError as e:
        import traceback
        traceback.print_exc()
        last_ai_message = "Desculpe, houve um problema com os dados fornecidos. Por favor, tente novamente."
        print(f"❌ Erro de validação: {str(e)}")

        # Salvar erro no banco
        Message.objects.create(
            conversation=conversation,
            content=user_message,
            response=last_ai_message,
            processing_status='error',
            owner=owner
        )

        return last_ai_message, contact

    except Exception as e:
        import traceback
        traceback.print_exc()
        last_ai_message = "Desculpe, ocorreu um erro ao processar sua mensagem."
        print(f"❌ Erro inesperado: {type(e).__name__} - {str(e)}")

        # Salvar erro no banco
        Message.objects.create(
            conversation=conversation,
            content=user_message,
            response=last_ai_message,
            processing_status='error',
            owner=owner
        )

        return last_ai_message, contact

    # 11. A mensagem já foi salva pelo DjangoCheckpointer!
    # Não precisamos salvar manualmente como antes

    # 12. Criar/atualizar resumo e extrair fatos periodicamente
    message_count = Message.objects.filter(conversation=conversation).count()

    # A cada 5 mensagens → criar/atualizar resumo
    SUMMARY_INTERVAL = 5
    if message_count > 0 and message_count % SUMMARY_INTERVAL == 0:
        from agents.tasks import create_conversation_summary
        create_conversation_summary(conversation)

    # A cada 20 mensagens: extrair fatos
    if message_count % 20 == 0:
        from agents.tasks import extract_long_term_facts
        extract_long_term_facts(conversation)

    # 13. Retornar resposta e contato
    return last_ai_message, contact