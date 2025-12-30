"""
Ferramentas disponíveis para conversação livre no LangGraph.

Estas ferramentas podem ser chamadas pelo LLM durante handle_conversation.
"""
from langchain.tools import tool


@tool
def request_human_intervention_tool(reason: str, runtime) -> str:
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

    Se o usuário mencionar ou solicitar QUALQUER item dos critérios configurados:

    🔴 VOCÊ DEVE EXECUTAR ESTAS 2 AÇÕES NA MESMA RESPOSTA:
    1️⃣ Informar ao usuário: "Vou transferir você para um atendente humano"
    2️⃣ CHAMAR IMEDIATAMENTE esta ferramenta: request_human_intervention_tool(reason="...")

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

    Args:
        reason: Motivo da transferência (ex: "usuário solicitou atendente", "solicitação de atestado")
        runtime: Objeto runtime com informações da conversa

    Returns:
        str: Mensagem de confirmação da transferência
    """
    from .tools import request_human_intervention

    # Chamar a função real de transferência
    result = request_human_intervention(reason=reason, runtime=runtime)

    if result:
        return (
            f"✅✅✅ TRANSFERÊNCIA EXECUTADA COM SUCESSO ✅✅✅\n\n"
            f"O atendimento foi transferido para um humano.\n"
            f"Motivo: {reason}\n\n"
            f"🔴 IMPORTANTE: VOCÊ NÃO DEVE MAIS RESPONDER NESTA CONVERSA!\n"
            f"🔴 O status da conversa foi alterado para 'human'.\n"
            f"🔴 Aguarde um atendente humano assumir o atendimento."
        )
    else:
        return f"❌ ERRO ao transferir para humano. Tente novamente."


def get_conversation_tools(agent=None):
    """
    Retorna a lista de tools disponíveis para conversação.

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
    original_doc = request_human_intervention_tool.__doc__
    if original_doc and '{intervention_rules}' in original_doc:
        request_human_intervention_tool.__doc__ = original_doc.format(
            intervention_rules=intervention_rules_text
        )

        # Log para debug - verificar se regras foram carregadas
        if agent and agent.human_handoff_criteria:
            print(f"\n🔔 Regras de intervenção carregadas para agente '{agent.display_name}':")
            for line in formatted_lines:
                print(line)
            print("")

    return [
        request_human_intervention_tool,
    ]