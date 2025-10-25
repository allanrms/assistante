from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from agents.models import Conversation, Message, ConversationSummary, LongTermMemory


# LLM para criar resumos e extrair fatos
summary_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
emb = OpenAIEmbeddings(model="text-embedding-3-small")


def create_conversation_summary(conversation) -> str:
    """
    Cria ou atualiza o resumo de uma conversa usando LLM.
    Retorna o texto do resumo criado.
    """
    from agents.models import Conversation, ConversationSummary, Message

    # Pegar todas as mensagens da conversa
    messages = Message.objects.filter(conversation=conversation).order_by("created_at")

    if not messages.exists():
        return ""

    # Montar histórico para o LLM (cada Message tem content do usuário e response da IA)
    history_text = []
    for msg in messages:
        history_text.append(f"Usuário: {msg.content}")
        if msg.response:
            history_text.append(f"Assistente: {msg.response}")

    full_history = "\n".join(history_text)

    # Prompt para criar resumo
    prompt = f"""Analise a conversa abaixo e crie um resumo conciso e informativo.

O resumo deve incluir:
- Principais assuntos discutidos
- Informações importantes sobre o usuário
- Ações realizadas (agendamentos, atualizações, etc.)
- Status atual da conversa

Conversa:
{full_history}

Resumo:"""

    # Gerar resumo com LLM
    response = summary_llm.invoke(prompt)
    summary_text = response.content.strip()

    # Salvar ou atualizar no banco
    summary_obj, created = ConversationSummary.objects.update_or_create(
        conversation=conversation,
        defaults={"summary": summary_text}
    )

    action = "Criado" if created else "Atualizado"
    print(f"📝 [SUMMARY] {action} resumo para conversa #{conversation.id}: {summary_text[:100]}...")

    return summary_text


def extract_long_term_facts(conversation) -> list:
    """
    Extrai fatos importantes da conversa e salva em LongTermMemory com embeddings.
    Retorna lista de fatos extraídos.
    """
    from agents.models import Conversation, Message, LongTermMemory

    contact = conversation.contact

    # Pegar todas as mensagens da conversa
    messages = Message.objects.filter(conversation=conversation).order_by("created_at")

    if not messages.exists():
        return []

    # Montar histórico para o LLM (cada Message tem content do usuário e response da IA)
    history_text = []
    for msg in messages:
        history_text.append(f"Usuário: {msg.content}")
        if msg.response:
            history_text.append(f"Assistente: {msg.response}")

    full_history = "\n".join(history_text)

    # Prompt para extrair fatos
    prompt = f"""Analise a conversa abaixo e extraia fatos importantes sobre o usuário que devem ser lembrados em conversas futuras.

Extraia APENAS fatos concretos como:
- Preferências do usuário
- Informações pessoais mencionadas
- Restrições ou necessidades específicas
- Agendamentos confirmados
- Problemas ou preocupações relatadas

NÃO inclua:
- Saudações ou cortesias
- Perguntas sem resposta
- Informações temporárias

Retorne cada fato em uma linha, começando com "- ".

Conversa:
{full_history}

Fatos importantes:"""

    # Gerar fatos com LLM
    response = summary_llm.invoke(prompt)
    facts_text = response.content.strip()

    # Parsear fatos (cada linha começando com "- ")
    facts = [
        line.strip("- ").strip()
        for line in facts_text.split("\n")
        if line.strip().startswith("-")
    ]

    # Salvar cada fato no banco com embedding
    saved_facts = []
    for fact in facts:
        if len(fact) < 10:  # Ignorar fatos muito curtos
            continue

        # Verificar se já existe um fato similar (evitar duplicatas)
        existing = LongTermMemory.objects.filter(
            contact=contact,
            content=fact
        ).exists()

        if existing:
            print(f"⚠️ [FACTS] Fato já existe, pulando: {fact[:50]}...")
            continue

        # Gerar embedding
        embedding_vector = emb.embed_query(fact)

        # Salvar no banco
        memory = LongTermMemory.objects.update_or_create(
            conversation=conversation,
            defaults={"embedding": embedding_vector, 'content':fact, 'contact': contact}
        )
        saved_facts.append(fact)
    #     print(f"💾 [FACTS] Salvo fato #{memory.id}: {fact[:80]}...")
    #
    # print(f"✅ [FACTS] Extraídos e salvos {len(saved_facts)} fatos para contato #{contact.id}")

    return saved_facts