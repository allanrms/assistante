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
    runtime: ToolRuntime,
) -> str:
    """
    Solicita intervenção humana e encerra o atendimento do agente.

    QUANDO USAR:
    - Quando o usuário pedir explicitamente para falar com um atendente, humano ou pessoa real.
    - Se o usuário estiver muito frustrado e o agente não conseguir ajudar.
    - Se o usuário disser "quero falar com um humano" ou algo similar.
    - Emissão de nota fiscal
    - Dúvida quanto a medicação
    - Envio/Pedido do resultado do exame
    - Solicitação de relatório
    - Solicitação de atestado
    - Solicitação de receita médica
    - Informações sobre cirurgia

    QUANDO NÃO USAR:
    - Para resolver problemas que o agente pode resolver.
    - Como uma forma de encerrar a conversa sem um motivo claro.

    REGRAS:
    1. Use esta ferramenta APENAS quando o usuário solicitar explicitamente.
    2. A conversa será marcada como "atendimento humano" e o agente não responderá mais.
    3. O agente deve informar ao usuário que um humano entrará em contato em breve.

    Returns:
        str: Mensagem de confirmação ou erro.
    """
    try:
        conversation = runtime.context["conversation"]
        if not conversation:
            return "Erro: Conversa não encontrada no contexto."

        conversation.status = 'human'
        conversation.save()

        return "Atendimento transferido para um humano. O agente não deve mais responder."

    except Exception as e:
        traceback.print_exc()
        return f"Erro ao solicitar intervenção humana: {str(e)}"


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


def get_agent_tools():
    """
    Retorna a lista de tools disponíveis para o agente.

    Returns:
        Lista de tools LangChain.
    """
    return [
        search_documents,
        list_available_files,
        send_file,
        request_human_intervention,
    ]