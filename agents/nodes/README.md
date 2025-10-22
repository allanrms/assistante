# Dialog Test - Agentes

Este diretório contém os agentes do sistema de conversação LangGraph, organizados de forma modular.

## Estrutura

Cada agente está em seu próprio arquivo e é **completamente autocontido**:
- **Configuração do LLM** específica para o agente
- **Função de prompt dinâmico** que injeta contexto (data, informações do contato)
- **Ferramentas (tools)** específicas do domínio do agente
- **Função de criação do node** que cria as tools internamente e monta o agente completo

**Importante:** Cada agente cria suas próprias tools internamente - não é necessário passar tools como parâmetro!

## Agentes Disponíveis

### 1. Recepção Agent (`recepcao_agent.py`)

**Responsabilidades:**
- Atendimento inicial do contato
- Coleta de dados do paciente (nome, email)
- Roteamento para outros agentes quando necessário

**LLM:** GPT-4o com temperature=0.6 (mais criativo para atendimento)

**Tools:** (criadas internamente)
- `atualizar_nome_contato(nome: str)` - Salva nome do contato no banco
- `atualizar_email_contato(email: str)` - Salva email do contato no banco
- `obter_informacoes_contato()` - Consulta informações já cadastradas
- `consultar_agendamentos_contato()` - Busca consultas marcadas do contato (futuras e histórico)

**Função principal:**
- `create_recepcao_node(contact)` - Cria o node completo (tools são criadas internamente)

---

### 2. Agenda Agent (`agenda_agent.py`)

**Responsabilidades:**
- Gerenciamento de agendamentos
- Consulta ao Google Calendar
- Verificação de disponibilidade
- Criação de eventos

**LLM:** GPT-4o com temperature=0.3 (mais determinístico para agendamentos)

**Tools:** (criadas internamente)
- `listar_eventos()` - Lista próximos eventos do calendário
- `verificar_disponibilidade(data: str)` - Verifica horários livres em uma data
- `buscar_proximas_datas(dia_semana: str)` - Busca próximas terças ou quintas
- `criar_evento(titulo, data, hora, tipo)` - Cria agendamento no Google Calendar e no banco

**Função principal:**
- `create_agenda_node(contact, client)` - Cria o node completo (tools são criadas internamente)

## Como Usar

```python
from agents.nodes import create_recepcao_node, create_agenda_node
from core.models import Contact

# Criar nodes (cada agente cria suas próprias tools internamente)
recepcao_node = create_recepcao_node(contact)
agenda_node = create_agenda_node(contact, client)

# Usar no grafo LangGraph
graph.add_node("recepcao", recepcao_node)
graph.add_node("agenda", agenda_node)
```

**Simples assim!** Não é necessário criar tools manualmente - cada agente é autocontido.

## Adicionando Novos Agentes

Para adicionar um novo agente, siga este padrão:

1. Crie um arquivo `nome_agent.py` neste diretório
2. Defina o LLM com temperatura apropriada
3. Implemente `get_prompt_nome(contact)` para prompts dinâmicos (privado)
4. Implemente `create_nome_tools(contact, ...)` com as tools do agente (privado)
5. Implemente `create_nome_node(contact, ...)` que cria tools internamente e retorna o node
6. Exporte apenas `create_nome_node` em `__init__.py`

### Template de Novo Agente

```python
# dialog_test/nodes/exemplo_agent.py
from typing import TYPE_CHECKING
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langgraph.graph import END

if TYPE_CHECKING:
    from core.models import Contact
    from dialog_test.conversation_graph import State

# LLM do agente
exemplo_llm = ChatOpenAI(model="gpt-4o", temperature=0.5)

# Prompt base
PROMPT_BASE = (Path(__file__).parent.parent / "prompts" / "exemplo.md").read_text()

def get_prompt_exemplo(contact: "Contact") -> str:
    """Gera prompt dinâmico (função privada)"""
    # Adicionar contexto temporal, informações do contato, etc.
    return PROMPT_BASE + contexto

def create_exemplo_tools(contact: "Contact"):
    """Cria tools do agente (função privada)"""
    @tool
    def fazer_algo(parametro: str) -> str:
        """Descrição clara da ferramenta"""
        try:
            # Lógica da tool
            return "✅ Sucesso"
        except Exception as e:
            return f"❌ Erro: {str(e)}"

    return [fazer_algo]

def create_exemplo_node(contact: "Contact", client=None):
    """Cria o nó do agente (função pública) - cria tools internamente"""

    # Criar tools internamente
    exemplo_tools = create_exemplo_tools(contact)

    # Criar agente com as tools
    exemplo_agent = create_react_agent(exemplo_llm, exemplo_tools)

    def exemplo_node(state: "State") -> dict:
        """Processa requisições do agente"""
        print("🎯 [EXEMPLO NODE] Iniciando...")

        # Gerar prompt dinâmico
        prompt_atual = get_prompt_exemplo(contact)
        messages = [SystemMessage(content=prompt_atual)] + list(state["history"])

        # Executar agente
        result = exemplo_agent.invoke({"messages": messages})

        # Processar resposta
        ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
        if ai_messages:
            msg = ai_messages[-1].content.strip()
        else:
            msg = "Erro ao processar"

        # Rotear para próximo agente ou finalizar
        next_agent = END  # ou outro agente

        return {
            "history": [AIMessage(content=msg)],
            "agent": next_agent
        }

    return exemplo_node
```

Depois, adicione em `__init__.py`:
```python
from .exemplo_agent import create_exemplo_node

__all__ = [
    # ...outros agentes
    'create_exemplo_node',
]
```

## Arquitetura

```
dialog_test/
├── agents/                    # Agentes modulares
│   ├── __init__.py           # Exports dos agentes
│   ├── README.md             # Este arquivo
│   ├── recepcao_agent.py     # Agente de recepção
│   └── agenda_agent.py       # Agente de agenda
├── prompts/                   # Prompts dos agentes
│   ├── aline_atendimento.md  # Prompt da recepção
│   └── aline_agenda.md       # Prompt da agenda
├── langgraph/
│   └── conversation_runner.py # Runner que monta o grafo
└── conversation_graph.py      # Define apenas o State
```

## State Compartilhado

O `State` é definido em `dialog_test/conversation_graph.py` e compartilhado entre todos os agentes:

```python
class State(TypedDict):
    history: Annotated[Sequence[BaseMessage], add_messages]
    agent: str        # Nome do próximo agente
    confirmed: bool   # Flag de confirmação de agendamento
```

## Convenções

- **Agentes autocontidos:** Cada `create_*_node` cria suas próprias tools internamente
- **Funções privadas:** `get_prompt_*` e `create_*_tools` são internas ao módulo (não exportadas)
- **Funções públicas:** Apenas `create_*_node` é exportada no `__init__.py`
- **Prefixos de mensagens:** Use `[AGENDA_REQUEST]` e `[AGENDA_RESPONSE]` para comunicação entre agentes
- **Logs:** Use print com emojis para facilitar debug (`🔧`, `✅`, `❌`, `📝`, etc.)
- **Type hints:** Use TYPE_CHECKING para evitar imports circulares
- **Tools:** Sempre retornem strings com mensagens claras de sucesso/erro
- **Erros:** Capture exceções e retorne mensagens formatadas (não deixe exceptions subir)
