import time
from typing import TypedDict, Any
from langchain.agents import create_agent

from .tools_secretary import get_secretary_tools
from .vectorstore import get_retriever_for_agent
from agents.langchain.llm_cost_calculator import calculate_llm_cost
from .tools import get_agent_tools
from .tools_calendar import get_calendar_tools
from .django_conversation_memory import DjangoConversationMemory
from ..models import LLMUsage, Agent, Message
from ..patterns.factories.llm_factory import LLMFactory


class AgentContext(TypedDict):
    """Schema do contexto passado para as tools via ToolRuntime.

    Note: Using TypedDict with total=False to avoid Pydantic serialization warnings.
    These fields are not meant to be serialized, only passed to tools at runtime.
    """
    conversation: Any
    retriever: Any


def ask_agent(message: Message, agent_model: Agent, k: int = 4) -> dict:
    """
    Faz uma pergunta ao agente RAG.

    Args:
        message: Instância de Message
        agent_model: Instância do Agent model (Django)
        k: Número de documentos a recuperar

    Returns:
        Dict com 'answer', 'sources' e 'usage'
    """
    conversation = message.conversation
    retriever = get_retriever_for_agent(agent_model, search_type="similarity", k=k)

    # Criar componentes
    llm = LLMFactory(agent_model).llm

    # Carregar ferramentas base (passando agent_model para carregar regras de intervenção)
    tools = get_agent_tools(agent=agent_model)

    tools_secretary = get_secretary_tools()
    tools.extend(tools_secretary)

    # Adicionar ferramentas do calendário se habilitado
    # if agent_model.has_calendar_tools:
    #     calendar_tools = get_calendar_tools()
    #     tools.extend(calendar_tools)



    memory = DjangoConversationMemory(conversation=conversation) if conversation else None

    # Montar prompt do sistema
    base_prompt = agent_model.build_prompt()


    # Obter histórico da conversa
    chat_history = []
    if memory:
        chat_history = memory.load_memory_variables({}).get("chat_history", [])

    # Criar agente com context_schema para passar dados às tools via ToolRuntime
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=base_prompt,
        context_schema=AgentContext,
    )

    # Montar mensagens com histórico
    messages_input = []
    if chat_history:
        messages_input.extend(chat_history)
    messages_input.append({"role": "user", "content": message.content})

    # Medir tempo e invocar com contexto para as tools
    start_time = time.time()
    result = agent.invoke(
        {"messages": messages_input},
        context={"conversation": conversation, "retriever": retriever},
    )
    response_time_ms = int((time.time() - start_time) * 1000)

    # Extrair resposta da última mensagem
    messages = result.get("messages", [])
    raw_content = messages[-1].content if messages else ""

    # Normalizar resposta (Gemini retorna lista de dicts, outros retornam string)
    if isinstance(raw_content, list):
        # Gemini: [{'type': 'text', 'text': '...'}]
        answer = "".join(
            item.get("text", "") for item in raw_content if isinstance(item, dict) and item.get("type") == "text"
        )
    else:
        answer = raw_content

    # Salvar no memory
    # if memory:
    #     memory.save_context({"input": message.content}, {"output": answer})

    # Estimativa de tokens e custos
    input_tokens = len(message.content) // 4
    output_tokens = len(answer) // 4

    costs = calculate_llm_cost(
        provider=agent_model.name,
        model_name=str(agent_model.model),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    # Salvar uso no banco
    llm_usage = LLMUsage.objects.create(
        conversation=conversation,
        message=message,
        provider=agent_model.name,
        model_name=agent_model.model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_cost=costs["input_cost"],
        output_cost=costs["output_cost"],
        response_time_ms=response_time_ms,
        context_size=0,
    )


    return {
        "answer": answer,
        "sources": [],
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "total_cost": float(llm_usage.total_cost),
            "response_time_ms": response_time_ms,
        }
    }