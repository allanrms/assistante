def debug_langgraph_messages(messages: list, node_name: str = "NODE", show_system: bool = False):
    """
    Exibe mensagens retornadas por um agente LangGraph de forma limpa e organizada.

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

    # Filtrar mensagens de sistema se necessário
    filtered_messages = [
        msg for msg in messages
        if show_system or type(msg).__name__ != "SystemMessage"
    ]

    if not filtered_messages:
        print(f"\n⚠️ [{node_name}] Apenas mensagens de sistema encontradas (use show_system=True para exibir).\n")
        return

    # Cabeçalho
    print("\n" + "═" * 100)
    print(f"🔍 [{node_name}] 📜 {len(filtered_messages)} mensagens")
    print("═" * 100)

    # Processar e exibir mensagens
    for i, msg_obj in enumerate(filtered_messages, 1):
        msg_type = type(msg_obj).__name__
        style = MESSAGE_STYLES.get(msg_type, DEFAULT_STYLE)

        # Separador e identificador
        print(f"\n{style['color']}{'─' * 100}")
        print(f"{i:02d}. {style['prefix']}{RESET}")

        # Exibir tool_calls se existirem
        if hasattr(msg_obj, "tool_calls") and msg_obj.tool_calls:
            tool_names = [tc.get("name", "unknown") for tc in msg_obj.tool_calls]
            print(f"   ⚙️ Chamadas: {', '.join(tool_names)}")

        # Exibir conteúdo
        content = msg_obj.content if hasattr(msg_obj, "content") else str(msg_obj)
        if content and content.strip():
            print(f"\n{content.strip()}")

    print(f"\n{RESET}{'═' * 100}\n")


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