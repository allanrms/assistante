"""
Tools para o agente RAG.

Define as ferramentas que o agente pode usar durante a conversa.
O contexto é passado via ToolRuntime para ser thread-safe.
"""
import traceback
from typing import TYPE_CHECKING
from langchain.tools import tool, ToolRuntime

if TYPE_CHECKING:
    from agents.models import Conversation
    from langchain_core.retrievers import BaseRetriever


class AgentContextSchema:
    """Schema do contexto passado para as tools via ToolRuntime."""
    conversation: "Conversation"
    retriever: "BaseRetriever"


@tool
def request_human_intervention(
    reason: str,
    runtime: ToolRuntime,
) -> str:
    """
    🚨 FERRAMENTA CRÍTICA: Transfere atendimento para humano (USO OBRIGATÓRIO!)

    ╔══════════════════════════════════════════════════════════════════╗
    ║  🔴 REGRA ABSOLUTA - NÃO É OPCIONAL! 🔴                          ║
    ║                                                                  ║
    ║  VOCÊ NÃO PODE APENAS DIZER QUE VAI TRANSFERIR!                 ║
    ║  VOCÊ DEVE EXECUTAR A TRANSFERÊNCIA CHAMANDO ESTA FERRAMENTA!   ║
    ║                                                                  ║
    ║  ❌ ERRADO: "Vou transferir você" (sem chamar a tool)           ║
    ║  ✅ CERTO: "Vou transferir você" + CHAMAR request_human_...     ║
    ╚══════════════════════════════════════════════════════════════════╝

    ═══════════════════════════════════════════════════════════════════
    🚨 CRITÉRIOS OBRIGATÓRIOS DE TRANSFERÊNCIA (AÇÃO IMEDIATA!)
    ═══════════════════════════════════════════════════════════════════

    Se o usuário mencionar ou solicitar QUALQUER item abaixo:

    🔴 VOCÊ DEVE EXECUTAR ESTAS 2 AÇÕES NA MESMA RESPOSTA:
    1️⃣ Informar ao usuário: "Vou transferir você para um atendente humano"
    2️⃣ CHAMAR IMEDIATAMENTE esta ferramenta: request_human_intervention(reason="...")

    ⚠️ ATENÇÃO: NÃO basta apenas FALAR que vai transferir!
    ⚠️ Você PRECISA CHAMAR A FERRAMENTA para a transferência acontecer!
    ⚠️ Se você não chamar a ferramenta, o usuário NÃO será transferido!

    CRITÉRIOS CONFIGURADOS (TRANSFERÊNCIA OBRIGATÓRIA):
{intervention_rules}

    ═══════════════════════════════════════════════════════════════════
    📋 OUTRAS SITUAÇÕES QUE EXIGEM TRANSFERÊNCIA
    ═══════════════════════════════════════════════════════════════════

    1. SOLICITAÇÃO EXPLÍCITA:
       - Usuário pede para falar com atendente, humano, pessoa real, gerente
       - Frases: "quero falar com humano", "me passa alguém", "preciso de pessoa"

    2. FRUSTRAÇÃO OU INSATISFAÇÃO:
       - Usuário irritado, frustrado ou impaciente
       - Palavras: "não está ajudando", "você não entende", "isso é ridículo"
       - Reclama repetidamente do atendimento

    3. INCAPACIDADE DE RESOLVER:
       - Problema complexo além das suas capacidades
       - Já tentou 2-3 vezes sem sucesso
       - Usuário pede algo que você não tem acesso

    QUANDO NÃO USAR:
    - Perguntas normais que você pode responder
    - Pequenas dúvidas ou esclarecimentos
    - Usuário apenas fazendo perguntas, sem frustração
    - Problemas que você está conseguindo resolver

    ═══════════════════════════════════════════════════════════════════
    📝 INSTRUÇÕES OBRIGATÓRIAS
    ═══════════════════════════════════════════════════════════════════

    1. SEMPRE informe ao usuário ANTES de transferir: "Vou transferir você para um atendente humano"
    2. Seja empático: "Entendo sua situação, vou conectar você com alguém que possa ajudar melhor"
    3. Após usar esta ferramenta, não continue conversando - apenas confirme a transferência
    4. A conversa será marcada como "atendimento humano" e você não poderá mais responder

    Args:
        reason: Motivo da transferência (ex: "usuário solicitou atendente", "solicitação de atestado")

    Returns:
        str: Mensagem de confirmação da transferência

    ═══════════════════════════════════════════════════════════════════
    💡 EXEMPLOS DE USO CORRETO
    ═══════════════════════════════════════════════════════════════════

    Exemplo 1 - Solicitação explícita:
        Usuário: "Quero falar com um humano"
        Você: "Entendo! Vou transferir você para um atendente humano agora."
        Ação: request_human_intervention(reason="usuário solicitou atendente humano")

    Exemplo 2 - Critério configurado (ex: solicitação de atestado):
        Usuário: "Preciso de um atestado médico"
        Você: "Vou transferir você para um atendente que poderá ajudar com o atestado."
        Ação: request_human_intervention(reason="solicitação de atestado")

    Exemplo 3 - Frustração:
        Usuário: "Isso não está me ajudando, você não entende nada!"
        Você: "Peço desculpas pela dificuldade. Vou transferir você para um atendente humano."
        Ação: request_human_intervention(reason="usuário demonstrou frustração com atendimento")

    ⚠️ LEMBRE-SE: Se o usuário mencionar QUALQUER critério configurado acima,
    você DEVE transferir IMEDIATAMENTE. Não tente resolver sozinho!
    """
    try:
        conversation = runtime.context["conversation"]
        if not conversation:
            return "❌ ERRO: Conversa não encontrada. Não foi possível transferir."

        # Validar motivo
        if not reason or not reason.strip():
            return "❌ ERRO: É necessário informar o motivo da transferência."

        # Status anterior para log
        status_anterior = conversation.status

        # Marcar conversa como atendimento humano
        conversation.status = 'human'
        conversation.save()

        # Verificar se salvou corretamente
        conversation.refresh_from_db()

        # Log MUITO VISÍVEL da transferência
        print("\n" + "="*80)
        print("🚨🚨🚨 TRANSFERÊNCIA PARA ATENDIMENTO HUMANO EXECUTADA 🚨🚨🚨")
        print("="*80)
        print(f"📋 Conversa ID: {conversation.id}")
        print(f"📱 Contato: {conversation.from_number}")
        print(f"📝 Motivo: {reason}")
        print(f"🔄 Status: {status_anterior} → {conversation.status}")
        print(f"✅ Status confirmado no DB: {conversation.status}")
        print("="*80 + "\n")

        return (
            f"✅✅✅ TRANSFERÊNCIA EXECUTADA COM SUCESSO ✅✅✅\n\n"
            f"O atendimento foi transferido para um humano.\n"
            f"Motivo: {reason}\n\n"
            f"🔴 IMPORTANTE: VOCÊ NÃO DEVE MAIS RESPONDER NESTA CONVERSA!\n"
            f"🔴 O status da conversa foi alterado para 'human'.\n"
            f"🔴 Aguarde um atendente humano assumir o atendimento."
        )

    except Exception as e:
        traceback.print_exc()
        print("\n" + "="*80)
        print("❌❌❌ ERRO NA TRANSFERÊNCIA PARA HUMANO ❌❌❌")
        print("="*80)
        print(f"Erro: {str(e)}")
        print("="*80 + "\n")
        return f"❌ ERRO ao transferir para humano: {str(e)}"


@tool
def list_available_files(
    runtime: ToolRuntime,
) -> str:
    """Lista arquivos disponíveis para envio ao usuário.

    Esta ferramenta lista APENAS arquivos que podem ser ENVIADOS via WhatsApp.
    Não confunda com arquivos de contexto que já aparecem nas suas instruções.

    QUANDO USAR:
    - Usuário pergunta: "que arquivos você tem?" ou "tem algum material?"
    - Antes de enviar arquivo (para confirmar nome exato)
    - Quando não sabe qual arquivo enviar

    QUANDO NÃO USAR:
    - Informação já está no contexto (use-a diretamente)
    - Apenas para consultar informações (use contexto)

    Returns:
        str: Lista formatada de arquivos disponíveis com nomes e tipos

    Exemplo:
        Arquivos disponíveis:
        - Manual do Produto (PDF)
        - Catálogo 2024 (PDF)
    """
    try:
        conversation = runtime.context["conversation"]
        if not conversation:
            return "Erro: Conversa não encontrada no contexto."

        evolution_instance = conversation.evolution_instance
        if not evolution_instance:
            return "Erro: Nenhuma instância Evolution configurada."

        agent = evolution_instance.agent
        if not agent:
            return "Erro: Nenhum agente configurado."

        # Buscar arquivos enviaveis (sendable ou both)
        files = agent.files.filter(
            is_active=True,
            usage_type__in=['sendable', 'both']
        ).order_by('name')

        if not files.exists():
            return "Nenhum arquivo disponível no momento."

        # Formatar lista
        files_list = []
        for file_obj in files:
            file_type = file_obj.get_file_type_display()
            file_info = f"- {file_obj.name} ({file_type})"
            files_list.append(file_info)

        return "Arquivos disponíveis:\n" + "\n".join(files_list)

    except Exception as e:
        traceback.print_exc()
        return f"Erro ao listar arquivos: {str(e)}"


@tool
def send_file(
    file_name: str,
    runtime: ToolRuntime,
) -> str:
    """Envia arquivo específico para o usuário via WhatsApp.

    QUANDO USAR:
    - Usuário pede EXPLICITAMENTE arquivo
    - Após recomendar algo, ofereça material de apoio

    QUANDO NÃO USAR:
    - Informação está no contexto (responda diretamente)
    - Não sabe qual arquivo (use list_available_files primeiro)

    REGRAS:
    1. Use nome EXATO (confirme com list_available_files)
    2. Se há apenas 1 arquivo relacionado -> ENVIE (não pergunte)
    3. SEMPRE confirme após envio
    4. NÃO peça confirmação se usuário já pediu

    Args:
        file_name: Nome exato do arquivo (sem tipo entre parênteses)

    Returns:
        str: Mensagem de sucesso ou erro com detalhes

    Exemplos:
        send_file("Manual Geral") - correto
        send_file("manual") - nome não exato
        send_file("Manual (PDF)") - remova o tipo
    """
    try:
        import re
        from whatsapp_connector.services import EvolutionAPIService

        # Validar parâmetros
        if not file_name or not file_name.strip():
            return "Erro: Nome do arquivo não fornecido."

        # Extrair dados do contexto
        conversation = runtime.context["conversation"]
        if not conversation:
            return "Erro: Conversa não encontrada no contexto."

        contact = conversation.contact
        evolution_instance = conversation.evolution_instance

        if not contact:
            return "Erro: Contato não encontrado."

        if not evolution_instance:
            return "Erro: Nenhuma instância Evolution configurada."

        agent = evolution_instance.agent
        if not agent:
            return "Erro: Nenhum agente configurado."

        # Limpar nome (remover tipo entre parênteses)
        clean_name = re.sub(r'\s*\([^)]*\)\s*$', '', file_name).strip()

        # Buscar arquivo - primeiro exato, depois similar
        file_obj = agent.files.filter(
            name__iexact=clean_name,
            is_active=True,
            usage_type__in=['sendable', 'both']
        ).first()

        if not file_obj:
            file_obj = agent.files.filter(
                name__icontains=clean_name,
                is_active=True,
                usage_type__in=['sendable', 'both']
            ).first()

        if not file_obj:
            available_files = list(agent.files.filter(
                is_active=True,
                usage_type__in=['sendable', 'both']
            ).values_list('name', flat=True))

            files_list = ', '.join(available_files) if available_files else 'nenhum'
            return f"Erro: Arquivo '{file_name}' não encontrado. Disponíveis: {files_list}"

        # Verificar tamanho antes de enviar
        file_size_mb = file_obj.file.size / (1024 * 1024)
        if file_size_mb > 5:
            return f"Erro: Arquivo '{file_obj.name}' muito grande ({file_size_mb:.1f}MB). Limite: 5MB."

        # Enviar arquivo
        file_path = file_obj.file.path
        service = EvolutionAPIService(evolution_instance)
        response = service.send_file_message(
            to_number=contact.phone_number,
            file_url_or_path=file_path,
            caption=file_obj.name
        )

        if response:
            return f"Arquivo '{file_obj.name}' enviado com sucesso!"
        else:
            return f"Erro ao enviar arquivo '{file_obj.name}'."

    except Exception as e:
        traceback.print_exc()
        return f"Erro ao enviar arquivo: {str(e)}"


@tool
def search_documents(query: str, runtime: ToolRuntime) -> str:
    """
    Busca documentos relevantes na base de conhecimento.

    Use esta ferramenta SEMPRE que precisar buscar informações para responder
    perguntas do usuário. Busque nos documentos disponíveis antes de responder.

    Args:
        query: A consulta/pergunta para buscar nos documentos.

    Returns:
        Conteúdo dos documentos relevantes encontrados.
    """
    retriever = runtime.context["retriever"]

    if not retriever:
        return "Erro: Nenhum retriever configurado para busca de documentos."

    docs = retriever.invoke(query)

    if not docs:
        return "Nenhum documento relevante encontrado para esta consulta."

    return "\n\n---\n\n".join([d.page_content for d in docs])


def debug_tool_docstring(agent=None):
    """
    Função de debug para verificar a docstring completa da ferramenta.
    Use para validar se as regras estão sendo injetadas corretamente.
    """
    # Recarregar as tools para garantir que a docstring está atualizada
    get_agent_tools(agent)

    print("\n" + "="*80)
    print("🔍 DEBUG: Docstring da ferramenta request_human_intervention")
    print("="*80)
    print(request_human_intervention.__doc__)
    print("="*80 + "\n")


def get_agent_tools(agent=None):
    """
    Retorna a lista de tools disponíveis para o agente.

    Args:
        agent: Instância do Agent para carregar critérios de transferência humana

    Returns:
        Lista de tools LangChain.
    """
    # Buscar critérios de transferência humana do agente
    intervention_rules_text = "    ⚠️ Nenhum critério específico cadastrado."

    if agent and agent.human_handoff_criteria:
        # Formatar as regras com indentação e destaque
        rules = agent.human_handoff_criteria.strip()

        # Processar cada linha das regras
        formatted_lines = []
        for line in rules.split("\n"):
            line = line.strip()
            if line:
                # Se a linha já começa com -, manter
                # Senão, adicionar -
                if not line.startswith("-"):
                    line = f"- {line}"
                formatted_lines.append(f"    ❗ {line}")

        intervention_rules_text = "\n".join(formatted_lines)

    # Atualizar a docstring dinamicamente com as regras do agente
    # Isso permite que cada agente tenha critérios específicos de transferência
    original_doc = request_human_intervention.__doc__
    if original_doc and '{intervention_rules}' in original_doc:
        request_human_intervention.__doc__ = original_doc.format(
            intervention_rules=intervention_rules_text
        )

        # Log para debug - verificar se regras foram carregadas
        if agent and agent.human_handoff_criteria:
            print(f"\n🔔 Regras de intervenção carregadas para agente '{agent.display_name}':")
            for line in formatted_lines:
                print(line)
            print("")

    return [
        search_documents,
        list_available_files,
        send_file,
        request_human_intervention,
    ]