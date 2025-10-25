# langgraph_app/runner.py
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langchain_openai import OpenAIEmbeddings
from pgvector.django import L2Distance

from agents.langgraph.state import State
from agents.langgraph.nodes import create_recepcao_node, create_agenda_node
from agents.models import Conversation, Message, ConversationSummary, LongTermMemory
from core.models import Contact

# Configuração de embeddings para RAG
emb = OpenAIEmbeddings(model="text-embedding-3-small")


def router(state: State) -> str:
    """Roteia para o próximo agente baseado em state.agent"""
    return state.agent


def create_app_for_number():
    """Cria um app LangGraph personalizado para um número WhatsApp"""

    # Criar nós dos agentes (cada um cria suas próprias tools internamente)
    recepcao_node = create_recepcao_node()
    agenda_node = create_agenda_node()

    # Criar grafo
    graph = StateGraph(State)
    graph.add_node("recepcao", recepcao_node)
    graph.add_node("agenda", agenda_node)

    # Define o ponto de entrada
    graph.add_edge(START, "recepcao")

    # Conditional edges baseadas no router
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
    """
    Ponto de entrada para o motor LangGraph usando Conversation/Message.

    Fluxo:
    1. Obtém ou cria Contact
    2. Obtém ou cria Conversation para esse contato
    3. Carrega histórico de mensagens do banco (últimas 10)
    4. Adiciona nova mensagem do usuário
    5. Executa o grafo LangGraph (recepcao -> agenda?)
    6. Salva mensagem do usuário e resposta da IA no banco
    7. Retorna resposta
    """
    # 1. Obter ou criar contato
    contact, contact_created = Contact.get_or_create_from_whatsapp(
        phone_number=from_number,
        client=owner,

    )
    print(f"👤 [Contact] {'Criado' if contact_created else 'Encontrado'}: {contact.phone_number}")

    # 2. Obter ou criar Conversation (excluindo conversas fechadas)
    conversation = Conversation.objects.filter(
        contact=contact,
        evolution_instance=evolution_instance
    ).exclude(status='closed').first()

    conv_created = False
    if not conversation:
        conversation = Conversation.objects.create(
            contact=contact,
            evolution_instance=evolution_instance,
            from_number=from_number,
            to_number=to_number,
            status='ai'
        )
        conv_created = True

    print(f"💬 [Conversation] {'Criada' if conv_created else 'Encontrada'}: #{conversation.id} (status: {conversation.status})")

    # 3. Carregar ConversationSummary (se existir)
    summary_obj = ConversationSummary.objects.filter(conversation=conversation).first()
    summary_text = summary_obj.summary if summary_obj else None

    # 4. Recuperar fatos relevantes via RAG (LongTermMemory com pgvector)
    query_vec = emb.embed_query(user_message)
    long_term_facts = (
        LongTermMemory.objects
        .filter(contact=contact)
        .annotate(distance=L2Distance("embedding", query_vec))
        .order_by("distance")[:3]
    )
    retrieved_facts = [fact.content for fact in long_term_facts]

    # 5. Montar histórico a partir das últimas mensagens do banco
    messages = []

    # Adicionar contexto de resumo e fatos no início (como SystemMessage)
    context_parts = []
    if summary_text:
        context_parts.append(f"**Resumo da conversa:**\n{summary_text}")
    if retrieved_facts:
        context_parts.append(f"**Fatos relevantes:**\n" + "\n".join([f"- {fact}" for fact in retrieved_facts]))

    if context_parts:
        context_message = "\n\n".join(context_parts)
        messages.append(SystemMessage(content=f"[CONTEXTO ADICIONAL]\n{context_message}"))
        print(f"📚 [CONTEXT] Adicionado resumo e {len(retrieved_facts)} fatos relevantes")

    # Carregar últimas 10 mensagens (cada Message tem content do usuário e response da IA)
    last_msgs = (
        Message.objects.filter(conversation=conversation)
        .order_by("-created_at")[:100]
    )
    last_msgs = list(last_msgs)[::-1]

    for msg in last_msgs:
        # Mensagem do usuário
        messages.append(HumanMessage(content=msg.content))
        # Resposta da IA
        if msg.response:
            messages.append(AIMessage(content=msg.response))

    # 6. Adicionar nova mensagem do usuário ao histórico
    messages.append(HumanMessage(content=user_message))

    # 7. Criar app personalizado para este contato
    app = create_app_for_number()

    # 8. Preparar state inicial
    initial_input = {
        "user_message": user_message,
        "history": messages,
        "agent": "recepcao",
        "confirmed": False,
        "contact": contact,
        "client": owner,
        "conversation_id": conversation.id,
    }

    # 9. Executar o grafo LangGraph
    result = app.invoke(initial_input)

    # 10. Extrair última mensagem AI
    ai_messages = [m for m in result["history"] if isinstance(m, AIMessage)]
    last_ai_message = ai_messages[-1].content if ai_messages else "Erro ao processar"

    # 11. Salvar no banco (1 Message com content do usuário e response da IA)
    if evolution_instance:
        message = Message.objects.filter(
            conversation=conversation,
            content=user_message,
        ).last()
        message.response = last_ai_message
        message.save()
    else:
        Message.objects.create(
            conversation=conversation,
            content=user_message,
            response=last_ai_message
        )




    print(f"💾 [Message] Salva no banco: user → AI")

    # 12. Criar/atualizar resumo e extrair fatos periodicamente
    message_count = Message.objects.filter(conversation=conversation).count()

    # A cada 10 mensagens OU se houver agendamento criado → criar/atualizar resumo
    if (message_count % 10 == 0) or result.get("confirmed"):
        print(f"📊 [AUTO] {message_count} mensagens ou agendamento criado → criando resumo...")
        from agents.tasks import create_conversation_summary
        create_conversation_summary(conversation)

    # A cada 20 mensagens: extrair fatos
    if message_count % 20 == 0:
        print(f"📊 [AUTO] {message_count} mensagens → extraindo fatos...")
        from agents.tasks import extract_long_term_facts
        extract_long_term_facts(conversation)

    # 13. Retornar resposta e contato
    return last_ai_message, contact