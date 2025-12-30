# Secretária Virtual LangGraph

Implementação determinística de assistente virtual para consultórios médicos usando **LangGraph como máquina de estados**.

## 📋 Especificação

Esta implementação segue **EXATAMENTE** o documento técnico `secretaria_virtual_langgraph_completa.md`.

### Princípios Arquiteturais

1. ✅ **LangGraph controla o fluxo** (não AgentExecutor)
2. ✅ **LLM apenas classifica intenção** ou gera texto
3. ✅ **Ferramentas só chamadas por nós específicos**
4. ✅ **Conversation.status é autoridade máxima**
5. ✅ **Transferência humana é estado terminal**
6. ✅ **Proibido improvisar fluxos**

## 🏗️ Arquitetura

```
START → guard → detect_intent → [roteamento] → ações → send_response → END
```

### Nós do Grafo

| Nó | Função | Saída |
|---|---|---|
| `guard` | Bloqueia se status != 'ai' | END ou continua |
| `detect_intent` | Classifica intenção via LLM | Intent detectada |
| `transfer_human` | Transfere para humano | END (terminal) |
| `agendar` | Gera link de agendamento | Link público |
| `consultar` | Lista agendamentos | Lista formatada |
| `cancelar_listar` | Mostra agendamentos para cancelar | Aguarda ID |
| `cancelar_confirmar` | Confirma cancelamento | Confirmação |
| `reagendar_listar` | Mostra agendamentos para reagendar | Aguarda ID |
| `reagendar_confirmar` | Gera novo link | Novo link |
| `send_response` | Envia mensagem ao usuário | END |

### Intenções Válidas

- `AGENDAR` - Criar novo agendamento
- `CONSULTAR` - Ver agendamentos existentes
- `CANCELAR` - Cancelar agendamento
- `REAGENDAR` - Mudar data/hora
- `HUMANO` - Transferir para atendente
- `OUTRO` - Qualquer outra coisa

## 📁 Estrutura de Arquivos

```
agents/langgraph/
├── __init__.py              # Exportações públicas
├── README.md                # Esta documentação
├── state.py                 # SecretaryState (Pydantic)
├── runtime.py               # SecretaryRuntime (envio de mensagens)
├── tools.py                 # Funções auxiliares (agendamento, etc)
├── nodes.py                 # Nós do grafo
├── graph.py                 # Construção do StateGraph
└── main.py                  # Ponto de entrada
```

## 🚀 Como Usar

### Integração com Webhook do WhatsApp

```python
from agents.langgraph import process_whatsapp_message

# Ao receber mensagem do webhook
result = process_whatsapp_message(
    conversation_id=123,
    message_id=456,
    user_input="Quero agendar uma consulta"
)

print(result['intent'])    # 'AGENDAR'
print(result['response'])  # Link de agendamento enviado
```

### Processar Objeto Message Diretamente

```python
from agents.langgraph import process_message_from_webhook
from agents.models import Message

message = Message.objects.get(id=456)
result = process_message_from_webhook(message)
```

## 🔧 Configuração Necessária

### 1. Variáveis de Ambiente

```bash
# OpenAI (se usar GPT)
OPENAI_API_KEY=sk-...

# Anthropic (se usar Claude)
ANTHROPIC_API_KEY=sk-ant-...
```

### 2. Modelos Django Requeridos

- ✅ `Conversation` - Gerenciamento de conversas
- ✅ `Message` - Mensagens trocadas
- ✅ `Agent` - Configuração de LLM
- ✅ `Contact` - Dados do contato
- ✅ `Appointment` - Agendamentos
- ✅ `AppointmentToken` - Tokens de agendamento

### 3. Ajustar Base URL

Em `tools.py`, ajuste a `base_url` para seu domínio:

```python
# TODO: Pegar de settings
base_url = "https://seu-dominio.com.br"
```

## 🔒 Regras Absolutas

⚠️ **NUNCA:**
- Inventar links de agendamento
- Chamar tools fora do nó correto
- Continuar após transferência humana
- Responder se `Conversation.status != 'ai'`

✅ **SEMPRE:**
- Validar que agendamento pertence ao contato
- Gerar tokens únicos para links
- Registrar transferências humanas
- Bloquear no guard se não for 'ai'

## 🧪 Testes

### Teste Manual

```python
from agents.langgraph import build_secretary_graph
from agents.langgraph.state import SecretaryState

graph = build_secretary_graph()

# Simular mensagem
state = SecretaryState(
    conversation_id=1,
    message_id=1,
    user_input="Quero consultar meus agendamentos"
)

result = graph.invoke(state)
print(f"Intenção: {result['intent']}")  # 'CONSULTAR'
```

### Visualizar Grafo (Opcional)

```python
from agents.langgraph import build_secretary_graph

graph = build_secretary_graph()

# Requer: pip install pygraphviz
graph.get_graph().draw_png("secretary_graph.png")
```

## 📊 Fluxo de Exemplo

### Cenário 1: Agendar Consulta

```
Usuário: "Quero agendar"
   ↓
[guard] ✅ Status = 'ai', continua
   ↓
[detect_intent] 🎯 Intent = 'AGENDAR'
   ↓
[agendar] 📅 Gera link único
   ↓
[send_response] 📤 Envia link via WhatsApp
   ↓
END
```

### Cenário 2: Transferência Humana

```
Usuário: "Quero falar com atendente"
   ↓
[guard] ✅ Status = 'ai', continua
   ↓
[detect_intent] 🎯 Intent = 'HUMANO'
   ↓
[transfer_human] 🚨 Altera status → 'human'
   ↓
END (terminal)
```

### Cenário 3: Cancelamento (2 etapas)

```
Usuário: "Quero cancelar"
   ↓
[guard] ✅ Status = 'ai', continua
   ↓
[detect_intent] 🎯 Intent = 'CANCELAR'
   ↓
[cancelar_listar] 📋 Mostra agendamentos
   ↓
[send_response] 📤 "Informe o ID..."
   ↓
END

--- Nova mensagem ---

Usuário: "15"
   ↓
[guard] ✅ Continua
   ↓
[detect_intent] 🎯 (detecta número)
   ↓
[cancelar_confirmar] ✅ Cancela ID 15
   ↓
[send_response] 📤 "Cancelado com sucesso"
   ↓
END
```

## 🎯 Resultado Esperado

Conforme documento técnico:

- ✅ Atendimento previsível
- ✅ Zero alucinação operacional
- ✅ Segurança em cancelamentos
- ✅ Transferência humana confiável

## 📚 Compatibilidade LangGraph

Implementado conforme **LangGraph 2025**:

- ✅ `StateGraph` com Pydantic BaseModel
- ✅ `START` e `END` importados de `langgraph.graph`
- ✅ `add_node`, `add_edge`, `add_conditional_edges`
- ✅ `graph.compile()` e `graph.invoke()`
- ✅ Validação em runtime nos inputs dos nós

## 🐛 Troubleshooting

### Erro: "No module named 'langgraph'"

```bash
pip install langgraph langchain-openai langchain-anthropic
```

### Erro: "Conversation matching query does not exist"

Certifique-se de que a conversa existe e está ativa:

```python
conversation = Conversation.objects.get(id=123)
print(conversation.status)  # Deve ser 'ai' ou 'human'
```

### Grafo não envia mensagens

Verifique:
1. `Conversation.status == 'ai'`
2. `EvolutionInstance` configurada
3. Credenciais da Evolution API válidas

## 📄 Licença

Este código é parte do projeto Assistante e segue a licença do projeto principal.

## 🤝 Suporte

Para dúvidas ou problemas, consulte o documento técnico original:
`secretaria_virtual_langgraph_completa.md`