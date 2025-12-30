"""
Construção do Grafo LangGraph para Secretária Virtual

Este módulo define a máquina de estados determinística.

FLUXO:
START → guard → detect_intent → [roteamento por intenção] → send_response → END

ROTAS:
- HUMANO → transfer_human → END
- AGENDAR → validar_dados_agendamento → [condicional]
    ├─ COMPLETO → gerar_link → send_response → END
    └─ INCOMPLETO → solicitar_dados → send_response → END
- CONSULTAR → consultar → send_response → END
- CANCELAR → cancelar_listar → send_response → (aguarda ID) → cancelar_confirmar → send_response → END
- REAGENDAR → reagendar_listar → send_response → (aguarda ID) → reagendar_confirmar → send_response → END
- OUTRO → handle_conversation → send_response → END

IMPORTANTE:
- Não usar AgentExecutor genérico
- Fluxo determinístico com conversa livre
- LLM para classificação de intenção E conversação
- Validação de dados de agendamento com LLM
- Agendamento coleta tipo (particular/convênio) e nome completo
"""

from langgraph.graph import StateGraph, START, END
from .state import SecretaryState
from .nodes import (
    conversation_guard,
    detect_intent,
    transfer_to_human,
    validar_dados_agendamento,
    gerar_link,
    solicitar_dados,
    consultar,
    cancelar_listar,
    cancelar_confirmar,
    reagendar_listar,
    reagendar_confirmar,
    handle_conversation,
    send_response
)


def build_secretary_graph():
    """
    Constrói o grafo da secretária virtual.

    Returns:
        StateGraph compilado e pronto para execução
    """
    # Criar grafo com o tipo de estado
    graph = StateGraph(SecretaryState)

    # ===========================================================================
    # ADICIONAR NÓS
    # ===========================================================================

    graph.add_node("guard", conversation_guard)
    graph.add_node("detect_intent", detect_intent)
    graph.add_node("transfer_human", transfer_to_human)
    graph.add_node("validar_dados_agendamento", validar_dados_agendamento)
    graph.add_node("gerar_link", gerar_link)
    graph.add_node("solicitar_dados", solicitar_dados)
    graph.add_node("consultar", consultar)
    graph.add_node("cancelar_listar", cancelar_listar)
    graph.add_node("cancelar_confirmar", cancelar_confirmar)
    graph.add_node("reagendar_listar", reagendar_listar)
    graph.add_node("reagendar_confirmar", reagendar_confirmar)
    graph.add_node("handle_conversation", handle_conversation)
    graph.add_node("send_response", send_response)

    # ===========================================================================
    # DEFINIR FLUXO LINEAR
    # ===========================================================================

    # START sempre vai para guard
    graph.add_edge(START, "guard")

    # guard vai direto para detecção de intenção
    graph.add_edge("guard", "detect_intent")

    # ===========================================================================
    # ROTEAMENTO CONDICIONAL POR INTENÇÃO
    # ===========================================================================

    def route_by_intent(state: SecretaryState) -> str:
        """
        Roteia para o nó correto baseado na intenção detectada.

        Também verifica se estamos em um fluxo de continuação (step preenchido)
        para rotear para o nó de confirmação direto.

        Args:
            state: Estado com intent e step preenchidos

        Returns:
            str: Nome do próximo nó
        """
        intent = state.intent
        step = state.step

        # Fluxo de continuação: CANCELAR com step aguardando ID
        if intent == "CANCELAR" and step == "AGUARDANDO_ID_CANCELAR":
            next_node = "cancelar_confirmar"
            print(f"➡️  ROTEAMENTO: {next_node}")
            return next_node

        # Fluxo de continuação: REAGENDAR com step aguardando ID
        if intent == "REAGENDAR" and step == "AGUARDANDO_ID_REAGENDAR":
            next_node = "reagendar_confirmar"
            print(f"➡️  ROTEAMENTO: {next_node}")
            return next_node

        # Fluxos normais (primeira interação)
        if intent == "HUMANO":
            next_node = "transfer_human"
        elif intent == "AGENDAR":
            next_node = "validar_dados_agendamento"
        elif intent == "CONSULTAR":
            next_node = "consultar"
        elif intent == "CANCELAR":
            next_node = "cancelar_listar"
        elif intent == "REAGENDAR":
            next_node = "reagendar_listar"
        else:
            # OUTRO ou qualquer coisa não reconhecida
            next_node = "handle_conversation"

        print(f"➡️  ROTEAMENTO: {next_node}")
        return next_node if next_node != "handle_conversation" else "handle_other"

    # Adicionar roteamento condicional
    graph.add_conditional_edges(
        "detect_intent",
        route_by_intent,
        {
            "transfer_human": "transfer_human",
            "validar_dados_agendamento": "validar_dados_agendamento",
            "consultar": "consultar",
            "cancelar_listar": "cancelar_listar",
            "cancelar_confirmar": "cancelar_confirmar",  # Fluxo de continuação
            "reagendar_listar": "reagendar_listar",
            "reagendar_confirmar": "reagendar_confirmar",  # Fluxo de continuação
            "handle_other": "handle_conversation"  # Para OUTRO, conversa livre
        }
    )

    # ===========================================================================
    # ROTEAMENTO CONDICIONAL PARA VALIDAÇÃO DE DADOS
    # ===========================================================================

    def route_by_validation(state: SecretaryState) -> str:
        """
        Decide se gera link ou solicita dados baseado na validação.

        Args:
            state: Estado com step preenchido

        Returns:
            str: "gerar_link" ou "solicitar_dados"
        """
        if state.step == "COMPLETO":
            return "gerar_link"
        else:
            return "solicitar_dados"

    # Adicionar roteamento condicional após validação
    graph.add_conditional_edges(
        "validar_dados_agendamento",
        route_by_validation,
        {
            "gerar_link": "gerar_link",
            "solicitar_dados": "solicitar_dados"
        }
    )

    # ===========================================================================
    # FLUXOS DE SAÍDA
    # ===========================================================================

    # Após ações, enviar resposta e finalizar
    graph.add_edge("gerar_link", "send_response")
    graph.add_edge("solicitar_dados", "send_response")
    graph.add_edge("consultar", "send_response")
    graph.add_edge("cancelar_listar", "send_response")
    graph.add_edge("reagendar_listar", "send_response")

    # Confirmações de cancelamento/reagendamento vão direto para send_response
    graph.add_edge("cancelar_confirmar", "send_response")
    graph.add_edge("reagendar_confirmar", "send_response")

    # Conversa livre vai para send_response
    graph.add_edge("handle_conversation", "send_response")

    # send_response sempre finaliza
    graph.add_edge("send_response", END)

    # transfer_human é terminal (edge direta para END)
    graph.add_edge("transfer_human", END)

    # ===========================================================================
    # COMPILAR GRAFO
    # ===========================================================================

    compiled_graph = graph.compile()

    print("✅ Grafo da Secretária Virtual compilado com sucesso")

    return compiled_graph