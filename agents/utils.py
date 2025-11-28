import re
from typing import Any
from langchain_core.messages import AIMessage


def extract_ai_message_content(message: AIMessage) -> str:
    """
    Extrai conteúdo de uma AIMessage de forma simples e direta.

    Centraliza a lógica de extração que estava duplicada em múltiplos lugares.
    Seguindo o princípio "Start simple" do LangChain.

    Args:
        message: AIMessage do LangChain

    Returns:
        String com o conteúdo extraído
    """
    content = message.content

    # Se for None ou vazio, retornar placeholder
    if not content:
        return "[Resposta vazia]"

    # Se for lista, extrair partes de texto
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'text':
                # Extrair apenas o campo 'text', ignorando 'extras' e outros campos
                text_parts.append(item.get('text', ''))
            elif isinstance(item, str):
                text_parts.append(item)
            else:
                # Fallback para converter para string
                text_parts.append(str(item))
        return '\n'.join(text_parts) if text_parts else "[Resposta vazia]"

    # Se for string, retornar diretamente
    return str(content)


def remove_markdown_formatting(text: str) -> str:
    """Remove formatação markdown do texto."""
    # Remover negrito (**texto** ou __texto__)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)

    # Remover itálico (*texto* ou _texto_)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)

    # Remover marcadores de lista (*, -, +)
    text = re.sub(r'^\s*[\*\-\+]\s+', '', text, flags=re.MULTILINE)

    # Remover títulos (# Título)
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)

    return text


def debug_langgraph_messages(messages: list, node_name: str = "NODE", show_system: bool = False):
    """
    Exibe apenas a última interação (mensagem recebida e resposta) de forma limpa.

    Args:
        messages: Lista de mensagens do LangGraph
        node_name: Nome do nó para identificação no debug
        show_system: Se True, exibe mensagens de sistema (padrão: False)
    """
    if not messages:
        print(f"\n⚠️ [{node_name}] Nenhuma mensagem encontrada.\n")
        return

    # Configuração de cores por tipo de mensagem
    MESSAGE_STYLES = {
        "SystemMessage": {"prefix": "🧩 SYSTEM", "color": "\033[95m"},
        "HumanMessage": {"prefix": "🙋 HUMAN", "color": "\033[94m"},
        "AIMessage": {"prefix": "🤖 AI", "color": "\033[92m"},
        "ToolMessage": {"prefix": "🛠️ TOOL", "color": "\033[93m"},
    }
    DEFAULT_STYLE = {"prefix": "📦 OTHER", "color": "\033[90m"}
    RESET = "\033[0m"

    # Buscar última HumanMessage e última AIMessage
    last_human = None
    last_ai = None
    tool_messages = []

    for msg in reversed(messages):
        msg_type = type(msg).__name__

        if msg_type == "AIMessage" and last_ai is None:
            last_ai = msg
        elif msg_type == "HumanMessage" and last_human is None:
            last_human = msg
        elif msg_type == "ToolMessage":
            tool_messages.insert(0, msg)

        # Para quando encontrar ambas
        if last_human and last_ai:
            break

    # Cabeçalho
    print("\n" + "═" * 100)
    print(f"🔍 [{node_name}] Última interação")
    print("═" * 100)

    # Mostrar última mensagem do usuário
    if last_human:
        style = MESSAGE_STYLES["HumanMessage"]
        print(f"{style['color']}{'─' * 100}")
        print(f"{style['prefix']}{RESET}")
        content = last_human.content if hasattr(last_human, "content") else str(last_human)
        if content and content.strip():
            print(content.strip())

    # Mostrar tools usadas se houver
    if tool_messages:
        print(f"{MESSAGE_STYLES['ToolMessage']['color']}{'─' * 100}")
        print(f"🛠️ TOOLS EXECUTADAS ({len(tool_messages)}){RESET}")
        for tool_msg in tool_messages:
            print(f"   → {tool_msg.content[:100]}..." if len(tool_msg.content) > 100 else f"   → {tool_msg.content}")

    # Mostrar última resposta da IA
    if last_ai:
        style = MESSAGE_STYLES["AIMessage"]
        print(f"{style['color']}{'─' * 100}")
        print(f"{style['prefix']}{RESET}")

        # Mostrar tool_calls se existirem
        if hasattr(last_ai, "tool_calls") and last_ai.tool_calls:
            tool_names = [tc.get("name", "unknown") for tc in last_ai.tool_calls]
            print(f"   ⚙️ Chamando tools: {', '.join(tool_names)}")

        # Exibir conteúdo
        content = last_ai.content if hasattr(last_ai, "content") else str(last_ai)
        if content and content.strip():
            print(content.strip())

    print(f"{RESET}{'═' * 100}\n")


def validate_agenda_request(message: str) -> tuple[bool, str | None]:
    """
    Valida se uma mensagem contém um [AGENDA_REQUEST] válido.

    Returns:
        (is_valid, extracted_request)
    """
    if "[AGENDA_REQUEST]" not in message:
        return False, None

    try:
        # Extrair a requisição (tudo depois de [AGENDA_REQUEST])
        request = message.split("[AGENDA_REQUEST]")[1].strip()

        if not request or len(request) < 5:
            print("⚠️ [VALIDATION] [AGENDA_REQUEST] encontrado mas sem conteúdo válido")
            return False, None

        print(f"✅ [VALIDATION] [AGENDA_REQUEST] válido extraído: {request[:100]}...")
        return True, request
    except Exception as e:
        print(f"❌ [VALIDATION] Erro ao validar [AGENDA_REQUEST]: {e}")
        return False, None


def validate_agenda_response(message: str) -> tuple[bool, str]:
    """
    Valida se uma mensagem contém um [AGENDA_RESPONSE] válido.

    Returns:
        (is_valid, extracted_response)
    """
    if "[AGENDA_RESPONSE]" not in message:
        return False, message

    try:
        # Extrair a resposta (tudo depois de [AGENDA_RESPONSE])
        response = message.split("[AGENDA_RESPONSE]")[1].strip()

        if not response:
            print("⚠️ [VALIDATION] [AGENDA_RESPONSE] encontrado mas vazio")
            return False, message

        print(f"✅ [VALIDATION] [AGENDA_RESPONSE] válido extraído: {response[:100]}...")
        return True, response
    except Exception as e:
        print(f"❌ [VALIDATION] Erro ao validar [AGENDA_RESPONSE]: {e}")
        return False, message