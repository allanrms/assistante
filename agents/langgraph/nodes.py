"""
Nós do grafo LangGraph para Secretária Virtual

Cada nó é uma função que recebe o estado e retorna atualizações.

PRINCÍPIOS:
- LangGraph controla o fluxo (não AgentExecutor)
- LLM apenas classifica intenção ou gera texto
- Ferramentas só chamadas por nós específicos
- Conversation.status é autoridade máxima
- Transferência humana é estado terminal
"""

from langgraph.graph import END
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from .state import SecretaryState
from .runtime import SecretaryRuntime
from .tools import (
    gerar_link_agendamento,
    consultar_agendamentos,
    cancelar_agendamento,
    reagendar_consulta,
    request_human_intervention
)
from agents.models import Agent, Conversation
from agents.patterns.factories.llm_factory import LLMFactory


# ==============================================================================
# NÓ 1: CONVERSATION GUARD
# ==============================================================================

def conversation_guard(state: SecretaryState):
    """
    Bloqueia respostas da IA se o atendimento for humano.

    Este é o primeiro nó executado. Marca no estado se pode continuar.

    Args:
        state: Estado atual do grafo

    Returns:
        dict: Estado com flag 'can_continue'
    """
    conversation = state.conversation

    # Print cabeçalho da mensagem
    print("\n" + "="*80)
    print(f"📨 NOVA MENSAGEM | Conversa #{conversation.id}")
    print(f"👤 USUÁRIO: {state.user_input}")
    print("="*80)

    if conversation.status != "ai":
        print(f"🛑 GUARD: Bloqueado (status: {conversation.status})")
        # Marca que não pode continuar
        return {"intent": "BLOCKED"}

    print(f"✅ GUARD: Liberado")
    return state


# ==============================================================================
# NÓ 3: DETECÇÃO DE INTENÇÃO
# ==============================================================================

def detect_intent(state: SecretaryState):
    """
    Detecta a intenção do usuário usando LLM com contexto do histórico.

    Intenções válidas:
    - AGENDAR: usuário quer criar novo agendamento
    - CONSULTAR: usuário quer ver agendamentos existentes
    - CANCELAR: usuário quer cancelar agendamento
    - REAGENDAR: usuário quer mudar data/hora de agendamento
    - HUMANO: usuário pede para falar com atendente
    - OUTRO: qualquer outra coisa

    Args:
        state: Estado atual do grafo

    Returns:
        dict: Atualização do estado com 'intent' preenchido
    """
    # Verificar se estamos em um fluxo de continuação (aguardando dados/ID)
    # Analisa se a PENÚLTIMA mensagem foi da IA pedindo algo e a ÚLTIMA foi do usuário respondendo
    chat_history = state.chat_history

    if len(chat_history) >= 2:
        # Pegar as duas últimas mensagens
        last_message = chat_history[-1] if chat_history else None
        second_last_message = chat_history[-2] if len(chat_history) >= 2 else None

        # Verificar se penúltima é AI e última é HUMAN (usuário respondeu)
        if (second_last_message and hasattr(second_last_message, 'type') and second_last_message.type == 'ai' and
            last_message and hasattr(last_message, 'type') and last_message.type == 'human'):

            ai_message = second_last_message.content

            # Se IA pediu ID para cancelar
            if "Informe o ID da consulta que deseja cancelar" in ai_message:
                print("🔄 Continuando fluxo de cancelamento (aguardando ID)")
                return {"intent": "CANCELAR", "step": "AGUARDANDO_ID_CANCELAR"}

            # Se IA pediu ID para reagendar
            if "Informe o ID da consulta que deseja reagendar" in ai_message:
                print("🔄 Continuando fluxo de reagendamento (aguardando ID)")
                return {"intent": "REAGENDAR", "step": "AGUARDANDO_ID_REAGENDAR"}

    # Usar agente do estado
    agent = state.agent

    llm = LLMFactory(agent).llm
    # Carregar prompt do sistema configurado no Agent model
    base_prompt = agent.build_prompt()

    # Construir contexto do histórico (últimas 3 interações)
    history_context = ""
    if chat_history:
        recent_history = chat_history[-6:]  # Últimas 3 interações (user + ai)
        history_lines = []
        for msg in recent_history:
            if hasattr(msg, 'type'):
                if msg.type == 'human':
                    history_lines.append(f"Usuário: {msg.content}")
                elif msg.type == 'ai':
                    history_lines.append(f"Assistente: {msg.content}")
        if history_lines:
            history_context = "\n\nHistórico recente:\n" + "\n".join(history_lines)

    # Incluir prompt do sistema se existir
    system_context = ""
    if base_prompt:
        system_context = f"\n\nContexto do sistema:\n{base_prompt}\n"

    # Prompt de classificação
    prompt = f"""{system_context}Classifique a intenção do usuário em UMA palavra:

AGENDAR - Usuário quer criar um novo agendamento
CONSULTAR - Usuário quer ver seus agendamentos
CANCELAR - Usuário quer cancelar um agendamento
REAGENDAR - Usuário quer mudar data/hora de agendamento
HUMANO - Usuário pede para falar com atendente humano
OUTRO - Qualquer outra coisa{history_context}

Mensagem atual do usuário:
{state.user_input}

Responda APENAS com uma das palavras acima, nada mais."""

    try:
        response = llm.invoke(prompt)
        intent = response.content.strip().upper()

        # Validar intenção
        valid_intents = ['AGENDAR', 'CONSULTAR', 'CANCELAR', 'REAGENDAR', 'HUMANO', 'OUTRO']
        if intent not in valid_intents:
            intent = 'OUTRO'

        print(f"🎯 INTENÇÃO: {intent}")
        return {"intent": intent}

    except Exception as e:
        print(f"❌ Erro ao detectar intenção: {e}")
        return {"intent": "OUTRO"}


# ==============================================================================
# NÓ 4: TRANSFERÊNCIA HUMANA (ESTADO TERMINAL)
# ==============================================================================

def transfer_to_human(state: SecretaryState):
    """
    Transfere atendimento para humano e ENCERRA o fluxo.

    Este é um estado terminal. O grafo tem uma edge direta deste nó para END.

    Args:
        state: Estado atual do grafo

    Returns:
        dict: Estado inalterado
    """
    runtime = SecretaryRuntime(state.conversation, state.channel, state.messages_sent)

    # Enviar mensagem de transferência
    runtime.send_message(
        "Vou transferir você para um atendente humano agora. "
        "Aguarde que alguém irá te responder em breve! 👤"
    )

    # Solicitar intervenção humana (altera status da conversa)
    request_human_intervention(
        reason="Usuário solicitou atendimento humano",
        runtime=runtime
    )

    print("🚨 Transferido para atendimento humano")

    # Print da resposta formatado
    print(f"\n💬 RESPOSTA:")
    print("─" * 80)
    print("Vou transferir você para um atendente humano agora. Aguarde que alguém irá te responder em breve! 👤")
    print("─" * 80 + "\n")

    # Retornar estado (edge para END está definida no grafo)
    return state


# ==============================================================================
# NÓ 5: VALIDAR DADOS DE AGENDAMENTO
# ==============================================================================

def validar_dados_agendamento(state: SecretaryState):
    """
    Valida se todos os dados necessários para agendamento foram fornecidos.

    Dados obrigatórios:
    - Tipo de atendimento (particular ou convênio)
    - Nome completo do paciente

    Args:
        state: Estado atual do grafo

    Returns:
        dict: Atualização com dados extraídos e status de validação
    """
    agent = state.agent
    llm = LLMFactory(agent).llm

    # Construir histórico
    history_messages = []
    for msg in state.chat_history:
        if hasattr(msg, 'type'):
            if msg.type == 'human':
                history_messages.append(f"Usuário: {msg.content}")
            elif msg.type == 'ai':
                history_messages.append(f"Assistente: {msg.content}")

    history_text = "\n".join(history_messages) if history_messages else ""

    # Prompt para extrair dados
    extraction_prompt = f"""Analise o histórico da conversa e a mensagem atual para extrair os dados de agendamento.

Histórico:
{history_text}

Mensagem atual: {state.user_input}

Extraia:
1. Tipo de atendimento: "particular" ou "convênio"
2. Nome completo do paciente
3. Nome do convênio (SOMENTE se tipo for convênio)

Responda APENAS em JSON:
{{"tipo": "particular/convênio/null", "nome_completo": "nome/null", "nome_convenio": "nome_do_convenio/null"}}"""

    try:
        response = llm.invoke(extraction_prompt)
        import json
        import re

        # Extrair JSON
        json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
        if json_match:
            dados = json.loads(json_match.group())
        else:
            dados = json.loads(response.content.strip())

        tipo = dados.get("tipo")
        nome_completo = dados.get("nome_completo")
        nome_convenio = dados.get("nome_convenio")

        # Verificar se é convênio Unimed
        if tipo and tipo.lower() in ["convênio", "convenio"]:
            # Verificar se menciona Unimed no histórico ou mensagem atual
            texto_completo = (history_text + "\n" + state.user_input).lower()
            if "unimed" in texto_completo:
                print(f"⚠️ Convênio Unimed detectado - retornando mensagem específica")
                mensagem_unimed = """Infelizmente o Dr. Daniel não atende pelo convênio da Unimed, mas ele poderia te atender em uma consulta particular e, caso precise fazer cirurgia, o Dr. Daniel consegue fazer pelo seu convênio, assim como, se precisar fazer algum exame, com o pedido do Dr. Daniel você consegue pedir autorização junto ao convênio.

Gostaria de agendar uma consulta particular?"""
                return {
                    "step": "INCOMPLETO",
                    "response": mensagem_unimed
                }

        # Validar se dados estão completos
        # Se for convênio, precisa do nome do convênio também
        if tipo and tipo.lower() in ["convênio", "convenio"]:
            dados_completos = (
                tipo and tipo != "null" and
                nome_completo and nome_completo != "null" and len(nome_completo) > 3 and
                nome_convenio and nome_convenio != "null" and len(nome_convenio) > 2
            )
        else:
            # Se for particular, não precisa de nome de convênio
            dados_completos = (
                tipo and tipo != "null" and tipo.lower() == "particular" and
                nome_completo and nome_completo != "null" and len(nome_completo) > 3
            )

        if dados_completos:
            if tipo and tipo.lower() in ["convênio", "convenio"]:
                print(f"✅ Dados completos - Tipo: {tipo}, Convênio: {nome_convenio}, Nome: {nome_completo}")
            else:
                print(f"✅ Dados completos - Tipo: {tipo}, Nome: {nome_completo}")
            return {
                "step": "COMPLETO",
                "response": json.dumps({"tipo": tipo, "nome_completo": nome_completo, "nome_convenio": nome_convenio})
            }
        else:
            if tipo and tipo.lower() in ["convênio", "convenio"]:
                print(f"⚠️ Dados incompletos - Tipo: {tipo}, Convênio: {nome_convenio}, Nome: {nome_completo}")
            else:
                print(f"⚠️ Dados incompletos - Tipo: {tipo}, Nome: {nome_completo}")
            return {
                "step": "INCOMPLETO",
                "response": json.dumps({"tipo": tipo, "nome_completo": nome_completo, "nome_convenio": nome_convenio})
            }

    except Exception as e:
        print(f"❌ Erro ao validar dados: {e}")
        return {"step": "INCOMPLETO", "response": "{}"}


# ==============================================================================
# NÓ 6: GERAR LINK DE AGENDAMENTO
# ==============================================================================

def gerar_link(state: SecretaryState):
    """
    Gera link de agendamento quando todos os dados estão completos.

    Args:
        state: Estado atual do grafo

    Returns:
        dict: Atualização com 'response' contendo o link
    """
    runtime = SecretaryRuntime(state.conversation, state.channel, state.messages_sent)

    # Extrair dados do response temporário
    try:
        import json
        dados = json.loads(state.response)
        tipo = dados.get("tipo", "")
        nome_completo = dados.get("nome_completo", "")
        nome_convenio = dados.get("nome_convenio", "")
    except:
        tipo = ""
        nome_completo = ""
        nome_convenio = ""

    # Gerar link
    link = gerar_link_agendamento(runtime)

    # Formatar resposta
    tipo_formatado = tipo.capitalize()

    # Se for convênio, incluir nome do convênio
    if tipo and tipo.lower() in ["convênio", "convenio"] and nome_convenio:
        response_text = f"""✅ Perfeito! Dados confirmados:

👤 **Paciente:** {nome_completo}
💳 **Tipo:** {tipo_formatado}
🏥 **Convênio:** {nome_convenio}

{link}"""
    else:
        response_text = f"""✅ Perfeito! Dados confirmados:

👤 **Paciente:** {nome_completo}
💳 **Tipo:** {tipo_formatado}

{link}"""

    print(f"📅 Link de agendamento gerado")

    return {"response": response_text}


# ==============================================================================
# NÓ 7: SOLICITAR DADOS FALTANTES
# ==============================================================================

def solicitar_dados(state: SecretaryState):
    """
    Solicita os dados faltantes para o agendamento de forma natural.

    Args:
        state: Estado atual do grafo

    Returns:
        dict: Atualização com 'response' solicitando dados
    """
    # Se a response já é uma mensagem completa (ex: mensagem Unimed), retornar diretamente
    if state.response and not state.response.startswith("{"):
        print(f"📋 Enviando mensagem pré-formatada")
        return {"response": state.response}

    agent = state.agent
    llm = LLMFactory(agent).llm
    base_prompt = agent.build_prompt()

    # Extrair dados parciais
    try:
        import json
        dados = json.loads(state.response)
        tipo = dados.get("tipo")
        tem_tipo = tipo and tipo != "null"
        tem_nome = dados.get("nome_completo") and dados.get("nome_completo") != "null"
        tem_convenio = dados.get("nome_convenio") and dados.get("nome_convenio") != "null"
    except:
        tipo = None
        tem_tipo = False
        tem_nome = False
        tem_convenio = False

    # Construir histórico
    history_messages = []
    for msg in state.chat_history:
        if hasattr(msg, 'type'):
            if msg.type == 'human':
                history_messages.append(f"Usuário: {msg.content}")
            elif msg.type == 'ai':
                history_messages.append(f"Assistente: {msg.content}")

    history_text = "\n".join(history_messages) if history_messages else ""

    # Verificar se é convênio e precisa do nome do convênio
    eh_convenio = tipo and tipo.lower() in ["convênio", "convenio"]

    # Prompt para solicitar dados de forma natural
    if eh_convenio:
        request_prompt = f"""{base_prompt}

---

Histórico:
{history_text}

Mensagem atual: {state.user_input}

---

O usuário quer agendar uma consulta pelo convênio. Você precisa coletar:
- Tipo de atendimento: {"✓ JÁ TEM (Convênio)" if tem_tipo else "✗ FALTANDO"}
- Nome do convênio: {"✓ JÁ TEM" if tem_convenio else "✗ FALTANDO"}
- Nome completo: {"✓ JÁ TEM" if tem_nome else "✗ FALTANDO"}

Peça de forma NATURAL e AMIGÁVEL apenas os dados que estão faltando.
Seja breve (máximo 2-3 linhas)."""
    else:
        request_prompt = f"""{base_prompt}

---

Histórico:
{history_text}

Mensagem atual: {state.user_input}

---

O usuário quer agendar uma consulta. Você precisa coletar:
- Tipo de atendimento: {"✓ JÁ TEM" if tem_tipo else "✗ FALTANDO"}
- Nome completo: {"✓ JÁ TEM" if tem_nome else "✗ FALTANDO"}

Peça de forma NATURAL e AMIGÁVEL apenas os dados que estão faltando.
Seja breve (máximo 2-3 linhas)."""

    try:
        response = llm.invoke(request_prompt)
        response_text = response.content.strip()
        print(f"📋 Solicitando dados faltantes")
        return {"response": response_text}

    except Exception as e:
        print(f"❌ Erro ao solicitar dados: {e}")
        # Fallback
        response_text = """Para realizar seu agendamento, preciso de:

📋 Tipo de atendimento (Particular ou Convênio) e Nome completo"""
        return {"response": response_text}


# ==============================================================================
# NÓ 6: CONSULTA DE AGENDAMENTOS
# ==============================================================================

def consultar(state: SecretaryState):
    """
    Lista os agendamentos do contato.

    Args:
        state: Estado atual do grafo

    Returns:
        dict: Atualização com 'response' contendo a lista
    """
    runtime = SecretaryRuntime(state.conversation, state.channel, state.messages_sent)

    response_text = consultar_agendamentos(runtime)

    print(f"📋 Agendamentos consultados")

    return {"response": response_text}


# ==============================================================================
# NÓ 7: CANCELAMENTO (ETAPA 1 - LISTAR)
# ==============================================================================

def cancelar_listar(state: SecretaryState):
    """
    Lista agendamentos e solicita ID para cancelar.

    Este é o primeiro passo do fluxo de cancelamento.
    Atualiza 'step' para AGUARDANDO_ID_CANCELAR.

    Args:
        state: Estado atual do grafo

    Returns:
        dict: Atualização com 'response' e 'step'
    """
    runtime = SecretaryRuntime(state.conversation, state.channel, state.messages_sent)

    # Consultar agendamentos
    result = consultar_agendamentos(runtime)

    # Verificar se há agendamentos (detectar se a mensagem indica ausência)
    if "não possui agendamentos" in result.lower() or "nenhum agendamento" in result.lower():
        # Não há agendamentos, apenas retornar a mensagem
        print(f"⚠️ Sem agendamentos para cancelar")
        return {"response": result}

    # Há agendamentos, adicionar instrução para solicitar ID
    response_text = result + "\n\n❓ Informe o ID da consulta que deseja cancelar."

    print(f"🗑️ Aguardando ID para cancelamento")

    return {
        "response": response_text,
        "step": "AGUARDANDO_ID_CANCELAR"
    }


# ==============================================================================
# NÓ 8: CANCELAMENTO (ETAPA 2 - CONFIRMAR)
# ==============================================================================

def cancelar_confirmar(state: SecretaryState):
    """
    Confirma o cancelamento do agendamento.

    Este nó é executado quando o usuário fornece o ID.

    Args:
        state: Estado atual do grafo

    Returns:
        dict: Atualização com 'response' da confirmação
    """
    runtime = SecretaryRuntime(state.conversation, state.channel, state.messages_sent)

    try:
        # Extrair ID do input do usuário
        appointment_id = int(state.user_input.strip())

        response_text = cancelar_agendamento(appointment_id, runtime)

        print(f"✅ Agendamento {appointment_id} cancelado")

        return {"response": response_text}

    except ValueError:
        return {
            "response": "❌ Por favor, informe apenas o número do ID do agendamento."
        }


# ==============================================================================
# NÓ 9: REAGENDAMENTO (ETAPA 1 - LISTAR)
# ==============================================================================

def reagendar_listar(state: SecretaryState):
    """
    Lista agendamentos e solicita ID para reagendar.

    Este é o primeiro passo do fluxo de reagendamento.
    Atualiza 'step' para AGUARDANDO_ID_REAGENDAR.

    Args:
        state: Estado atual do grafo

    Returns:
        dict: Atualização com 'response' e 'step'
    """
    runtime = SecretaryRuntime(state.conversation, state.channel, state.messages_sent)

    # Consultar agendamentos
    result = consultar_agendamentos(runtime)

    # Verificar se há agendamentos (detectar se a mensagem indica ausência)
    if "não possui agendamentos" in result.lower() or "nenhum agendamento" in result.lower():
        # Não há agendamentos, apenas retornar a mensagem
        print(f"⚠️ Sem agendamentos para reagendar")
        return {"response": result}

    # Há agendamentos, adicionar instrução para solicitar ID
    response_text = result + "\n\n❓ Informe o ID da consulta que deseja reagendar."

    print(f"📅 Aguardando ID para reagendamento")

    return {
        "response": response_text,
        "step": "AGUARDANDO_ID_REAGENDAR"
    }


# ==============================================================================
# NÓ 10: REAGENDAMENTO (ETAPA 2 - CONFIRMAR)
# ==============================================================================

def reagendar_confirmar(state: SecretaryState):
    """
    Confirma o reagendamento e gera novo link.

    Este nó é executado quando o usuário fornece o ID.

    Args:
        state: Estado atual do grafo

    Returns:
        dict: Atualização com 'response' contendo novo link
    """
    runtime = SecretaryRuntime(state.conversation, state.channel, state.messages_sent)

    try:
        # Extrair ID do input do usuário
        appointment_id = int(state.user_input.strip())

        response_text = reagendar_consulta(appointment_id, runtime)

        print(f"🔄 Agendamento {appointment_id} reagendado")

        return {"response": response_text}

    except ValueError:
        return {
            "response": "❌ Por favor, informe apenas o número do ID do agendamento."
        }


# ==============================================================================
# NÓ 11: CONVERSA LIVRE
# ==============================================================================

def handle_conversation(state: SecretaryState):
    """
    Gera resposta conversacional livre usando LLM.

    Este nó é executado quando a intenção é "OUTRO" ou quando o usuário
    está apenas conversando sem uma intenção específica de ação.

    Args:
        state: Estado atual do grafo

    Returns:
        dict: Atualização com 'response' contendo a mensagem gerada
    """
    agent = state.agent
    llm = LLMFactory(agent).llm
    base_prompt = agent.build_prompt()

    # Construir histórico de conversa
    history_messages = []
    for msg in state.chat_history:
        if hasattr(msg, 'type'):
            if msg.type == 'human':
                history_messages.append(f"Usuário: {msg.content}")
            elif msg.type == 'ai':
                history_messages.append(f"Assistente: {msg.content}")

    history_text = "\n".join(history_messages) if history_messages else ""

    # Construir prompt completo
    if history_text:
        prompt = f"""{base_prompt}

---

## Histórico da Conversa

{history_text}

---

## Mensagem Atual do Usuário

{state.user_input}

---

Responda à mensagem do usuário de forma natural e amigável."""
    else:
        # Primeira mensagem (sem histórico)
        prompt = f"""{base_prompt}

---

## Mensagem do Usuário

{state.user_input}

---

Responda à mensagem do usuário de forma natural e amigável."""

    # Gerar resposta
    response = llm.invoke(prompt)
    response_text = response.content.strip()

    print(f"💬 Resposta conversacional gerada")

    return {"response": response_text}


# ==============================================================================
# NÓ 12: ENVIAR RESPOSTA
# ==============================================================================

def send_response(state: SecretaryState):
    """
    Envia a resposta final ao usuário.

    Este nó é executado ao final de cada fluxo para enviar
    a mensagem que foi preparada no campo 'response'.

    Args:
        state: Estado atual do grafo

    Returns:
        dict: Estado inalterado (final do fluxo)
    """
    runtime = SecretaryRuntime(state.conversation, state.channel, state.messages_sent)

    if state.response:
        runtime.send_message(state.response)

        # Print da resposta formatado
        print(f"\n💬 RESPOSTA:")
        print("─" * 80)
        print(state.response)
        print("─" * 80 + "\n")

    return state