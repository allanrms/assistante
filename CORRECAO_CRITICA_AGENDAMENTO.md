# 🚨 CORREÇÃO CRÍTICA: IA Confirmando Agendamento Sem Criar

## ❌ Problema Reportado

**Sintoma:**
A IA dizia "Perfeito! Consulta agendada para 27/10/2025 às 11:00" mas NÃO estava criando o agendamento no Google Calendar.

**Logs do erro:**
```
14. 🤖 AI
   ⚙️ Chamadas: atualizar_nome_contato, consultar_agendamentos_contato

19. 🤖 AI
Perfeito! Consulta agendada para 27/10/2025 às 11:00.

⚠️ [RECEPÇÃO NODE] Nenhum [AGENDA_REQUEST] válido detectado — resposta direta ao usuário
```

**Análise do problema:**
1. Paciente confirmou com "sim"
2. IA chamou ferramentas ERRADAS (`atualizar_nome_contato`, `consultar_agendamentos_contato`)
3. IA NÃO enviou `[AGENDA_REQUEST]`
4. IA mentiu dizendo que agendou

---

## ✅ Solução Implementada

### 1. Aviso Gigante no Início do Prompt (`recepcao.md:5-11`)

Adicionado um aviso em **NEGRITO E MAIÚSCULAS** no topo do prompt:

```markdown
## ⚠️ REGRA CRÍTICA - LEIA PRIMEIRO

**VOCÊ NUNCA, EM HIPÓTESE ALGUMA, PODE DIZER QUE UM AGENDAMENTO FOI CRIADO SEM TER ENVIADO `[AGENDA_REQUEST]` E RECEBIDO `[AGENDA_RESPONSE] ✅ Agendamento criado`**

**SE VOCÊ DISSER "CONSULTA AGENDADA" OU "AGENDAMENTO CRIADO" SEM EXECUTAR ESTE PROCESSO, VOCÊ ESTÁ MENTINDO PARA O PACIENTE.**

**Você é APENAS a recepcionista. Você NÃO cria agendamentos. Quem cria é a Aline Agenda (outro agente).**
```

---

### 2. Nova Ferramenta: `solicitar_criacao_agendamento` (`recepcao_agent.py:147-177`)

Criada ferramenta específica para forçar o comportamento correto:

```python
@tool
def solicitar_criacao_agendamento(nome_paciente: str, tipo_consulta: str, data: str, horario: str) -> str:
    """
    Solicita à Aline Agenda a criação de um agendamento no Google Calendar.
    USE ESTA FERRAMENTA quando o paciente CONFIRMAR que deseja agendar.
    """
    # Validar tipo de consulta
    if tipo_consulta.lower() not in ['particular', 'convênio', 'convenio']:
        return "❌ Tipo de consulta inválido. Use 'particular' ou 'convênio'."

    # Retornar a mensagem [AGENDA_REQUEST] formatada
    request_msg = f"[AGENDA_REQUEST] Criar agendamento para {nome_paciente}, tipo {tipo_consulta}, data {data}, horário {horario}"
    return request_msg
```

**Por que isso funciona:**
- Força a IA a usar uma ferramenta quando paciente confirmar
- Garante formato correto de `[AGENDA_REQUEST]`
- Evita que a IA invente respostas

---

### 3. Detecção de [AGENDA_REQUEST] em ToolMessage (`recepcao_agent.py:307-317`)

Adicionado código para detectar `[AGENDA_REQUEST]` tanto em `ToolMessage` quanto em `AIMessage`:

```python
# Verificar se alguma ToolMessage contém [AGENDA_REQUEST]
from langchain_core.messages import ToolMessage
for msg in result["messages"]:
    if isinstance(msg, ToolMessage) and "[AGENDA_REQUEST]" in msg.content:
        print("🎯 [RECEPÇÃO NODE] [AGENDA_REQUEST] detectado em ToolMessage — roteando para agenda")
        is_valid, agenda_request = validate_agenda_request(msg.content)
        if is_valid:
            return {
                "history": [HumanMessage(content=agenda_request)],
                "agent": "agenda"
            }
```

---

### 4. Instruções Explícitas no Prompt (`recepcao.md:218-273`)

Adicionado fluxo detalhado com exemplos do que fazer e NÃO fazer:

```markdown
**ERRADO (NUNCA FAÇA ISSO):**
❌ Paciente: "sim"
❌ Você: "Perfeito! Consulta agendada para 27/10/2025 às 11:00" ← MENTIRA!

**CERTO (SEMPRE FAÇA ASSIM):**
✅ Paciente: "sim"
✅ Você: [CHAMA solicitar_criacao_agendamento(...)]
✅ [AGUARDA RESPOSTA [AGENDA_RESPONSE] da Aline Agenda]
✅ [SÓ ENTÃO confirma ao paciente]
```

E instrução sobre o que fazer após chamar a ferramenta:

```markdown
**⚠️ O QUE FAZER APÓS CHAMAR A FERRAMENTA:**

Quando você chamar `solicitar_criacao_agendamento`, a ferramenta vai retornar algo como:
[AGENDA_REQUEST] Criar agendamento para Allan Ramos, tipo particular, data 27/10/2025, horário 11:00

**VOCÊ DEVE RETORNAR EXATAMENTE ESTA MENSAGEM AO USUÁRIO.**
**NÃO adicione nada antes ou depois.**
**NÃO diga "Perfeito, agendado!"**
**APENAS retorne a mensagem [AGENDA_REQUEST] que a ferramenta gerou.**
```

---

## 🧪 Como Testar a Correção

### Teste 1: Fluxo Completo de Agendamento

```bash
python manage.py runserver
```

**No WhatsApp:**
1. Usuário: "Quero marcar consulta"
2. Bot: "Pode me informar seu nome completo?"
3. Usuário: "Allan Ramos"
4. Bot: "A consulta será particular ou pelo convênio?"
5. Usuário: "Particular"
6. Bot mostra datas disponíveis
7. Usuário escolhe data
8. Bot mostra horários disponíveis
9. Usuário: "às 11h"
10. Bot: "Só para confirmar, posso agendar sua consulta para 27/10/2025 às 11:00?"
11. Usuário: "sim"

**O QUE DEVE ACONTECER:**

**Logs esperados:**
```bash
🔧 [TOOL CALL] solicitar_criacao_agendamento
   📝 Nome: Allan Ramos
   🏥 Tipo: particular
   📅 Data: 27/10/2025
   ⏰ Horário: 11:00
✅ [TOOL] Retornando solicitação formatada: [AGENDA_REQUEST] Criar agendamento...
🎯 [RECEPÇÃO NODE] [AGENDA_REQUEST] detectado em ToolMessage — roteando para agenda

🔧 [TOOL CALL] criar_evento
   📝 Titulo: Allan Ramos
   📅 Data: 27/10/2025
   ⏰ Hora: 11:00
   🏥 Tipo: particular
📡 [TOOL] Enviando evento para Google Calendar...
✅ [TOOL] Evento criado com sucesso no Calendar
✅ [TOOL] Appointment #X criado com sucesso no banco
```

**Resposta ao usuário (SOMENTE após sucesso):**
```
Perfeito! Consulta agendada para 27/10/2025 às 11:00.
Endereço: R. Martins Alfenas, 2309, Centro, Alfenas - MG.
[Google Maps](https://share.google/44Vh42ePv6uVCKTQP)
```

---

### Teste 2: Verificar que Não Confirma Sem Criar

**Cenário:** Forçar erro no Google Calendar (desconectar internet, por exemplo)

**Comportamento esperado:**
1. IA chama `solicitar_criacao_agendamento`
2. Sistema envia para Agenda Agent
3. Agenda Agent tenta criar e falha
4. Agenda retorna `[AGENDA_RESPONSE] ❌ Erro ao criar evento: ...`
5. **IA NÃO diz que agendou**
6. IA informa o erro ao paciente

---

## 📊 Indicadores de Sucesso

### ✅ Funcionando Corretamente:

- [ ] Log `[TOOL CALL] solicitar_criacao_agendamento` aparece quando paciente confirma
- [ ] Log `[RECEPÇÃO NODE] [AGENDA_REQUEST] detectado` aparece
- [ ] Log `[TOOL CALL] criar_evento` aparece no Agenda Agent
- [ ] Log `✅ [TOOL] Evento criado com sucesso no Calendar` aparece
- [ ] Log `✅ [TOOL] Appointment #X criado com sucesso no banco` aparece
- [ ] Bot SOMENTE confirma ao paciente APÓS todos os logs acima

### ❌ Problema Persiste:

- [ ] Bot diz "agendado" sem logs de `solicitar_criacao_agendamento`
- [ ] Log `⚠️ [RECEPÇÃO NODE] Nenhum [AGENDA_REQUEST] válido detectado` aparece após confirmação
- [ ] Bot chama ferramentas erradas (`atualizar_nome_contato`, `consultar_agendamentos_contato`) quando deveria criar agendamento
- [ ] Agendamento NÃO aparece no Google Calendar

---

## 🔍 Troubleshooting

### Problema: Bot ainda confirma sem criar

**Diagnóstico:**
```bash
# Verificar se a temperatura está baixa
grep "temperature" agents/langgraph/nodes/recepcao_agent.py
# Deve mostrar: temperature=0.1

# Verificar se a ferramenta foi carregada
grep "solicitar_criacao_agendamento" agents/langgraph/nodes/recepcao_agent.py
# Deve aparecer na lista de ferramentas
```

**Solução:**
- Reiniciar o servidor Django
- Verificar se não há cache de código antigo
- Confirmar que o arquivo `recepcao.md` foi atualizado

---

### Problema: Ferramenta não é chamada

**Diagnóstico:**
```bash
# Verificar logs quando paciente confirma "sim"
python manage.py runserver 2>&1 | grep -A 5 "TOOL CALL"
```

**Se não aparecer `solicitar_criacao_agendamento`:**
- O prompt pode não estar sendo carregado corretamente
- A temperatura pode estar muito alta (causar comportamento errático)
- O modelo pode estar ignorando a instrução

**Solução:**
- Adicionar mais ênfase no prompt sobre USO OBRIGATÓRIO da ferramenta
- Reduzir ainda mais a temperatura (tentar 0.0)
- Adicionar exemplo de conversa completa no prompt

---

## 📋 Checklist de Verificação

Antes de considerar o problema resolvido:

- [ ] Testado agendamento completo pelo menos 3 vezes
- [ ] Todos os agendamentos criados aparecem no Google Calendar
- [ ] Logs mostram execução correta das ferramentas
- [ ] Bot NÃO confirma sem receber `[AGENDA_RESPONSE] ✅ Agendamento criado`
- [ ] Testado cancelamento de consulta (deve continuar funcionando)
- [ ] Testado consulta de agendamentos (deve continuar funcionando)

---

## 📁 Arquivos Modificados

1. **`agents/langgraph/prompts/recepcao.md`**
   - Adicionado aviso crítico no início
   - Instruções detalhadas sobre uso de `solicitar_criacao_agendamento`
   - Exemplos explícitos de certo vs errado

2. **`agents/langgraph/nodes/recepcao_agent.py`**
   - Nova ferramenta `solicitar_criacao_agendamento`
   - Detecção de `[AGENDA_REQUEST]` em ToolMessage
   - Logs detalhados

---

## 🚀 Próximos Passos

Se o problema persistir após estas correções:

1. **Considerar approach alternativo:**
   - Usar function calling estruturado do OpenAI ao invés de React Agent
   - Criar validação de estado antes de permitir confirmação ao usuário
   - Adicionar middleware que bloqueia respostas sem `[AGENDA_REQUEST]`

2. **Adicionar testes automatizados:**
   ```python
   def test_nao_confirma_sem_criar_agendamento():
       # Simular fluxo completo
       # Assert que [AGENDA_REQUEST] foi enviado
       # Assert que resposta só ocorre após [AGENDA_RESPONSE]
   ```

3. **Implementar rate limiting de confirmações:**
   - Bloquear múltiplas confirmações em curto período
   - Prevenir que IA "alucine" múltiplos agendamentos

---

**Data da correção:** 24/10/2025 (segunda iteração)
**Status:** ✅ Correções críticas aplicadas - aguardando testes
