# from datetime import datetime
# from django.conf import settings
# from django_ai_assistant import AIAssistant
# from django_ai_assistant.langchain.tools import method_tool
# from langchain_openai import ChatOpenAI
# from langchain_anthropic import ChatAnthropic
# from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain.schema import HumanMessage, AIMessage, SystemMessage
# from nodes.models import LLMProviderConfig, ChatHistory, AssistantContextFile
# from whatsapp_connector.models import ChatSession
#
#
# def create_dynamic_assistant_class(llm_config: LLMProviderConfig, assistant_id: str = None):
#     """
#     Cria uma classe AIAssistant dinâmica baseada no LLMProviderConfig
#     """
#
#     class DynamicAIAssistant(AIAssistant):
#         id = assistant_id or f"assistant_{llm_config.id}"
#         name = llm_config.display_name or f"{llm_config.get_name_display()} - {llm_config.model}"
#         instructions = llm_config.instructions or "Você é um assistente inteligente."
#         model = llm_config.model
#
#         def __init__(self):
#             self.llm_config = llm_config
#             super().__init__()
#
#         def get_llm(self):
#             """Retorna o modelo LLM configurado baseado no LLMProviderConfig"""
#             provider = self.llm_config.name
#
#             if provider == "openai":
#                 return ChatOpenAI(
#                     model=self.llm_config.model,
#                     temperature=self.llm_config.temperature,
#                     max_tokens=self.llm_config.max_tokens,
#                     top_p=self.llm_config.top_p,
#                     presence_penalty=self.llm_config.presence_penalty,
#                     frequency_penalty=self.llm_config.frequency_penalty,
#                     openai_api_key=getattr(settings, 'OPENAI_API_KEY', '')
#                 )
#             elif provider == "anthropic":
#                 return ChatAnthropic(
#                     model=self.llm_config.model,
#                     temperature=self.llm_config.temperature,
#                     max_tokens=self.llm_config.max_tokens,
#                     top_p=self.llm_config.top_p,
#                     anthropic_api_key=getattr(settings, 'ANTHROPIC_API_KEY', '')
#                 )
#             elif provider == "google":
#                 return ChatGoogleGenerativeAI(
#                     model=self.llm_config.model,
#                     temperature=self.llm_config.temperature,
#                     max_output_tokens=self.llm_config.max_tokens,
#                     top_p=self.llm_config.top_p,
#                     google_api_key=getattr(settings, 'GOOGLE_API_KEY', '')
#                 )
#             else:
#                 # Fallback para OpenAI se provider não reconhecido
#                 return ChatOpenAI(
#                     model=self.llm_config.model,
#                     temperature=self.llm_config.temperature,
#                     max_tokens=self.llm_config.max_tokens,
#                     openai_api_key=getattr(settings, 'OPENAI_API_KEY', '')
#                 )
#
#         def get_instructions(self):
#             """Retorna instruções dinâmicas com contexto atual"""
#             current_time = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
#             base_instructions = self.instructions
#
#             # Adicionar contexto de arquivos
#             context_files_content = self._get_context_files_content()
#             if context_files_content:
#                 base_instructions += f"\n\n=== CONTEXTO ADICIONAL ===\n{context_files_content}"
#
#             return f"{base_instructions}\n\nData e hora atual: {current_time}"
#
#         def _get_context_files_content(self):
#             """
#             Busca e retorna o conteúdo dos arquivos de contexto ativos
#             """
#             try:
#                 context_files = AssistantContextFile.objects.filter(
#                     llm_config=self.llm_config,
#                     is_active=True,
#                     status='ready'
#                 ).exclude(file_type='pdf').order_by('name')
#
#                 if not context_files.exists():
#                     return ""
#
#                 context_content = []
#                 total_chars = 0
#                 max_context_length = 20000
#
#                 for file in context_files:
#                     if file.extracted_content:
#                         file_content = file.extracted_content.strip()
#
#                         if total_chars + len(file_content) > max_context_length:
#                             remaining_chars = max_context_length - total_chars
#                             if remaining_chars > 100:
#                                 file_content = file_content[:remaining_chars] + "..."
#                                 context_content.append(f"**{file.name}:**\n{file_content}")
#                             break
#
#                         context_content.append(f"**{file.name}:**\n{file_content}")
#                         total_chars += len(file_content) + len(file.name) + 10
#
#                 if context_content:
#                     result = "\n\n".join(context_content)
#                     result += f"\n\n(Contexto baseado em {len(context_content)} arquivo(s) de referência)"
#                     return result
#
#                 return ""
#
#             except Exception as e:
#                 print(f"Erro ao buscar arquivos de contexto: {e}")
#                 return ""
#
#     return DynamicAIAssistant
#
#
# class DjangoAIAssistantService:
#     """
#     Service que integra LLMProviderConfig com django-ai-assistant
#     """
#
#     def __init__(self, llm_config: LLMProviderConfig, assistant_id: str = None):
#         self.llm_config = llm_config
#         # Criar uma classe dinâmica AIAssistant
#         assistant_class = create_dynamic_assistant_class(llm_config, assistant_id)
#         self.assistant = assistant_class()
#
#     def get_llm(self):
#         """Delegate para o assistant interno"""
#         return self.assistant.get_llm()
#
#     def get_instructions(self):
#         """Delegate para o assistant interno"""
#         return self.assistant.get_instructions()
#
# class AgentLLMService:
#     """
#     Service principal que gerencia diferentes provedores LLM usando django-ai-assistant
#     """
#
#     def __init__(self, llm_config: LLMProviderConfig):
#         self.llm_config = llm_config
#         self.assistant = DjangoAIAssistantService(llm_config)
#
#     def send_text_message(self, message_content: str, chat_session):
#         """
#         Envia mensagem de texto usando django-ai-assistant com todas as funcionalidades do OpenAIService
#
#         Args:
#             message_content (str): Conteúdo da mensagem
#             chat_session: Sessão do chat
#
#         Returns:
#             dict: Resposta do assistant ou None em caso de erro
#         """
#         try:
#             print(f"Enviando mensagem via AgentLLMService: {message_content}")
#
#             # VERIFICAR STATUS DA SESSÃO - Não responder se não permitir AI
#             if hasattr(chat_session, 'allows_ai_response') and not chat_session.allows_ai_response():
#                 print(f"🚫 FILTRADO: Sessão {chat_session.from_number} não permite resposta do AI (status: {chat_session.status}) - Assistant não irá responder")
#                 return None
#
#             # Recuperar últimas 10 mensagens da sessão em ordem cronológica
#             last_messages = ChatHistory.objects.filter(session_id=chat_session.from_number, closed=False).order_by("created_at")[:10]
#
#             # PRIMEIRO: Verificar se é uma solicitação relacionada a calendário
#             # calendar_response = self._try_calendar_assistant(message_content, chat_session, last_messages)
#             # if calendar_response:
#             #     return calendar_response
#
#             # SEGUNDO: Verificar se é uma solicitação relacionada a finanças
#             # finance_response = self._try_finance_assistant(message_content, chat_session, last_messages)
#             # if finance_response:
#             #     return finance_response
#
#             # Montar contexto do sistema com instruções estruturadas
#             system_content = self._build_enhanced_system_prompt()
#
#             # Adicionar instruções para resposta estruturada
#             # system_content += f"\n\n=== INSTRUÇÕES DE FORMATAÇÃO DE RESPOSTA ===\n"
#             # system_content += "Quando você precisar enviar tanto texto quanto um arquivo/link para o usuário, formate sua resposta EXATAMENTE assim:\n"
#             # system_content += '{"text": "sua mensagem aqui", "file": "https://url-do-arquivo.com/arquivo.pdf"}\n'
#             # system_content += "- Use APENAS esse formato JSON quando quiser enviar texto + arquivo\n"
#             # system_content += "- O campo 'text' deve conter sua mensagem de texto\n"
#             # system_content += "- O campo 'file' deve conter a URL COMPLETA do arquivo (obrigatório: http:// ou https://)\n"
#             # system_content += "- Para respostas apenas de texto, responda normalmente (sem JSON)\n"
#             # system_content += "- NUNCA use apenas nomes de arquivos como 'Cardápio.pdf' - sempre URLs completas\n"
#             # system_content += "- Se não tiver URL real do arquivo, NÃO use o formato JSON\n"
#
#
#
#             # Adicionar contexto dos arquivos
#             context_files_content = self._get_context_files_content()
#             if context_files_content:
#                 system_content += f"\n\n=== CONTEXTO ADICIONAL ===\n{context_files_content}"
#
#             # Adicionar informação sobre PDFs que serão anexados
#             pdf_files = self._get_pdf_files()
#             if pdf_files:
#                 pdf_names = [pdf.name for pdf in pdf_files]
#                 system_content += f"\n\n=== DOCUMENTOS PDF ANEXADOS ===\n"
#                 system_content += f"Os seguintes documentos PDF estão anexados nesta conversa: {', '.join(pdf_names)}\n"
#                 system_content += "Você pode referenciar e analisar o conteúdo destes PDFs diretamente."
#
#             # Adicionar informação sobre imagens que serão anexadas
#             image_files = self._get_image_files()
#             if image_files:
#                 image_names = [img.name for img in image_files]
#                 system_content += f"\n\n=== IMAGENS ANEXADAS ===\n"
#                 system_content += f"As seguintes imagens estão anexadas nesta conversa: {', '.join(image_names)}\n"
#                 system_content += "Você pode ver e analisar o conteúdo visual destas imagens diretamente."
#
#             # Adicionar lista de arquivos disponíveis com URLs
#             available_files = self._get_available_files_with_urls()
#             if available_files:
#                 system_content += f"\n\n=== ARQUIVOS DISPONÍVEIS PARA ENVIO ===\n"
#                 system_content += "Os seguintes arquivos estão disponíveis e podem ser enviados usando o formato JSON:\n"
#                 for file_info in available_files:
#                     system_content += f"• **{file_info['name']}**: {file_info['url']}\n"
#                 system_content += "\nPara enviar qualquer um destes arquivos, use o formato JSON com a URL exata listada acima."
#
#
#             system_content += """
#             Se o cliente mencionar algo relacionado à agenda (como marcar reunião, marcar consulta, cancelar, desmarcar, remarcar, alterar horário ou verificar disponibilidade),
#             responda sempre no formato:
#             'AGENDAR: <detalhes da solicitação do cliente>'
#
#             Exemplos:
#             - 'AGENDAR: Marcar consulta amanhã às 15h com o Dr. João'
#             - 'AGENDAR: Cancelar consulta de segunda às 10h'
#             - 'AGENDAR: Remarcar consulta para quarta às 14h'
#             - 'AGENDAR: Mostrar horários livres para esta semana'
#
#             Caso contrário, apenas converse normalmente e responda sem acionar o agendamento.
#             """
#
#             # Preparar mensagens usando LangChain format
#             messages = []
#
#             # Adicionar instruções do sistema
#             from langchain.schema import SystemMessage, HumanMessage, AIMessage
#             messages.append(SystemMessage(content=system_content))
#
#             # Adicionar histórico de mensagens
#             for msg in last_messages:
#                 # Garante que content e response nunca sejam None
#                 human_content = msg.message.get("content") or ""
#                 ai_response = msg.message.get("response") or ""
#
#                 if human_content.strip():
#                     messages.append(HumanMessage(content=human_content))
#
#                 if ai_response.strip():
#                     messages.append(AIMessage(content=ai_response))
#
#             # Preparar conteúdo da mensagem atual (com suporte a imagens)
#             user_message_content = []
#
#             # Adicionar texto da mensagem
#             if message_content and message_content.strip():
#                 user_message_content.append({
#                     "type": "text",
#                     "text": message_content
#                 })
#
#             # Para suporte a imagens no LangChain, precisamos usar ChatOpenAI com vision
#             current_message_content = message_content
#
#             # Se há imagens, precisamos usar um formato especial para o LangChain
#             image_files = self._get_image_files()
#             if image_files:
#                 # Para LangChain, vamos incluir referência às imagens no texto
#                 image_refs = []
#                 for img in image_files:
#                     image_refs.append(f"[IMAGEM ANEXADA: {img.name}]")
#
#                 if image_refs:
#                     current_message_content += f"\n\nImagens anexadas: {', '.join(image_refs)}"
#
#             # Adicionar mensagem atual
#             if current_message_content and current_message_content.strip():
#                 messages.append(HumanMessage(content=current_message_content))
#
#             # Criar histórico da mensagem humana
#             history = ChatHistory.create(
#                 session_id=chat_session.from_number,
#                 content=message_content,
#                 external_id=chat_session.id,
#                 response=None
#             )
#
#             # Usar django-ai-assistant LLM para processar
#             llm = self.assistant.get_llm()
#
#             # Enviar para o LLM
#             response = llm.invoke(messages)
#             ai_response = response.content
#
#             print(f'ai_response: {ai_response}')
#
#             if ai_response.startswith("AGENDAR:"):
#                 print(f'_try_calendar_assistant: {ai_response.startswith("AGENDAR:")}')
#
#                 detalhes = ai_response.replace("AGENDAR:", "").strip()
#                 resultado = self._try_calendar_assistant(f"Agende a seguinte consulta: {detalhes}", chat_session, last_messages)
#                 return f"{resultado}"
#
#             print(f"Resposta do django-ai-assistant: {ai_response}")
#
#             # Processar resposta estruturada
#             if ai_response:
#                 # Tentar processar resposta estruturada
#                 processed_response = self._process_structured_response(ai_response)
#
#                 if processed_response:
#                     # Resposta estruturada processada com sucesso
#                     response_msg = processed_response
#                 else:
#                     # Resposta simples
#                     response_msg = ai_response
#             else:
#                 response_msg = 'Desculpe, ocorreu um erro ao processar sua mensagem.'
#                 print(f"Erro no LLM: {ai_response}")
#
#             # Salvar resposta no histórico
#             history.message['response'] = response_msg if isinstance(response_msg, str) else ai_response
#             history.save()
#
#             print(f'response_msg: {response_msg}')
#
#             return response_msg
#
#         except Exception as e:
#             print(f"Erro ao comunicar via django-ai-assistant: {e}")
#             return {
#                 'success': False,
#                 'error': str(e)
#             }
#
#     # Manter método send_message para compatibilidade
#     def send_message(self, message_content: str, chat_session, context_data: dict = None):
#         """Método de compatibilidade que chama send_text_message"""
#         return self.send_text_message(message_content, chat_session)
#
#     def _build_message_history(self, chat_session, current_message):
#         """
#         Constrói histórico de mensagens no formato LangChain
#         """
#         messages = []
#
#         # Adicionar instruções do sistema
#         system_instructions = self.assistant.get_instructions()
#         if system_instructions:
#             messages.append(SystemMessage(content=system_instructions))
#
#         # Recuperar últimas mensagens da sessão
#         last_messages = ChatHistory.objects.filter(
#             session_id=chat_session.from_number,
#             closed=False
#         ).order_by("created_at")[:10]
#
#         # Adicionar mensagens do histórico
#         for msg in last_messages:
#             human_content = msg.message.get("content") or ""
#             ai_response = msg.message.get("response") or ""
#
#             if human_content.strip():
#                 messages.append(HumanMessage(content=human_content))
#
#             if ai_response.strip():
#                 messages.append(AIMessage(content=ai_response))
#
#         # Adicionar mensagem atual
#         if current_message and current_message.strip():
#             messages.append(HumanMessage(content=current_message))
#
#         return messages
#
#     def _get_context_files_content(self):
#         """
#         Busca e retorna o conteúdo dos arquivos de contexto ativos
#         """
#         try:
#             context_files = AssistantContextFile.objects.filter(
#                 llm_config=self.llm_config,
#                 is_active=True,
#                 status='ready'
#             ).exclude(file_type='pdf').order_by('name')
#
#             if not context_files.exists():
#                 return ""
#
#             context_content = []
#             total_chars = 0
#             max_context_length = 20000
#
#             for file in context_files:
#                 if file.extracted_content:
#                     file_content = file.extracted_content.strip()
#
#                     if total_chars + len(file_content) > max_context_length:
#                         remaining_chars = max_context_length - total_chars
#                         if remaining_chars > 100:
#                             file_content = file_content[:remaining_chars] + "..."
#                             context_content.append(f"**{file.name}:**\n{file_content}")
#                         break
#
#                     context_content.append(f"**{file.name}:**\n{file_content}")
#                     total_chars += len(file_content) + len(file.name) + 10
#
#             if context_content:
#                 result = "\n\n".join(context_content)
#                 result += f"\n\n(Contexto baseado em {len(context_content)} arquivo(s) de referência)"
#                 return result
#
#             return ""
#
#         except Exception as e:
#             print(f"Erro ao buscar arquivos de contexto: {e}")
#             return ""
#
#     @method_tool
#     def list_context_files(self) -> str:
#         """
#         Lista arquivos de contexto disponíveis para o assistant
#
#         Returns:
#             String com lista de arquivos de contexto
#         """
#         try:
#             files = AssistantContextFile.objects.filter(
#                 llm_config=self.llm_config,
#                 is_active=True,
#                 status='ready'
#             ).order_by('name')
#
#             if not files.exists():
#                 return "Nenhum arquivo de contexto disponível."
#
#             file_list = ["📁 **Arquivos de Contexto Disponíveis:**\n"]
#
#             for i, file in enumerate(files, 1):
#                 file_info = f"{i}. **{file.name}** ({file.get_file_type_display()})"
#                 if file.file_size:
#                     file_info += f" - {file.get_file_size_display()}"
#                 file_list.append(file_info)
#
#             return "\n".join(file_list)
#
#         except Exception as e:
#             return f"Erro ao listar arquivos: {str(e)}"
#
#     @method_tool
#     def get_llm_config_info(self) -> str:
#         """
#         Retorna informações sobre a configuração LLM atual
#
#         Returns:
#             String com informações da configuração
#         """
#         try:
#             config_info = f"""🤖 **Configuração LLM Atual:**
#
#                             📋 **Nome:** {self.llm_config.display_name}
#                             🏭 **Provedor:** {self.llm_config.get_name_display()}
#                             🧠 **Modelo:** {self.llm_config.model}
#                             🌡️ **Temperatura:** {self.llm_config.temperature}
#                             📏 **Max Tokens:** {self.llm_config.max_tokens}
#                             🎯 **Top-p:** {self.llm_config.top_p}
#                             ⚖️ **Penalidade Presença:** {self.llm_config.presence_penalty}
#                             🔄 **Penalidade Frequência:** {self.llm_config.frequency_penalty}
#                             📝 **Criado em:** {self.llm_config.created_at.strftime('%d/%m/%Y %H:%M')}"""
#
#             return config_info
#
#         except Exception as e:
#             return f"Erro ao obter informações da configuração: {str(e)}"
#
#
#     def _get_pdf_files(self):
#         """
#         Busca arquivos PDF de contexto para envio direto ao modelo
#         """
#         try:
#             pdf_files = AssistantContextFile.objects.filter(
#                 llm_config=self.llm_config,
#                 is_active=True,
#                 status='ready',
#                 file_type='pdf'
#             ).order_by('name')
#
#             return list(pdf_files)
#
#         except Exception as e:
#             print(f"Erro ao buscar arquivos PDF: {e}")
#             return []
#
#     def _get_image_files(self):
#         """
#         Busca arquivos de imagem de contexto para envio direto ao modelo
#         """
#         try:
#             image_files = AssistantContextFile.objects.filter(
#                 llm_config=self.llm_config,
#                 is_active=True,
#                 status='ready',
#                 file_type__in=['jpg', 'png', 'gif', 'webp']
#             ).order_by('name')
#
#             return list(image_files)
#
#         except Exception as e:
#             print(f"Erro ao buscar arquivos de imagem: {e}")
#             return []
#
#     def _get_available_files_with_urls(self):
#         """
#         Busca todos os arquivos de contexto ativos e suas URLs para envio
#         """
#         try:
#             # Buscar todos os arquivos de contexto ativos e prontos
#             all_files = AssistantContextFile.objects.filter(
#                 llm_config=self.llm_config,
#                 is_active=True,
#                 status='ready'
#             ).order_by('name')
#
#             available_files = []
#
#             for file in all_files:
#                 file_info = {
#                     'name': file.name,
#                     'type': file.file_type,
#                 }
#
#                 # Tentar obter URL do arquivo
#                 try:
#                     if hasattr(file.file, 'url'):
#                         # Se o arquivo tem URL direta (ex: storage público)
#                         file_url = file.file.url
#
#                         # Converter URL relativa em absoluta se necessário
#                         if file_url.startswith('/'):
#                             # Construir URL absoluta usando settings
#                             from django.conf import settings
#                             base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
#                             file_url = f"{base_url.rstrip('/')}{file_url}"
#
#                         file_info['url'] = file_url
#                         available_files.append(file_info)
#
#                     elif hasattr(file.file, 'path'):
#                         # Se só tem caminho local, criar URL baseada no Django MEDIA_URL
#                         from django.conf import settings
#
#                         # Obter o caminho relativo do arquivo
#                         full_path = file.file.path
#                         media_root = getattr(settings, 'MEDIA_ROOT', '')
#
#                         if media_root and full_path.startswith(media_root):
#                             relative_path = full_path[len(media_root):].lstrip('/')
#                             media_url = getattr(settings, 'MEDIA_URL', '/media/')
#
#                             # Construir URL completa
#                             base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
#                             file_url = f"{base_url.rstrip('/')}{media_url.rstrip('/')}/{relative_path}"
#
#                             file_info['url'] = file_url
#                             available_files.append(file_info)
#
#                 except Exception as url_error:
#                     print(f"Erro ao obter URL do arquivo {file.name}: {url_error}")
#                     continue
#
#             return available_files
#
#         except Exception as e:
#             print(f"Erro ao buscar arquivos disponíveis: {e}")
#             return []
#
#     def _process_structured_response(self, ai_response):
#         """
#         Processa resposta da IA em formato JSON estruturado
#         Formato esperado: {"text": "mensagem", "file": "url_do_arquivo"}
#         """
#         import json
#         import re
#
#         try:
#             # Tentar encontrar JSON na resposta
#             json_pattern = r'\{[^{}]*"text"[^{}]*"file"[^{}]*\}'
#             json_match = re.search(json_pattern, ai_response)
#
#             if json_match:
#                 json_str = json_match.group(0)
#                 try:
#                     parsed_data = json.loads(json_str)
#
#                     # Validar se tem os campos necessários
#                     if "text" in parsed_data and "file" in parsed_data:
#                         text = parsed_data.get("text", "").strip()
#                         file_url = parsed_data.get("file", "").strip()
#
#                         # Validar se ao menos um dos campos não está vazio
#                         if text or file_url:
#                             result = {
#                                 "type": "structured",
#                                 "text": text,
#                                 "file": file_url
#                             }
#                             print(f"Resposta estruturada detectada: texto='{text[:50]}...', arquivo='{file_url}'")
#                             return result
#
#                 except json.JSONDecodeError:
#                     pass
#
#             # Tentar formato mais flexível sem JSON estrito
#             text_match = re.search(r'"?text"?\s*:\s*"([^"]*)"', ai_response)
#             file_match = re.search(r'"?file"?\s*:\s*"([^"]*)"', ai_response)
#
#             if text_match or file_match:
#                 text = text_match.group(1) if text_match else ""
#                 file_url = file_match.group(1) if file_match else ""
#
#                 if text or file_url:
#                     result = {
#                         "type": "structured",
#                         "text": text.strip(),
#                         "file": file_url.strip()
#                     }
#                     print(f"Resposta estruturada (flexível) detectada: texto='{text[:50]}...', arquivo='{file_url}'")
#                     return result
#
#             return None
#
#         except Exception as e:
#             print(f"Erro ao processar resposta estruturada: {e}")
#             return None
#
#     def _build_enhanced_system_prompt(self):
#         """
#         Constrói um prompt de sistema melhorado que interpreta melhor as instruções do usuário
#         """
#         current_time = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
#
#         # Começar com seção de identidade e contexto temporal
#         system_prompt = f"=== CONTEXTO E IDENTIDADE ===\n"
#         system_prompt += f"Data e hora atual: {current_time}\n\n"
#
#         # Processar e estruturar as instruções do usuário
#         enhanced_instructions = self.llm_config.instructions+system_prompt or "Você é um assistente inteligente."
#
#         return enhanced_instructions
#
#     def _enhance_user_instructions(self, raw_instructions):
#         """
#         Analisa e melhora as instruções fornecidas pelo usuário para torná-las mais efetivas
#         """
#         instructions = raw_instructions.strip()
#
#         # Detectar padrões comuns e adicionar estrutura
#         enhanced = ""
#
#         # Se as instruções contêm características de personalidade
#         if any(keyword in instructions.lower() for keyword in ['você é', 'atue como', 'comporte-se', 'seja', 'comportamento']):
#             enhanced += "IDENTIDADE E PERSONALIDADE:\n"
#             enhanced += f"{instructions}\n\n"
#
#             enhanced += "APLICAÇÃO DAS INSTRUÇÕES:\n"
#             enhanced += "• Mantenha essa identidade consistentemente durante toda a conversa\n"
#             enhanced += "• Todas as suas respostas devem refletir essa personalidade\n"
#             enhanced += "• Se houver conflito entre instruções, priorize o comportamento descrito acima\n"
#
#         # Se as instruções contêm procedimentos ou regras específicas
#         elif any(keyword in instructions.lower() for keyword in ['sempre', 'nunca', 'quando', 'se', 'deve', 'não deve', 'regra', 'procedimento']):
#             enhanced += "REGRAS E PROCEDIMENTOS:\n"
#             enhanced += f"{instructions}\n\n"
#
#             enhanced += "CUMPRIMENTO DAS REGRAS:\n"
#             enhanced += "• Siga rigorosamente todas as regras listadas acima\n"
#             enhanced += "• Verifique cada resposta antes de enviá-la para garantir conformidade\n"
#             enhanced += "• Em caso de dúvida, peça esclarecimentos ao usuário\n"
#
#         # Se as instruções contêm conhecimento específico ou especialização
#         elif any(keyword in instructions.lower() for keyword in ['especialista', 'conhecimento', 'área', 'domínio', 'expert', 'foco']):
#             enhanced += "ÁREA DE ESPECIALIZAÇÃO:\n"
#             enhanced += f"{instructions}\n\n"
#
#             enhanced += "APLICAÇÃO DO CONHECIMENTO ESPECIALIZADO:\n"
#             enhanced += "• Use seu conhecimento especializado para fornecer respostas detalhadas e precisas\n"
#             enhanced += "• Cite fontes ou referências quando apropriado\n"
#             enhanced += "• Explique conceitos complexos de forma acessível quando necessário\n"
#
#         # Caso geral - instruções simples ou outras
#         else:
#             enhanced += "INSTRUÇÕES PERSONALIZADAS:\n"
#             enhanced += f"{instructions}\n\n"
#
#             enhanced += "INTERPRETAÇÃO E APLICAÇÃO:\n"
#             enhanced += "• Interprete essas instruções de forma ampla e consistente\n"
#             enhanced += "• Aplique o espírito das instruções, não apenas a letra\n"
#             enhanced += "• Adapte sua abordagem conforme necessário para cumprir os objetivos\n"
#
#         # Adicionar lembretes importantes
#         enhanced += "\nLEMBRETE IMPORTANTE:\n"
#         enhanced += "Estas instruções têm prioridade sobre comportamentos padrão. Certifique-se de que cada resposta está alinhada com as diretrizes acima."
#
#         return enhanced
#
#     def _try_calendar_assistant(self, message_content: str, chat_session:ChatSession, last_messages=None):
#         """
#         Processa mensagens relacionadas a calendário usando GoogleCalendarAIAssistant
#
#         Args:
#             message_content (str): Conteúdo da mensagem
#             chat_session: Sessão do chat
#             last_messages: Últimas mensagens da conversa para contexto
#
#         Returns:
#             str ou None: Resposta da IA de calendário se aplicável, None caso contrário
#         """
#         try:
#             print(f"🗓️ Processando solicitação de calendário: {message_content[:100]}...")
#
#             # Usar django_ai_assistant thread management (seguindo padrão do _try_finance_assistant)
#             from django_ai_assistant.models import Thread
#
#             # Buscar ou criar thread para o usuário
#             thread, created = Thread.objects.get_or_create(
#                 name=f"calendar_thread_{chat_session.from_number}"
#             )
#
#             if created:
#                 print(f"🧵 Nova thread de calendário criada: {thread.id}")
#             else:
#                 print(f"🧵 Usando thread de calendário existente: {thread.id}")
#
#         except Exception as thread_error:
#             print(f"❌ Erro ao criar/buscar thread: {thread_error}")
#             import traceback
#             traceback.print_exc()
#             return None
#
#         # Criar instância do GoogleCalendarAIAssistant
#         try:
#             from google_calendar.ai_assistants import GoogleCalendarAIAssistant
#             calendar_assistant = GoogleCalendarAIAssistant()
#         except Exception as assistant_error:
#             print(f"❌ Erro ao criar GoogleCalendarAIAssistant: {assistant_error}")
#             return None
#
#         # Preparar mensagens no formato LangChain (similar ao send_text_message)
#         messages = []
#
#         # Adicionar histórico de mensagens
#         if last_messages and chat_session.messages.exists():
#             print(f"💬 Adicionando contexto de {last_messages.count()} mensagens anteriores")
#
#             for msg in chat_session.messages.all():
#                 user_msg = msg.content
#                 ai_msg = msg.response
#
#                 if user_msg and user_msg.strip():
#                     messages.append(HumanMessage(content=user_msg))
#                 if ai_msg and ai_msg.strip():
#                     messages.append(AIMessage(content=ai_msg))
#
#         # Adicionar mensagem atual
#         if message_content and message_content.strip():
#             messages.append(HumanMessage(content=message_content))
#
#         print(f"🗓️ Processando mensagem de calendário via LLM diretamente...")
#
#         # Processar com LLM diretamente usando padrão llm.invoke(messages)
#         try:
#             # Usar o LLM diretamente como no send_text_message
#             llm = calendar_assistant.get_llm()
#
#             # Enviar para o LLM usando o padrão invoke
#             response = llm.invoke(messages)
#             ai_response = response.content
#
#             if ai_response and isinstance(ai_response, str) and ai_response.strip():
#                 print(f"✅ Resposta da IA de calendário: {ai_response[:100]}...")
#
#                 # Criar histórico da mensagem
#                 history = ChatHistory.create(
#                     session_id=chat_session.from_number,
#                     content=message_content,
#                     external_id=chat_session.id,
#                     response=ai_response
#                 )
#
#                 return ai_response
#             else:
#                 print("❌ IA de calendário não retornou resposta válida")
#                 return None
#
#         except Exception as run_error:
#             print(f"❌ Erro ao executar IA de calendário: {run_error}")
#             import traceback
#             traceback.print_exc()
#             return None
#
#     def _try_finance_assistant(self, message_content: str, chat_session, last_messages=None):
#         """
#         Verifica se a mensagem é relacionada a finanças e usa FinanceAIAssistant se necessário
#
#         Args:
#             message_content (str): Conteúdo da mensagem
#             chat_session: Sessão do chat
#             last_messages: Últimas mensagens da conversa para contexto
#
#         Returns:
#             str ou None: Resposta da IA de finanças se aplicável, None caso contrário
#         """
#         try:
#             # Normalizar texto para análise
#             import re
#             normalized_text = re.sub(r'\s+', ' ', message_content.lower().strip())
#
#             # Palavras-chave que indicam interesse em finanças
#             finance_keywords = [
#                 # Comandos de registro
#                 'registrar gasto', 'registrar despesa', 'registrar receita', 'adicionar gasto',
#                 'adicionar despesa', 'adicionar receita', 'gastei', 'recebi', 'paguei',
#                 'comprei', 'vendi', 'transferi', 'depositei', 'saquei',
#
#                 # Comandos de listagem
#                 'meus gastos', 'minhas despesas', 'minhas receitas', 'movimentações',
#                 'extrato', 'listar gastos', 'listar despesas', 'listar receitas',
#                 'ver gastos', 'ver despesas', 'consultar gastos', 'gastos do mês',
#
#                 # Comandos de saldo
#                 'meu saldo', 'saldo total', 'quanto gastei', 'quanto recebi',
#                 'saldo por categoria', 'resumo financeiro', 'balanço', 'total',
#
#                 # Palavras relacionadas a dinheiro
#                 'dinheiro', 'real', 'reais', 'grana', 'bufunfa', 'valor', 'quantia',
#                 'pagamento', 'conta', 'fatura', 'boleto',
#
#                 # Categorias comuns
#                 'alimentação', 'transporte', 'moradia', 'saúde', 'educação',
#                 'lazer', 'compras', 'salário', 'freelance', 'investimento',
#                 'mercado', 'supermercado', 'farmácia', 'combustível', 'uber',
#
#                 # Comandos de categorias
#                 'criar categoria', 'nova categoria', 'categorias', 'segmentar',
#
#                 # Palavras financeiras gerais
#                 'finança', 'financeiro', 'economia', 'poupar', 'economizar',
#                 'orçamento', 'planejamento', 'controle financeiro',
#
#                 # Símbolos monetários
#                 'r$', 'rs', '$'
#             ]
#
#             # Verificar se a mensagem contém palavras-chave de finanças
#             finance_match = any(keyword in normalized_text for keyword in finance_keywords)
#
#             # Verificar se contém padrões monetários
#             money_patterns = [
#                 r'r\$\s*\d+', r'rs\s*\d+', r'\d+\s*reais?', r'\d+\s*real',
#                 r'\d+[,\.]\d+', r'gast[ei|ou]', r'pagu[ei|ou]', r'receb[i|eu]'
#             ]
#             money_match = any(re.search(pattern, normalized_text) for pattern in money_patterns)
#
#             if not (finance_match or money_match):
#                 return None
#
#             print(f"🔍 Detectada solicitação de finanças: {message_content[:100]}...")
#
#             # Usar django_ai_assistant thread management
#             from django_ai_assistant.models import Thread
#
#             # Buscar ou criar thread para o usuário
#             thread, created = Thread.objects.get_or_create(
#                 name=f"finance_thread_{chat_session.from_number}"
#             )
#
#             if created:
#                 print(f"🧵 Nova thread de finanças criada: {thread.id}")
#             else:
#                 print(f"🧵 Usando thread de finanças existente: {thread.id}")
#
#             # Importar e usar o assistant de finanças
#             from finance.ai_assistants import FinanceAIAssistant
#
#             finance_assistant = FinanceAIAssistant()
#
#             # Preparar mensagem com contexto se disponível
#             contextualized_message = message_content
#
#             if last_messages and last_messages.exists():
#                 print(f"💬 Adicionando contexto de {last_messages.count()} mensagens anteriores")
#
#                 context_messages = []
#                 for msg in last_messages:
#                     if msg.message_content and len(msg.message_content.strip()) > 0:
#                         role = "Usuário" if msg.role == "user" else "Assistente"
#                         context_messages.append(f"{role}: {msg.message_content}")
#
#                 if context_messages:
#                     context = "\n".join(context_messages[-5:])  # Últimas 5 mensagens
#                     contextualized_message = f"Contexto da conversa:\n{context}\n\nMensagem atual: {message_content}"
#
#             print(f"💰 Processando mensagem de finanças via FinanceAIAssistant...")
#
#             # Processar com o assistant de finanças
#             ai_response = finance_assistant.run(contextualized_message, thread_id=thread.id)
#
#             print(f"✅ Resposta do assistant de finanças gerada: {len(ai_response)} caracteres")
#
#             # Salvar na conversa
#             if hasattr(chat_session, 'from_number'):
#                 ChatHistory.objects.create(
#                     session_id=chat_session.from_number,
#                     role="user",
#                     message_content=message_content
#                 )
#
#                 ChatHistory.objects.create(
#                     session_id=chat_session.from_number,
#                     role="assistant",
#                     message_content=ai_response,
#                     llm_config=self.llm_config
#                 )
#
#             return ai_response
#
#         except ImportError as e:
#             print(f"❌ Erro de importação em _try_finance_assistant: {e}")
#             return None
#         except Exception as e:
#             print(f"❌ Erro geral em _try_finance_assistant: {e}")
#             import traceback
#             traceback.print_exc()
#             return None
#
#
# # Factory function para criar services baseados no provider
# def create_llm_service(llm_config: LLMProviderConfig, use_django_ai_assistant: bool = True):
#     """
#     Factory function para criar o service apropriado baseado na configuração LLM
#
#     Args:
#         llm_config: Configuração do LLM
#         use_django_ai_assistant: Se deve usar django-ai-assistant (padrão: True)
#
#     Returns:
#         Service instance apropriado
#     """
#     if use_django_ai_assistant:
#         return AgentLLMService(llm_config)
#     else:
#         # Fallback para service legado
#         # return OpenAIService(llm_config)
#         return None