# agents/utils/llm_cost_calculator.py
"""
Calculadora de custos de LLM.

Preços atualizados em: Janeiro 2025
Fonte: Páginas de pricing oficiais dos providers
"""

from decimal import Decimal
from typing import Dict, Optional
import time


# Preços por 1M de tokens (USD)
# Fonte: https://openai.com/api/pricing/ | https://www.anthropic.com/pricing | https://ai.google.dev/gemini-api/docs/pricing
# Atualizado: Janeiro 2025
LLM_PRICING = {
    # OpenAI
    "gpt-4o": {
        "input": Decimal("2.50"),  # $2.50 / 1M tokens
        "output": Decimal("10.00"),  # $10.00 / 1M tokens
    },
    "gpt-4o-mini": {
        "input": Decimal("0.15"),  # $0.15 / 1M tokens
        "output": Decimal("0.60"),  # $0.60 / 1M tokens
    },
    "gpt-4-turbo": {
        "input": Decimal("10.00"),
        "output": Decimal("30.00"),
    },
    "gpt-3.5-turbo": {
        "input": Decimal("0.50"),
        "output": Decimal("1.50"),
    },
    "o1": {
        "input": Decimal("15.00"),  # $15.00 / 1M tokens
        "output": Decimal("60.00"),  # $60.00 / 1M tokens
    },
    "o1-mini": {
        "input": Decimal("3.00"),  # $3.00 / 1M tokens
        "output": Decimal("12.00"),  # $12.00 / 1M tokens
    },

    # Anthropic Claude
    "claude-3-5-sonnet-20241022": {
        "input": Decimal("3.00"),  # $3.00 / 1M tokens
        "output": Decimal("15.00"),  # $15.00 / 1M tokens
        "cache_write": Decimal("3.75"),  # $3.75 / 1M tokens (criar cache)
        "cache_read": Decimal("0.30"),  # $0.30 / 1M tokens (ler cache - 90% desconto!)
    },
    "claude-3-5-haiku-20241022": {
        "input": Decimal("0.80"),
        "output": Decimal("4.00"),
        "cache_write": Decimal("1.00"),
        "cache_read": Decimal("0.08"),
    },
    "claude-3-haiku-20240307": {
        "input": Decimal("0.25"),
        "output": Decimal("1.25"),
        "cache_write": Decimal("0.30"),
        "cache_read": Decimal("0.03"),
    },
    "claude-3-opus-20240229": {
        "input": Decimal("15.00"),
        "output": Decimal("75.00"),
        "cache_write": Decimal("18.75"),
        "cache_read": Decimal("1.50"),
    },

    # Google Gemini (Fonte: https://ai.google.dev/gemini-api/docs/pricing)
    "gemini-2.5-pro": {
        "input": Decimal("1.25"),  # $1.25 / 1M tokens (≤200k), $2.50 (>200k)
        "output": Decimal("10.00"),  # $10.00 / 1M tokens (≤200k), $15.00 (>200k)
    },
    "gemini-2.5-flash": {
        "input": Decimal("0.30"),  # $0.30 / 1M tokens (text/image/video)
        "output": Decimal("2.50"),  # $2.50 / 1M tokens
    },
    "gemini-2.5-flash-lite": {
        "input": Decimal("0.10"),  # $0.10 / 1M tokens
        "output": Decimal("0.40"),  # $0.40 / 1M tokens
    },
    "gemini-2.0-flash": {
        "input": Decimal("0.10"),  # $0.10 / 1M tokens (text/image/video)
        "output": Decimal("0.40"),  # $0.40 / 1M tokens
    },
    "gemini-2.0-flash-exp": {
        "input": Decimal("0.00"),  # Grátis durante preview
        "output": Decimal("0.00"),
    },
    "gemini-1.5-pro": {
        "input": Decimal("1.25"),  # $1.25 / 1M tokens
        "output": Decimal("5.00"),  # $5.00 / 1M tokens (legacy)
    },
    "gemini-1.5-flash": {
        "input": Decimal("0.075"),
        "output": Decimal("0.30"),
    },
}


def calculate_llm_cost(
    provider: str,
    model_name: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> Dict[str, Decimal]:
    """
    Calcula o custo de uma chamada à LLM.

    Args:
        provider: Nome do provider (openai, anthropic, google)
        model_name: Nome do modelo
        input_tokens: Tokens de entrada
        output_tokens: Tokens de saída
        cache_creation_tokens: Tokens usados para criar cache (Anthropic)
        cache_read_tokens: Tokens lidos do cache (Anthropic)

    Returns:
        Dict com custos detalhados:
        {
            "input_cost": Decimal,
            "output_cost": Decimal,
            "cache_creation_cost": Decimal,
            "cache_read_cost": Decimal,
            "total_cost": Decimal
        }
    """

    # Buscar pricing do modelo
    pricing = LLM_PRICING.get(model_name)

    if not pricing:
        # Modelo desconhecido - usar valores médios do provider
        print(f"⚠️ Modelo {model_name} não encontrado na tabela de preços. Usando valores padrão.")

        if provider == "anthropic":
            pricing = LLM_PRICING["claude-3-5-sonnet-20241022"]
        elif provider == "google":
            pricing = LLM_PRICING["gemini-2.5-pro"]
        else:  # openai
            pricing = LLM_PRICING["gpt-4o"]

    # Calcular custos (preços são por 1M tokens)
    input_cost = (Decimal(input_tokens) / Decimal(1_000_000)) * pricing["input"]
    output_cost = (Decimal(output_tokens) / Decimal(1_000_000)) * pricing["output"]

    # Cache (apenas Anthropic)
    cache_creation_cost = Decimal(0)
    cache_read_cost = Decimal(0)

    if "cache_write" in pricing and cache_creation_tokens > 0:
        cache_creation_cost = (Decimal(cache_creation_tokens) / Decimal(1_000_000)) * pricing["cache_write"]

    if "cache_read" in pricing and cache_read_tokens > 0:
        cache_read_cost = (Decimal(cache_read_tokens) / Decimal(1_000_000)) * pricing["cache_read"]

    total_cost = input_cost + output_cost + cache_creation_cost + cache_read_cost

    return {
        "input_cost": input_cost,
        "output_cost": output_cost,
        "cache_creation_cost": cache_creation_cost,
        "cache_read_cost": cache_read_cost,
        "total_cost": total_cost,
    }


def track_llm_usage(
    conversation,
    agent,
    provider: str,
    model_name: str,
    result,
    additional_context: str = "",
    start_time: Optional[float] = None,
) -> Optional['LLMUsage']:
    """
    Rastreia o uso de LLM e salva no banco.

    Args:
        conversation: Objeto Conversation
        agent: Objeto Agent
        provider: Nome do provider
        model_name: Nome do modelo
        result: Resultado do agent.invoke()
        additional_context: Contexto adicional usado
        start_time: Timestamp do início da chamada (para calcular tempo)

    Returns:
        LLMUsage object ou None se houver erro
    """
    from agents.models import LLMUsage

    try:
        # Tentar extrair usage_metadata de diferentes locais
        usage_metadata = None
        input_tokens = 0
        output_tokens = 0
        cache_creation_tokens = 0
        cache_read_tokens = 0

        # 1. Tentar no nível raiz do resultado
        if "usage_metadata" in result:
            usage_metadata = result["usage_metadata"]

        # 2. Tentar extrair das mensagens AI
        if not usage_metadata:
            from langchain_core.messages import AIMessage

            ai_message_count = 0
            for msg in result.get("messages", []):
                if isinstance(msg, AIMessage):
                    ai_message_count += 1

                    # Debug: mostrar estrutura da mensagem (apenas última mensagem para não poluir)
                    is_last = ai_message_count == len([m for m in result.get("messages", []) if isinstance(m, AIMessage)])

                    if is_last:
                        print(f"🔍 AIMessage #{ai_message_count} (última):")
                        print(f"   - Tipo: {type(msg)}")
                        print(f"   - Tem response_metadata? {hasattr(msg, 'response_metadata')}")
                        print(f"   - Tem usage_metadata? {hasattr(msg, 'usage_metadata')}")

                    # Verificar usage_metadata como atributo direto (Google Gemini)
                    if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                        usage = msg.usage_metadata
                        if is_last:
                            print(f"   - Formato: Atributo direto usage_metadata")
                            print(f"   - Usage: {usage}")

                        # Google/Gemini format no atributo direto
                        if hasattr(usage, 'get'):
                            input_tokens += usage.get("input_tokens", 0)
                            output_tokens += usage.get("output_tokens", 0)
                        elif hasattr(usage, '__dict__'):
                            # Se for um objeto, converter para dict
                            usage_dict = usage.__dict__ if hasattr(usage, '__dict__') else {}
                            input_tokens += usage_dict.get("input_tokens", 0)
                            output_tokens += usage_dict.get("output_tokens", 0)

                    if hasattr(msg, "response_metadata") and msg.response_metadata:
                        response_meta = msg.response_metadata
                        print(f"   - Chaves em response_metadata: {list(response_meta.keys())}")

                        # Se for a última mensagem, mostrar conteúdo completo
                        if ai_message_count == len([m for m in result.get("messages", []) if isinstance(m, AIMessage)]):
                            print(f"   - Conteúdo completo do response_metadata:")
                            import json
                            print(json.dumps(response_meta, indent=2, default=str))

                        # Verificar outros atributos da mensagem
                        print(f"   - Atributos da mensagem: {[attr for attr in dir(msg) if not attr.startswith('_')]}")

                        # Anthropic format
                        if "usage" in response_meta:
                            usage = response_meta["usage"]
                            print(f"   - Formato: Anthropic")
                            print(f"   - Usage: {usage}")
                            input_tokens += usage.get("input_tokens", 0)
                            output_tokens += usage.get("output_tokens", 0)
                            cache_creation_tokens += usage.get("cache_creation_input_tokens", 0)
                            cache_read_tokens += usage.get("cache_read_input_tokens", 0)

                        # OpenAI format
                        elif "token_usage" in response_meta:
                            usage = response_meta["token_usage"]
                            print(f"   - Formato: OpenAI")
                            print(f"   - Usage: {usage}")
                            input_tokens += usage.get("prompt_tokens", 0)
                            output_tokens += usage.get("completion_tokens", 0)

                        # Google/Gemini format
                        elif "usage_metadata" in response_meta:
                            usage = response_meta["usage_metadata"]
                            print(f"   - Formato: Google Gemini")
                            print(f"   - Usage: {usage}")
                            input_tokens += usage.get("prompt_token_count", 0)
                            output_tokens += usage.get("candidates_token_count", 0)

                        else:
                            print(f"   - ⚠️ Formato de usage desconhecido")
                    else:
                        print(f"   - ⚠️ Sem response_metadata")

        # 3. Se encontrou usage_metadata no nível raiz, usar ele
        if usage_metadata:
            input_tokens = usage_metadata.get("input_tokens", 0)
            output_tokens = usage_metadata.get("output_tokens", 0)
            cache_creation_tokens = usage_metadata.get("cache_creation_input_tokens", 0)
            cache_read_tokens = usage_metadata.get("cache_read_input_tokens", 0)

        # Se não encontrou nenhum token, retornar None
        if input_tokens == 0 and output_tokens == 0:
            print("⚠️ Nenhuma informação de uso encontrada na resposta")
            print(f"Debug - Chaves disponíveis no resultado: {list(result.keys())}")
            return None

        # Calcular custos
        costs = calculate_llm_cost(
            provider=provider,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_tokens=cache_creation_tokens,
            cache_read_tokens=cache_read_tokens,
        )

        # Calcular tempo de resposta
        response_time_ms = None
        if start_time:
            response_time_ms = int((time.time() - start_time) * 1000)

        # Extrair ferramentas usadas
        tools_used = []
        for msg in result.get("messages", []):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_name = tool_call.get("name")
                    if tool_name and tool_name not in tools_used:
                        tools_used.append(tool_name)

        # Criar registro
        llm_usage = LLMUsage.objects.create(
            conversation=conversation,
            agent=agent,
            provider=provider,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_tokens=cache_creation_tokens,
            cache_read_tokens=cache_read_tokens,
            input_cost=costs["input_cost"],
            output_cost=costs["output_cost"],
            cache_creation_cost=costs["cache_creation_cost"],
            cache_read_cost=costs["cache_read_cost"],
            total_cost=costs["total_cost"],
            response_time_ms=response_time_ms,
            context_size=len(additional_context),
            tools_used=tools_used,
        )

        # Log estruturado
        print("\n" + "="*80)
        print(f"💰 CUSTO DA CHAMADA LLM")
        print(f"🤖 Modelo: {provider}/{model_name}")
        print(f"📊 Tokens: {input_tokens:,} entrada + {output_tokens:,} saída = {input_tokens + output_tokens:,} total")

        if cache_creation_tokens > 0:
            print(f"💾 Cache criado: {cache_creation_tokens:,} tokens (${costs['cache_creation_cost']:.6f})")
        if cache_read_tokens > 0:
            saving = costs["cache_creation_cost"] - costs["cache_read_cost"]
            print(f"⚡ Cache lido: {cache_read_tokens:,} tokens (${costs['cache_read_cost']:.6f}) - Economia: ${saving:.6f}")

        print(f"💵 Custo total: ${costs['total_cost']:.6f} USD")

        if response_time_ms:
            print(f"⏱️  Tempo: {response_time_ms}ms")

        if tools_used:
            print(f"🔧 Ferramentas: {', '.join(tools_used)}")

        print("="*80 + "\n")

        return llm_usage

    except Exception as e:
        print(f"⚠️ Erro ao rastrear uso de LLM: {str(e)}")
        import traceback
        traceback.print_exc()
        return None