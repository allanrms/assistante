# Integração Google Calendar com LangChain

Esta documentação descreve a arquitetura modular criada para integrar as ferramentas do Google Calendar com o LangChainAgent.

## Arquitetura

### 1. GoogleCalendarLangChainTools (`google_calendar/langchain_tools.py`)

Classe responsável por criar ferramentas LangChain a partir dos métodos do GoogleCalendarAIAssistant.

**Características:**
- Converte `@method_tool` do django-ai-assistant para `Tool` do LangChain
- Mantém a mesma funcionalidade das ferramentas originais
- Formato padronizado de entrada/saída para LangChain
- Tratamento de erros consistente

**Ferramentas disponíveis:**
- `conectar_google_calendar`: Conecta usuário via OAuth2
- `listar_eventos_calendar`: Lista próximos eventos
- `criar_evento_calendar`: Cria novos eventos
- `verificar_disponibilidade`: Verifica conflitos de horário
- `deletar_evento_por_telefone`: Cancela eventos por telefone
- `deletar_evento`: Cancela eventos por título/hora

### 2. LangChainAgent Atualizado (`agents/langchain_agent.py`)

O agente agora importa e utiliza as ferramentas do Google Calendar automaticamente.

**Mudanças:**
- Import da classe `GoogleCalendarLangChainTools`
- Método `_create_tools()` atualizado para incluir ferramentas do Calendar
- Tratamento de erros para casos onde o Calendar não esteja disponível
- Extensibilidade para adicionar outras ferramentas

## Como Usar

### Exemplo 1: Criação do Agente

```python
from agents.langchain_agent import LangChainAgent
from agents.models import LLMProviderConfig
from whatsapp_connector.models import MessageHistory

# Buscar configuração LLM
llm_config = LLMProviderConfig.objects.get(name="openai")

# Buscar MessageHistory
message_history = MessageHistory.objects.get(id=123)

# Criar agente (automaticamente carrega ferramentas do Calendar)
agent = LangChainAgent(llm_config, message_history)

# Enviar mensagem
response = agent.send_message("Quero agendar uma consulta para amanhã às 14h")
```

### Exemplo 2: Adicionando Novas Ferramentas

Para adicionar ferramentas de outros módulos, siga o mesmo padrão:

```python
# 1. Criar classe de ferramentas no módulo (ex: outro_modulo/langchain_tools.py)
class OutroModuloLangChainTools:
    def __init__(self, contexto):
        self.contexto = contexto

    def get_tools(self):
        return [
            Tool(
                name="nova_ferramenta",
                func=self._nova_ferramenta,
                description="Descrição da nova ferramenta"
            )
        ]

    def _nova_ferramenta(self, input_str: str) -> str:
        # Implementação da ferramenta
        return "Resultado da ferramenta"

# 2. Atualizar LangChainAgent._create_tools()
def _create_tools(self):
    tools = []

    # Google Calendar
    try:
        google_tools = GoogleCalendarLangChainTools(self.chat_session.from_number)
        tools.extend(google_tools.get_tools())
    except Exception as e:
        print(f"⚠️ Erro Google Calendar: {e}")

    # Novo módulo
    try:
        outro_tools = OutroModuloLangChainTools(self.contexto)
        tools.extend(outro_tools.get_tools())
    except Exception as e:
        print(f"⚠️ Erro Outro Módulo: {e}")

    return tools
```

## Formatos de Entrada das Ferramentas

### criar_evento_calendar
```
Format: titulo|data_inicio|hora_inicio|data_fim|hora_fim|descricao|localizacao
Exemplo: "Consulta médica|25/12/2024|14:30||15:30|Consulta de rotina|Clínica ABC"
```

### verificar_disponibilidade
```
Format: data|hora_inicio|hora_fim
Exemplo: "25/12/2024|14:00|15:00"
```

### deletar_evento
```
Format: titulo|hora|data
Exemplo: "Consulta médica|14:30|25/12/2024"
```

## Vantagens da Arquitetura

1. **Modularidade**: Cada módulo mantém suas próprias ferramentas
2. **Reutilização**: Ferramentas podem ser usadas em diferentes agentes
3. **Manutenibilidade**: Mudanças no Calendar não afetam outros módulos
4. **Extensibilidade**: Fácil adição de novos módulos de ferramentas
5. **Consistência**: Padrão uniforme para todas as ferramentas LangChain
6. **Robustez**: Tratamento de erros isolado por módulo

## Próximos Passos

1. Criar ferramentas para outros módulos (ex: WhatsApp, SMS, Email)
2. Implementar cache de ferramentas para melhor performance
3. Adicionar logging detalhado para debug
4. Criar testes unitários para as ferramentas
5. Documentar exemplos de uso específicos para cada ferramenta