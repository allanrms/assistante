from agents.models import Message, ConversationSummary, LongTermMemory
from agents.patterns.factories.llm_factory import LLMFactory


def create_conversation_summary(conversation) -> str:
    """
    Cria ou atualiza o resumo de uma conversa usando LLM.
    Retorna o texto do resumo criado.
    """
    try:
        # Obter LLM do Agent configurado
        print(f"📝 [SUMMARY] Iniciando criação de resumo para conversa #{conversation.id}")

        if not conversation.evolution_instance or not conversation.evolution_instance.agent:
            print(f"⚠️ [SUMMARY] Nenhum agente configurado para a conversa #{conversation.id}")
            return ""

        agent_config = conversation.evolution_instance.agent

        # Criar LLM diretamente (sem factory, já que não precisamos de tools/agent)
        from langchain_google_genai import ChatGoogleGenerativeAI

        print(f"🤖 [SUMMARY] Criando LLM para resumo...")
        factory = LLMFactory(
            agent=agent_config,
            contact_id=conversation.contact.id,
            tools_factory=[],
            evolution_instance=conversation.evolution_instance
        )

        summary_llm = factory.llm

        # Pegar todas as mensagens da conversa
        messages = Message.objects.filter(conversation=conversation).order_by("created_at")

        if not messages.exists():
            print(f"⚠️ [SUMMARY] Nenhuma mensagem encontrada para conversa #{conversation.id}")
            return ""

        print(f"📚 [SUMMARY] Processando {messages.count()} mensagem(ns)...")

        # Montar histórico para o LLM (cada Message tem content do usuário e response da IA)
        history_text = []
        for msg in messages:
            if msg.content:
                history_text.append(f"Usuário: {msg.content}")
            if msg.response:
                history_text.append(f"Assistente: {msg.response}")

        full_history = "\n".join(history_text)

        if not full_history.strip():
            print(f"⚠️ [SUMMARY] Histórico vazio para conversa #{conversation.id}")
            return ""

        print(f"📄 [SUMMARY] Histórico montado ({len(full_history)} caracteres)")

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

        print(f"🤖 [SUMMARY] Invocando LLM para gerar resumo...")

        # Gerar resumo com LLM
        response = summary_llm.invoke(prompt)

        # Verificar se response tem content
        if not hasattr(response, 'content'):
            print(f"❌ [SUMMARY] Resposta do LLM não tem atributo 'content': {type(response)}")
            print(f"❌ [SUMMARY] Response completo: {response}")
            return ""

        summary_text = response.content.strip()

        if not summary_text:
            print(f"⚠️ [SUMMARY] LLM retornou resumo vazio")
            return ""

        print(f"✅ [SUMMARY] Resumo gerado ({len(summary_text)} caracteres)")

        # Salvar ou atualizar no banco
        summary_obj, created = ConversationSummary.objects.update_or_create(
            conversation=conversation,
            defaults={"summary": summary_text}
        )

        action = "Criado" if created else "Atualizado"
        print(f"📝 [SUMMARY] {action} resumo para conversa #{conversation.id}: {summary_text[:100]}...")

        return summary_text

    except Exception as e:
        import traceback
        print(f"❌ [SUMMARY] Erro ao criar resumo para conversa #{conversation.id}: {str(e)}")
        traceback.print_exc()
        return ""


def extract_long_term_facts(conversation) -> list:
    """
    Extrai fatos importantes da conversa e salva em LongTermMemory com embeddings.
    Retorna lista de fatos extraídos.
    """
    try:
        print(f"🧠 [FACTS] Iniciando extração de fatos para conversa #{conversation.id}")

        if not conversation.evolution_instance or not conversation.evolution_instance.agent:
            print(f"⚠️ [FACTS] Nenhum agente configurado para a conversa #{conversation.id}")
            return []

        agent_config = conversation.evolution_instance.agent

        # Criar LLM e embeddings diretamente
        from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
        from agents.patterns.factories.llm_factory import PaddedEmbeddings

        print(f"🤖 [FACTS] Criando LLM e embeddings para extração...")

        factory = LLMFactory(
            agent=agent_config,
            contact_id=conversation.contact.id,
            tools_factory=[],
            evolution_instance=conversation.evolution_instance
        )

        summary_llm = factory.llm
        emb = factory.embeddings

        contact = conversation.contact

        # Pegar todas as mensagens da conversa
        messages = Message.objects.filter(conversation=conversation).order_by("created_at")

        if not messages.exists():
            print(f"⚠️ [FACTS] Nenhuma mensagem encontrada para conversa #{conversation.id}")
            return []

        print(f"📚 [FACTS] Processando {messages.count()} mensagem(ns)...")

        # Montar histórico para o LLM (cada Message tem content do usuário e response da IA)
        history_text = []
        for msg in messages:
            if msg.content:
                history_text.append(f"Usuário: {msg.content}")
            if msg.response:
                history_text.append(f"Assistente: {msg.response}")

        full_history = "\n".join(history_text)

        if not full_history.strip():
            print(f"⚠️ [FACTS] Histórico vazio para conversa #{conversation.id}")
            return []

        print(f"📄 [FACTS] Histórico montado ({len(full_history)} caracteres)")

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

        print(f"🤖 [FACTS] Invocando LLM para extrair fatos...")

        # Gerar fatos com LLM
        response = summary_llm.invoke(prompt)

        # Verificar se response tem content
        if not hasattr(response, 'content'):
            print(f"❌ [FACTS] Resposta do LLM não tem atributo 'content': {type(response)}")
            return []

        facts_text = response.content.strip()

        if not facts_text:
            print(f"⚠️ [FACTS] LLM retornou texto vazio")
            return []

        print(f"✅ [FACTS] Fatos extraídos do LLM")

        # Parsear fatos (cada linha começando com "- ")
        facts = [
            line.strip("- ").strip()
            for line in facts_text.split("\n")
            if line.strip().startswith("-")
        ]

        print(f"📋 [FACTS] Parseados {len(facts)} fato(s)")

        # Salvar cada fato no banco com embedding
        saved_facts = []
        for fact in facts:
            if len(fact) < 10:  # Ignorar fatos muito curtos
                print(f"⚠️ [FACTS] Fato muito curto, ignorando: {fact}")
                continue

            # Verificar se já existe um fato similar (evitar duplicatas)
            existing = LongTermMemory.objects.filter(
                contact=contact,
                content=fact
            ).exists()

            if existing:
                print(f"⚠️ [FACTS] Fato já existe, pulando: {fact[:50]}...")
                continue

            try:
                # Gerar embedding
                print(f"🔢 [FACTS] Gerando embedding para: {fact[:50]}...")
                embedding_vector = emb.embed_query(fact)

                # Salvar no banco com provider
                memory, created = LongTermMemory.objects.update_or_create(
                    conversation=conversation,
                    content=fact,
                    defaults={
                        "embedding": embedding_vector,
                        "embedding_provider": emb.provider,
                        "contact": contact
                    }
                )
                saved_facts.append(fact)
                action = "Criado" if created else "Atualizado"
                print(f"💾 [FACTS] {action} fato #{memory.id}: {fact[:80]}...")

            except Exception as e:
                print(f"❌ [FACTS] Erro ao salvar fato: {str(e)}")
                continue

        print(f"✅ [FACTS] Extraídos e salvos {len(saved_facts)} fato(s) para contato #{contact.id}")

        return saved_facts

    except Exception as e:
        import traceback
        print(f"❌ [FACTS] Erro ao extrair fatos para conversa #{conversation.id}: {str(e)}")
        traceback.print_exc()
        return []