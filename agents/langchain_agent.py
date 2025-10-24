# from langchain_openai import ChatOpenAI
# from langchain_anthropic import ChatAnthropic
# from langchain_google_genai import ChatGoogleGenerativeAI
# from django.conf import settings
# from whatsapp_connector.models import MessageHistory
# from google_calendar.langchain_tools import GoogleCalendarLangChainTools
# from datetime import datetime, timedelta
#
#
# class LangChainAgent:
#     """
#     Agente LangChain configurado dinamicamente com LLMProviderConfig e ChatSession
#     """
#
#     def __init__(self, llm_config: LLMProviderConfig, message_history: MessageHistory):
#         """
#         Inicializa o agente LangChain com configurações específicas
#
#         Args:
#             llm_config (LLMProviderConfig): Configuração do modelo LLM
#             message_history (MessageHistory): Histórico de mensagem atual
#         """
#         try:
#             self.llm_config = llm_config
#             self.message_history = message_history
#             self.chat_session = message_history.chat_session
#
#             print(f"🔧 Inicializando LangChain Agent para {self.chat_session.from_number}")
#
#             self.llm = self._create_llm()
#             print("✅ LLM criado com sucesso")
#
#             self.tools = self._create_tools()
#             print(f"✅ {len(self.tools)} ferramentas criadas")
#
#             self.agent = self._create_agent()
#             print("✅ Agente LangChain inicializado com sucesso")
#
#         except Exception as e:
#             print(f"❌ Erro fatal na inicialização do LangChain Agent: {e}")
#             raise e
#
#     def _create_llm(self):
#         """
#         Cria o modelo LLM baseado na configuração
#
#         Returns:
#             LLM configurado (OpenAI, Anthropic ou Google)
#         """
#         provider = self.llm_config.name
#
#         if provider == "openai":
#             return ChatOpenAI(
#                 model=self.llm_config.model,
#                 temperature=self.llm_config.temperature,
#                 max_tokens=self.llm_config.max_tokens,
#                 top_p=self.llm_config.top_p,
#                 presence_penalty=self.llm_config.presence_penalty,
#                 frequency_penalty=self.llm_config.frequency_penalty,
#                 openai_api_key=getattr(settings, 'OPENAI_API_KEY', '')
#             )
#         elif provider == "anthropic":
#             return ChatAnthropic(
#                 model=self.llm_config.model,
#                 temperature=self.llm_config.temperature,
#                 max_tokens=self.llm_config.max_tokens,
#                 top_p=self.llm_config.top_p,
#                 anthropic_api_key=getattr(settings, 'ANTHROPIC_API_KEY', '')
#             )
#         elif provider == "google":
#             return ChatGoogleGenerativeAI(
#                 model=self.llm_config.model,
#                 temperature=self.llm_config.temperature,
#                 max_output_tokens=self.llm_config.max_tokens,
#                 top_p=self.llm_config.top_p,
#                 google_api_key=getattr(settings, 'GOOGLE_API_KEY', '')
#             )
#         else:
#             # Fallback para OpenAI
#             return ChatOpenAI(
#                 model=self.llm_config.model or "gpt-4o",
#                 temperature=self.llm_config.temperature,
#                 openai_api_key=getattr(settings, 'OPENAI_API_KEY', '')
#             )
#
#     def _create_tools(self):
#         """
#         Cria ferramentas disponíveis para o agente
#
#         Returns:
#             Lista de ferramentas LangChain
#         """
#         tools = []
#         number_whatsapp = self.chat_session.from_number
#
#         # Google Calendar Tools
#
#         if self.chat_session.evolution_instance.llm_config.has_calendar_tools == True:
#             google_calendar_tools = GoogleCalendarLangChainTools(number_whatsapp)
#             tools.extend(google_calendar_tools.get_tools())
#
#         # Ferramenta para obter hora atual
#         def get_current_time(_=None):
#             now = datetime.now()
#             days_of_week = {
#                 0: "segunda-feira", 1: "terça-feira", 2: "quarta-feira",
#                 3: "quinta-feira", 4: "sexta-feira", 5: "sábado", 6: "domingo"
#             }
#             day_of_week = days_of_week[now.weekday()]
#             return f"{now.strftime('%d/%m/%Y %H:%M')} ({day_of_week})"
#
#         tools.append(Tool(
#             name="get_current_time",
#             func=get_current_time,
#             description="Obtém a data e hora atual no formato brasileiro com dia da semana"
#         ))
#
#         # Ferramenta para verificar dia da semana de uma data específica
#         def get_weekday(data_str: str):
#             try:
#                 data_obj = datetime.strptime(data_str, '%d/%m/%Y')
#                 days_of_week = {
#                     0: "segunda-feira", 1: "terça-feira", 2: "quarta-feira",
#                     3: "quinta-feira", 4: "sexta-feira", 5: "sábado", 6: "domingo"
#                 }
#                 days_of_week = days_of_week[data_obj.weekday()]
#                 return f"{data_str} é uma {days_of_week}"
#             except ValueError:
#                 return "❌ Formato de data inválido. Use DD/MM/YYYY"
#
#         tools.append(Tool(
#             name="get_weekday",
#             func=get_weekday,
#             description="Verifica qual dia da semana é uma data específica. Formato: DD/MM/YYYY"
#         ))
#
#         # Ferramenta para encontrar próximas datas de terça ou quinta
#         def get_next_weekday(weekday: str):
#             """Finds the next Tuesday or Thursday from today"""
#             try:
#                 today = datetime.now()
#                 target_weekdays = {
#                     "terca": 1,
#                     "terça": 1,
#                     "quinta": 3
#                 }
#
#                 normalized_weekday = weekday.lower().strip()
#                 if normalized_weekday not in target_weekdays:
#                     return "❌ Use 'terça' ou 'quinta'"
#
#                 target_day = target_weekdays[normalized_weekday]
#                 days_until_target = (target_day - today.weekday()) % 7
#
#                 # If it's the same weekday, get next occurrence
#                 if days_until_target == 0:
#                     days_until_target = 7
#
#                 next_date = today + timedelta(days=days_until_target)
#                 following_date = next_date + timedelta(days=7)
#
#                 return f"""Próximas {normalized_weekday}s:
# 1. {next_date.strftime('%d/%m/%Y')} ({normalized_weekday})
# 2. {following_date.strftime('%d/%m/%Y')} ({normalized_weekday})"""
#             except Exception as e:
#                 return f"❌ Erro: {str(e)}"
#
#         tools.append(Tool(
#             name="proximo_dia_semana",
#             func=get_next_weekday,
#             description="Encontra as próximas 2 ocorrências de terça ou quinta a partir de hoje. Use: 'terça' ou 'quinta'"
#         ))
#
#         # Ferramenta para enviar arquivos
#         def send_file(file_name: str):
#             """Sends an available file to the user via WhatsApp"""
#             try:
#                 from whatsapp_connector.services import EvolutionAPIService
#                 from agents.models import AssistantContextFile
#                 import re
#
#                 print(f"📤 Ferramenta enviar_arquivo chamada com: '{file_name}'")
#
#                 # Clean file name (remove parentheses with file types)
#                 clean_name = re.sub(r'\s*\([^)]*\)\s*$', '', file_name).strip()
#                 print(f"🧹 Nome limpo: '{clean_name}'")
#
#                 # Search file by name (flexible search)
#                 file_obj = self.llm_config.context_files.filter(
#                     name__icontains=clean_name,
#                     is_active=True,
#                     status='ready'
#                 ).first()
#
#                 if not file_obj:
#                     # List available files for debug
#                     available_files = self.llm_config.context_files.filter(
#                         is_active=True,
#                         status='ready'
#                     ).values_list('name', flat=True)
#                     files_list = ', '.join(available_files) if available_files else 'nenhum'
#                     return f"❌ Arquivo '{file_name}' não encontrado. Arquivos disponíveis: {files_list}"
#
#                 # Get full file path
#                 file_path = file_obj.file.path
#
#                 # Send file via Evolution API
#                 service = EvolutionAPIService(self.chat_session.evolution_instance)
#                 response = service.send_file_message(
#                     to_number=number_whatsapp,
#                     file_url_or_path=file_path,
#                     caption=file_obj.name
#                 )
#
#                 if response:
#                     return f"✅ Arquivo '{file_obj.name}' enviado com sucesso!"
#                 else:
#                     return f"❌ Erro ao enviar arquivo '{file_obj.name}'"
#
#             except Exception as e:
#                 return f"❌ Erro ao enviar arquivo: {str(e)}"
#
#         tools.append(Tool(
#             name="enviar_arquivo",
#             func=send_file,
#             description="Envia um arquivo disponível para o usuário. Use o nome exato do arquivo conforme listado nos arquivos disponíveis. Exemplo: enviar_arquivo('FAQ Mudanca Para Portugal')"
#         ))
#
#         # Ferramenta para atualizar resumo do contato
#         def update_contact_summary(resumo: str):
#             """
#             Atualiza o resumo sobre este contato no ChatSession.
#             Use para salvar informações importantes como: nome, preferências, histórico de consultas,
#             condições médicas, etc.
#             """
#             try:
#                 print(f"📝 Atualizando resumo do contato {number_whatsapp}")
#
#                 # Atualizar resumo no ChatSession
#                 self.chat_session.contact_summary = resumo
#                 self.chat_session.save(update_fields=['contact_summary'])
#
#                 print(f"✅ Resumo atualizado: {resumo[:100]}...")
#                 return f"✅ Resumo do contato atualizado com sucesso!"
#             except Exception as e:
#                 print(f"❌ Erro ao atualizar resumo: {e}")
#                 return f"❌ Erro ao atualizar resumo: {str(e)}"
#
#         tools.append(Tool(
#             name="update_contact_summary",
#             func=update_contact_summary,
#             description="""Atualiza/salva informações importantes sobre este usuário para lembrar em conversas futuras.
#
# 🎯 QUANDO USAR:
# - SEMPRE que o usuário mencionar dados pessoais importantes
# - Quando descobrir informações que devem ser lembradas
# - Para melhorar personalização em futuras conversas
#
# 📝 O QUE SALVAR:
# - Nome completo
# - Profissão/ocupação
# - Localização (cidade, país)
# - Interesses ou hobbies mencionados
# - Preferências ou gostos pessoais
# - Contexto familiar (ex: "tem 2 filhos")
# - Situações de vida importantes (ex: "está se mudando para Portugal")
# - Projetos pessoais ou profissionais mencionados
# - Qualquer informação que ajude a tornar conversas futuras mais personalizadas
#
# ⚠️ IMPORTANTE:
# - Sempre ADICIONE novas informações ao resumo existente (não substitua)
# - Use formato claro e estruturado: "Campo: Valor | Campo2: Valor2"
# - Seja conciso mas informativo
# - NUNCA invente informações - só salve o que o usuário disse
#
# ✅ EXEMPLOS CORRETOS:
# - update_contact_summary('Nome: João Silva | Profissão: Engenheiro | Cidade: São Paulo | Interesse: viagens')
# - update_contact_summary('Nome: Maria Costa | Localização: Lisboa, Portugal | Projeto: mudança internacional | Família: 2 filhos')
# - update_contact_summary('Nome: Pedro Santos | Trabalha com: desenvolvimento de software | Gosta de: tecnologia e games | Situação: procurando novo emprego')"""
#         ))
#
#         return tools
#
#
#     def _create_agent(self):
#         """
#         Cria o agente LangChain com configurações específicas
#
#         Returns:
#             Agente LangChain configurado
#         """
#         try:
#             # Criar prompt do sistema
#             system_prompt = self._build_system_prompt()
#
#             return initialize_agent(
#                 self.tools,
#                 self.llm,
#                 agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
#                 verbose=True,
#                 handle_parsing_errors="Check your output and make sure it conforms to the expected format!",
#                 max_iterations=5,  # Limit iterations to prevent infinite loops
#                 early_stopping_method="generate",  # Generate final answer when max iterations reached
#                 agent_kwargs={"system_message": system_prompt}
#             )
#         except Exception as e:
#             print(f"❌ Erro ao criar agente LangChain: {e}")
#             # Fallback: tentar sem agent_kwargs
#             try:
#                 return initialize_agent(
#                     self.tools,
#                     self.llm,
#                     agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
#                     verbose=True,
#                     handle_parsing_errors=True
#                 )
#             except Exception as e2:
#                 print(f"❌ Erro no fallback do agente: {e2}")
#                 raise e2
#
#     def _get_chat_history(self):
#         """
#         Recupera histórico da conversa no formato LangChain com contexto resumido
#
#         Returns:
#             Lista de mensagens LangChain
#         """
#         try:
#             # Buscar últimas mensagens da sessão
#             last_messages = self.chat_session.messages.order_by("created_at")[:15]
#
#             memory_messages = []
#
#             # Extrair informações importantes do histórico completo
#             patient_name = None
#             appointment_type = None
#             suggested_date = None
#             suggested_time = None
#
#             for msg in last_messages:
#                 user_content = msg.content or ""
#                 ai_content = msg.response or ""
#
#                 # Tentar extrair nome
#                 if not patient_name and ai_content and "nome completo" in ai_content.lower():
#                     # A próxima mensagem do usuário provavelmente é o nome
#                     patient_name = user_content.strip() if user_content.strip() else None
#
#                 # Tentar extrair tipo de consulta
#                 if "particular" in user_content.lower():
#                     appointment_type = "particular"
#                 elif "convênio" in user_content.lower() or "convenio" in user_content.lower():
#                     appointment_type = "convênio"
#
#                 # Adicionar ao histórico
#                 if user_content.strip():
#                     memory_messages.append(HumanMessage(content=user_content.strip()))
#                 if ai_content.strip():
#                     memory_messages.append(AIMessage(content=ai_content.strip()))
#
#             # Se temos informações contextuais, adicionar no início
#             if patient_name or appointment_type:
#                 context = "CONTEXTO DA CONVERSA:\n"
#                 if patient_name:
#                     context += f"- Nome do paciente: {patient_name}\n"
#                 if appointment_type:
#                     context += f"- Tipo de consulta: {appointment_type}\n"
#
#                 memory_messages.insert(0, HumanMessage(content=context))
#
#             return memory_messages
#
#         except Exception as e:
#             print(f"Erro ao recuperar histórico: {e}")
#             return []
#
#     def _get_available_files(self):
#         """
#         Obtém lista de arquivos disponíveis de llm_config.context_files
#
#         Returns:
#             String com lista formatada de arquivos disponíveis
#         """
#         # Buscar arquivos ativos do llm_config
#         context_files = self.llm_config.context_files.filter(
#             is_active=True,
#             status='ready'
#         )
#
#         if not context_files.exists():
#             return ""
#
#         files_section = "\n\n## 📁 ARQUIVOS DISPONÍVEIS PARA ENVIO\n\n"
#         files_section += "Você tem acesso aos seguintes arquivos que podem ser enviados ao usuário:\n\n"
#
#         for file_obj in context_files:
#             files_section += f"- {file_obj.name} ({file_obj.get_file_type_display()})\n"
#
#         files_section += "\n**INSTRUÇÕES DE ENVIO DE ARQUIVOS:**\n"
#         files_section += "1. Se houver um arquivo útil para a dúvida do usuário, mencione de forma natural que ele existe, sem repetir sempre.\n"
#         files_section += "   - Exemplo: 'Posso te enviar o regulamento em PDF, se quiser.'\n"
#         files_section += "2. Só use a ferramenta `enviar_arquivo` quando o usuário confirmar o interesse (responder 'sim', 'pode enviar', 'quero', 'manda', etc.).\n"
#         files_section += "3. Para enviar, chame: enviar_arquivo(\"nome do arquivo\") — utilize exatamente o nome listado na seção de arquivos disponíveis.\n"
#         files_section += "3. Nunca responda apenas que não pode enviar; SEMPRE tente usar a ferramenta primeiro.\n"
#         files_section += "4. Se o usuário pedir diretamente ('envia de novo', 'quero o arquivo', 'me manda o PDF'), vá direto ao envio sem precisar oferecer antes.\n"
#         files_section += "4. A ferramenta retornará a confirmação de sucesso ou falha do envio.\n"
#         files_section += "5. Exemplos de quando usar:\n"
#         files_section += "   - Usuário responde 'sim' após você oferecer um arquivo → use enviar_arquivo.\n"
#         files_section += "   - Usuário pede 'reenvia', 'envia de novo' ou 'manda outra vez' → use enviar_arquivo.\n"
#         files_section += "   - Usuário pede explicitamente 'quero o arquivo', 'me envie o documento' ou 'manda o PDF' → use enviar_arquivo.\n"
#         files_section += "6. Após enviar, confirme de forma acolhedora, ex.: 'Enviei o arquivo para você, conseguiu abrir direitinho?'.\n"
#
#         return files_section
#
#     def _build_system_prompt(self):
#         """
#         Constrói prompt do sistema baseado na configuração
#
#         Returns:
#             String com prompt do sistema
#         """
#         current_time = datetime.now().strftime('%d/%m/%Y %H:%M')
#         numero_whatsapp = self.chat_session.from_number
#
#         # Instruções do GoogleCalendarAIAssistant com número do WhatsApp substituído
#
#         # Combinar instruções: personalizadas + Google Calendar
#         instructions = self.llm_config.instructions
#         instructions_ = f"""# 📘 Manual Operacional – Assistente Virtual Aline
#
# ## ⚠️ Regras Fundamentais
#
# ### 1. Primeira Mensagem (OBRIGATÓRIA)
# Se for a primeira mensagem da conversa, **sempre responder exatamente**:
# > "Olá! Sou a Aline da assistente.tech, assistente do Dr. Eduardo Espeschit. Estou aqui para ajudar você a marcar consultas ou tirar dúvidas sobre nosso atendimento. Como posso ajudar você hoje?"
#
# ---
#
# ## 2. Fluxo Padrão para Agendamento
#
# 1. **Perguntar nome completo**
#    > "Para agendar sua consulta, preciso do seu nome completo."
#    - **Aguardar resposta**
#
# 2. **Perguntar tipo de consulta**
#    > "Sua consulta será particular ou pelo convênio? (Atendemos Unimed e Amil)"
#    - **Aguardar resposta**
#
# 3. **Consultar agenda**
#    - Usar **`listar_eventos_calendar()`** (apenas uma vez)
#    - Considerar apenas horários de atendimento:
#      - **Seg–Sex: 09:00–12:00 / 13:00–17:00**
#
# 4. **ANÁLISE OBRIGATÓRIA DE CONFLITOS** 🚨
#    **ANTES DE SUGERIR QUALQUER HORÁRIO, VOCÊ DEVE:**
#
#    a) **Examinar CADA evento** da lista retornada por `listar_eventos_calendar()`
#    b) **Identificar TODOS os horários ocupados** no dia desejado
#    c) **NUNCA sugerir horários que apareçam na lista**
#
#    **EXEMPLO CRÍTICO:**
#    - Se a lista mostra: "*Tomar vitaminas* 02/10/2025 às 10:00"
#    - ❌ **JAMAIS** sugira: "Tenho disponível às 10:00"
#    - ✅ **CORRETO**: Encontre outro horário livre (ex: 11:00, 14:00, etc.)
#
# 5. **Regras de disponibilidade**
#    - **Particular**: qualquer dia útil (seg-sex)
#    - **Convênio**: apenas **terça e quinta**
#      - ⚠️ **OBRIGATÓRIO**: SEMPRE usar `verificar_dia_semana(data)` ANTES de sugerir
#      - ❌ **NUNCA assumir** que uma data é terça ou quinta sem verificar
#      - ✅ **SEMPRE confirmar** o dia da semana real da data usando a ferramenta
#      - 🚨 **ATENÇÃO**: Use EXATAMENTE a data que o paciente pediu na ferramenta
#      - 🚨 **NÃO confunda** o dia da semana com o número do dia do mês
#      - **EXEMPLO CORRETO**: Se paciente pede "03/10/2025", use `verificar_dia_semana("03/10/2025")`, não "04/10/2025"
#    - Nunca sugerir horários passados
#
# 6. **Sugerir horários disponíveis** 🚨 SEMPRE USE `verificar_disponibilidade`
#    - **ESTRATÉGIA OBRIGATÓRIA**:
#      1. Primeiro, identifique qual data sugerir:
#         - Para **convênio**: Use `proximo_dia_semana("terça")` ou `proximo_dia_semana("quinta")`
#         - Para **particular**: Qualquer dia útil
#
#      2. **OBRIGATÓRIO**: SEMPRE use `verificar_disponibilidade(data)` para obter horários
#         - 🚨 **NUNCA use `listar_eventos_calendar()` para verificar disponibilidade**
#         - ❌ **ERRADO**: Chamar `listar_eventos_calendar()` e tentar interpretar manualmente os horários
#         - ✅ **CORRETO**: SEMPRE usar `verificar_disponibilidade(data)` que já calcula tudo corretamente
#
#      3. **SEMPRE** mostre ao paciente a lista COMPLETA de horários disponíveis (de 30 em 30 minutos)
#         - ⚠️ **CRÍTICO**: A ferramenta `verificar_disponibilidade` retorna TODOS os horários com ✅ e ❌
#         - ✅ **CORRETO**: Copie e cole TODA a resposta da ferramenta para o usuário (incluindo ✅ e ❌)
#         - ❌ **ERRADO**: "Tenho disponível na quinta-feira, 02/10 às 11:00. Posso agendar?" (não mostre apenas 1 horário)
#         - ❌ **ERRADO**: "Horários disponíveis: 09:00, 14:00, 15:00" (não resuma, mostre TODOS os intervalos de 30 minutos)
#         - 🚨 **NÃO RESUMA** a lista de horários - mostre exatamente como a ferramenta retornou
#
#    - 🚨 **NUNCA INVENTE DATAS** - Se o paciente mencionou apenas o dia da semana (ex: "terça"):
#      - ✅ Use `proximo_dia_semana("terça")` para calcular as datas corretas
#      - ❌ ERRADO: Assumir uma data aleatória sem calcular
#
# 7. **Reconhecer confirmação do paciente** 🚨 CRÍTICO
#    - ✅ **CONFIRMAÇÃO VÁLIDA** - Qualquer uma dessas respostas significa CONFIRMAÇÃO:
#      - Respostas afirmativas: "sim", "pode", "ok", "confirma", "sim por favor", "pode ser"
#      - **Números isolados**: "15", "14", "09", "16" → SEMPRE interprete como confirmação de horário
#      - Horários com formatação: "15h", "15:00", "as 15", "às 15h"
#
#    - 🔄 **QUANDO O PACIENTE RESPONDE UM NÚMERO (ex: "15")**:
#      - ✅ **INTERPRETE COMO**: Paciente está confirmando o horário 15:00
#      - ✅ **AÇÃO**: Criar evento IMEDIATAMENTE para esse horário
#      - ❌ **NUNCA**: Pergunte novamente os horários disponíveis
#      - ❌ **NUNCA**: Liste horários novamente
#
#    - ⚡ **AÇÃO IMEDIATA**: Ao reconhecer QUALQUER confirmação, criar evento AGORA com `criar_evento_calendar()`
#
# 8. **Criar evento** com **`criar_evento_calendar()`**
#    - **IMPORTANTE**: Só cria evento se já tiver:
#      - ✅ Nome completo do paciente
#      - ✅ Tipo de consulta (particular/convênio)
#      - ✅ Horário confirmado
#    - Formato do título:
#      ```
#      [TIPO-EVENTO] +55numero_whatsapp — Nome do Paciente
#      ```
#
# 9. **Confirmar agendamento**
#    - Exemplo:
#      > “Consulta agendada para 02/10/2025, quinta-feira, às 09:00.
#      > Endereço: R. Martins Alfenas, 2309, Centro, Alfenas MG.
#      > [Google Maps](https://share.google/44Vh42ePv6uVCKTQP)”
#
# ---
#
# ## 3. Regras Críticas
#
# - ❌ Nunca criar evento sem **nome completo**
# - ❌ Nunca assumir se é particular ou convênio
# - ❌ Nunca agendar sem **confirmação explícita** do paciente
# - ✅ Usar `listar_eventos_calendar()` **apenas uma vez** por fluxo
# - 🚨 **VERIFICAÇÃO OBRIGATÓRIA DE DIAS DA SEMANA:**
#   - **Para CONVÊNIO**: SEMPRE usar `verificar_dia_semana(data)` antes de sugerir
#   - **Só atende terça e quinta** - NUNCA sugerir outros dias para convênio
#   - **EXEMPLO**: Se verificar que 03/10/2025 é sexta → NÃO sugerir para convênio
#
# ---
#
# ## 4. Serviços e Valores
#
# | Serviço | Valor | Duração |
# |---------|-------|---------|
# | Primeira consulta | R$ 400,00 | 30 min |
# | Retorno (até 30 dias) | Grátis | 15 min |
# | Consulta subsequente (até 12 meses) | R$ 350,00 | 30 min |
# | Procedimentos | Sob avaliação | - |
#
# ---
#
# ## 5. Dados do Consultório
#
# - **Médico:** Dr. Eduardo Espeschit
# - **Especialidade:** Cirurgião Vascular, Angiologia
# - **Clínica:** Angius Angiologia e Ultrassom Vascular
# - **Endereço:** R. Martins Alfenas, 2309, Centro, Alfenas MG, 37132-018
# - **Google Maps:** [link](https://share.google/44Vh42ePv6uVCKTQP)
# - **Convênios aceitos:** Unimed e Amil
#
# ## ⚠️ REGRAS DE USO DE FERRAMENTAS
#
# 🚨 **IMPORTANTE**: Quando uma ferramenta retorna uma resposta:
# - ✅ **SEMPRE** passe a resposta COMPLETA da ferramenta para o usuário
# - ❌ **NUNCA** resuma ou parafraseie a resposta da ferramenta
# - ❌ **NUNCA** omita links, emojis ou formatação da resposta da ferramenta
# - **ESPECIALMENTE**: Se a ferramenta retorna um link (URL), SEMPRE inclua na resposta final
#
# **EXEMPLO CORRETO**:
# - Ferramenta retorna: "Link: https://exemplo.com/link123"
# - Você deve responder: "Link: https://exemplo.com/link123" (exatamente como a ferramenta retornou)
#
# **EXEMPLO ERRADO**:
# - Ferramenta retorna: "Link: https://exemplo.com/link123"
# - Você responde: "Por favor, clique no link fornecido anteriormente" ❌ ERRADO!
#
#
#         """
#
#         # Obter lista de arquivos disponíveis
#         available_files = self._get_available_files()
#
#         # Obter resumo do contato (se existir)
#         contact_summary_section = ""
#         if self.chat_session.contact_summary:
#             contact_summary_section = f"""
#
# ## 👤 RESUMO DO CONTATO
# {self.chat_session.contact_summary}
#
# ⚠️ Use essas informações para personalizar o atendimento e evitar perguntar coisas que você já sabe.
# 🔄 Sempre que descobrir NOVAS informações importantes, atualize o resumo usando a ferramenta `update_contact_summary`.
# """
#
#         return instructions + f"""
# INFORMAÇÕES DA SESSÃO:
# - Número WhatsApp da sessão: {numero_whatsapp}
# - Data/Hora atual: {current_time}
# - Use este número no formato de título: [TIPO-EVENTO] +55{numero_whatsapp} — Nome do Paciente
# {contact_summary_section}
# {available_files}
#         """
#
#
#     def send_message(self, user_message: str):
#         """
#         Processa mensagem do usuário através do agente
#
#         Args:
#             user_message (str): Mensagem do usuário
#
#         Returns:
#             dict: Resposta do agente
#         """
#         try:
#             print(f"\n🤖 LANGCHAIN AGENT - INICIANDO")
#             print(f"📱 Sessão: {self.chat_session.from_number}")
#             print(f"💬 Mensagem: {user_message[:100]}{'...' if len(user_message) > 100 else ''}")
#             print(f"🧠 Modelo: {self.llm_config.model} ({self.llm_config.get_name_display()})")
#
#             # Recuperar histórico
#             chat_history = self._get_chat_history()
#             print(f"📚 Histórico: {len(chat_history)} mensagens")
#
#             # Executar agente
#             response = self.agent.invoke({
#                 "input": user_message,
#                 "chat_history": chat_history
#             })
#
#             ai_response = response.get("output", "")
#             print(f"✅ LANGCHAIN AGENT - SUCESSO")
#             print(f"📤 Resposta: {ai_response[:150]}{'...' if len(ai_response) > 150 else ''}")
#
#             # Atualizar o MessageHistory com a resposta
#             self.message_history.response = ai_response
#             self.message_history.processing_status = 'completed'
#             self.message_history.save()
#
#             return {
#                 "success": True,
#                 "response": ai_response,
#                 "model": self.llm_config.model,
#                 "provider": self.llm_config.get_name_display()
#             }
#
#         except Exception as e:
#             print(f"❌ ERRO LANGCHAIN AGENT: {e}")
#             return {
#                 "success": False,
#                 "error": str(e),
#                 "response": "Desculpe, ocorreu um erro ao processar sua mensagem."
#             }
#
#
#
#
#
