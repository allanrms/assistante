class OpenAIService:
    """
    Service para integração com OpenAI API
    """

    def __init__(self, llm_config: LLMProviderConfig):
        # Use configurações do LLMProviderConfig
        self.llm_config = llm_config
        self.api_key = getattr(settings, 'OPENAI_API_KEY', '')  # API key ainda vem do settings por segurança
        self.base_url = "https://api.openai.com/v1"

    def _get_headers(self):
        """Retorna headers para requisições à OpenAI API"""
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    # def send_text_message(self, from_number, sender_name, message_content):
    def send_text_message(self, message_content, chat_session):
        """
        Envia mensagem de texto para OpenAI e retorna a resposta

        Args:
            from_number (str): Número do remetente
            sender_name (str): Nome do remetente
            message_content (str): Conteúdo da mensagem

        Returns:
            dict: Resposta da OpenAI API ou None em caso de erro
        """
        try:
            # print(f"Enviando mensagem para OpenAI de {sender_name} ({from_number}): {message_content}")
            print(f"Enviando mensagem para OpenAI: {message_content}")

            # Recuperar últimas 10 mensagens da sessão em ordem cronológica
            last_messages = ChatHistory.objects.filter(session_id=chat_session.from_number, closed=False).order_by(
                "created_at")[:10]

            # Montar contexto do sistema com instruções estruturadas
            system_content = self._build_enhanced_system_prompt()

            # Adicionar instruções para resposta estruturada
            system_content += f"\n\n=== INSTRUÇÕES DE FORMATAÇÃO DE RESPOSTA ===\n"
            system_content += "Quando você precisar enviar tanto texto quanto um arquivo/link para o usuário, formate sua resposta EXATAMENTE assim:\n"
            system_content += '{"text": "sua mensagem aqui", "file": "https://url-do-arquivo.com/arquivo.pdf"}\n'
            system_content += "- Use APENAS esse formato JSON quando quiser enviar texto + arquivo\n"
            system_content += "- O campo 'text' deve conter sua mensagem de texto\n"
            system_content += "- O campo 'file' deve conter a URL COMPLETA do arquivo (obrigatório: http:// ou https://)\n"
            system_content += "- Para respostas apenas de texto, responda normalmente (sem JSON)\n"
            system_content += "- NUNCA use apenas nomes de arquivos como 'Cardápio.pdf' - sempre URLs completas\n"
            system_content += "- Se não tiver URL real do arquivo, NÃO use o formato JSON\n"

            # Adicionar contexto dos arquivos
            context_files_content = self._get_context_files_content()
            if context_files_content:
                system_content += f"\n\n=== CONTEXTO ADICIONAL ===\n{context_files_content}"

            # Adicionar informação sobre PDFs que serão anexados
            pdf_files = self._get_pdf_files()
            if pdf_files:
                pdf_names = [pdf.name for pdf in pdf_files]
                system_content += f"\n\n=== DOCUMENTOS PDF ANEXADOS ===\n"
                system_content += f"Os seguintes documentos PDF estão anexados nesta conversa: {', '.join(pdf_names)}\n"
                system_content += "Você pode referenciar e analisar o conteúdo destes PDFs diretamente."

            # Adicionar informação sobre imagens que serão anexadas
            image_files = self._get_image_files()
            if image_files:
                image_names = [img.name for img in image_files]
                system_content += f"\n\n=== IMAGENS ANEXADAS ===\n"
                system_content += f"As seguintes imagens estão anexadas nesta conversa: {', '.join(image_names)}\n"
                system_content += "Você pode ver e analisar o conteúdo visual destas imagens diretamente."

            # Adicionar lista de arquivos disponíveis com URLs
            available_files = self._get_available_files_with_urls()
            if available_files:
                system_content += f"\n\n=== ARQUIVOS DISPONÍVEIS PARA ENVIO ===\n"
                system_content += "Os seguintes arquivos estão disponíveis e podem ser enviados usando o formato JSON:\n"
                for file_info in available_files:
                    system_content += f"• **{file_info['name']}**: {file_info['url']}\n"
                system_content += "\nPara enviar qualquer um destes arquivos, use o formato JSON com a URL exata listada acima."

            messages_payload = [
                {
                    "role": "system",
                    "content": system_content
                }
            ]

            for msg in last_messages:
                # Garante que content e response nunca sejam None
                human_content = msg.message.get("content") or ""
                ai_response = msg.message.get("response") or ""

                if human_content.strip():
                    messages_payload.append({
                        "role": "user",
                        "content": human_content
                    })

                if ai_response.strip():
                    messages_payload.append({
                        "role": "assistant",
                        "content": ai_response
                    })

                # Adicionar a nova mensagem do usuário
            user_message_content = []

            # Adicionar texto da mensagem
            if message_content and message_content.strip():
                user_message_content.append({
                    "type": "text",
                    "text": message_content
                })

            # Adicionar imagens de contexto diretamente na mensagem (se houver)
            image_files = self._get_image_files()
            for image_file in image_files:
                try:
                    # Para imagens, enviar diretamente como image_url
                    with open(image_file.file.path, 'rb') as img_file:
                        import base64
                        image_data = base64.b64encode(img_file.read()).decode('utf-8')

                    # Detectar tipo da imagem
                    image_extension = image_file.get_file_extension().lower()
                    if image_extension in ['.jpg', '.jpeg']:
                        mime_type = 'image/jpeg'
                    elif image_extension == '.png':
                        mime_type = 'image/png'
                    elif image_extension == '.gif':
                        mime_type = 'image/gif'
                    elif image_extension == '.webp':
                        mime_type = 'image/webp'
                    else:
                        mime_type = 'image/jpeg'  # fallback

                    user_message_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_data}",
                            "detail": "high"
                        }
                    })
                    print(f"Imagem anexada: {image_file.name}")

                except Exception as e:
                    print(f"Erro ao anexar imagem {image_file.name}: {e}")

            # Garantir que PDFs sejam enviados para OpenAI e obter file_ids
            uploaded_pdfs = self.ensure_pdfs_uploaded()
            attachments = []

            if uploaded_pdfs:
                for pdf_file, file_id in uploaded_pdfs:
                    attachments.append({
                        "file_id": file_id,
                        "tools": [{"type": "file_search"}]
                    })

                print(f"{len(uploaded_pdfs)} PDF(s) anexados como files: {[f[1] for f in uploaded_pdfs]}")

            # Montar mensagem do usuário
            user_message = {
                "role": "user",
            }

            # Adicionar conteúdo
            if len(user_message_content) > 1 or (
                    len(user_message_content) == 1 and user_message_content[0]["type"] != "text"):
                user_message["content"] = user_message_content
            elif len(user_message_content) == 1:
                user_message["content"] = user_message_content[0]["text"]
            else:
                user_message["content"] = message_content or ""

            # Adicionar attachments se houver PDFs
            if attachments:
                user_message["attachments"] = attachments

            messages_payload.append(user_message)

            # Preparar o payload para a OpenAI API
            payload = {
                "model": self.llm_config.model,
                "messages": messages_payload,
                "max_tokens": self.llm_config.max_tokens,
                "temperature": self.llm_config.temperature,
                "top_p": self.llm_config.top_p,
                "presence_penalty": self.llm_config.presence_penalty,
                "frequency_penalty": self.llm_config.frequency_penalty
            }

            # create_human
            history = ChatHistory.create(session_id=chat_session.from_number, content=message_content,
                                         external_id=chat_session.id, response=None)

            # Fazer requisição para OpenAI
            url = f"{self.base_url}/chat/completions"
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                response_data = response.json()
                ai_response = response_data['choices'][0]['message']['content']

                print(f"Resposta da OpenAI: {ai_response}")

                if ai_response:
                    # Tentar processar resposta estruturada
                    processed_response = self._process_structured_response(ai_response)

                    if processed_response:
                        # Resposta estruturada processada com sucesso
                        response_msg = processed_response
                    else:
                        # Resposta simples
                        response_msg = ai_response
                else:
                    response_msg = 'Desculpe, ocorreu um erro ao processar sua mensagem.'
                    print(f"Erro no OpenAI: {ai_response}")

                history.message['response'] = response_msg if isinstance(response_msg, str) else ai_response
                history.save()

                return response_msg

            else:
                print(f"Erro na requisição para OpenAI: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {response.text}"
                }

        except Exception as e:
            print(f"Erro ao comunicar com OpenAI: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _get_context_files_content(self):
        """
        Busca e retorna o conteúdo dos arquivos de contexto ativos.
        Para PDFs, retorna apenas uma referência pois o arquivo será enviado diretamente.
        Para imagens, inclui metadados básicos.
        """
        try:
            # Buscar arquivos de contexto ativos e prontos (não PDFs, mas incluir imagens)
            context_files = AssistantContextFile.objects.filter(
                llm_config=self.llm_config,
                is_active=True,
                status='ready'
            ).exclude(file_type='pdf').order_by('name')

            if not context_files.exists():
                return ""

            context_content = []
            total_chars = 0
            max_context_length = 20000  # Limite para não exceder o contexto da API

            for file in context_files:
                # Para tipos não-PDF, usar o conteúdo extraído
                if file.extracted_content:
                    file_content = file.extracted_content.strip()

                    # Verificar se ainda há espaço no contexto
                    if total_chars + len(file_content) > max_context_length:
                        # Truncar se necessário
                        remaining_chars = max_context_length - total_chars
                        if remaining_chars > 100:  # Só incluir se sobrar espaço significativo
                            file_content = file_content[:remaining_chars] + "..."
                            context_content.append(f"**{file.name}:**\n{file_content}")
                        break

                    context_content.append(f"**{file.name}:**\n{file_content}")
                    total_chars += len(file_content) + len(file.name) + 10  # +10 para formatação

            if context_content:
                result = "\n\n".join(context_content)
                result += f"\n\n(Contexto baseado em {len(context_content)} arquivo(s) de referência)"
                return result

            return ""

        except Exception as e:
            print(f"Erro ao buscar arquivos de contexto: {e}")
            return ""

    def _get_pdf_files(self):
        """
        Busca arquivos PDF de contexto para envio direto ao modelo
        """
        try:
            pdf_files = AssistantContextFile.objects.filter(
                llm_config=self.llm_config,
                is_active=True,
                status='ready',
                file_type='pdf'
            ).order_by('name')

            return list(pdf_files)

        except Exception as e:
            print(f"Erro ao buscar arquivos PDF: {e}")
            return []

    def _get_image_files(self):
        """
        Busca arquivos de imagem de contexto para envio direto ao modelo
        """
        try:
            image_files = AssistantContextFile.objects.filter(
                llm_config=self.llm_config,
                is_active=True,
                status='ready',
                file_type__in=['jpg', 'png', 'gif', 'webp']
            ).order_by('name')

            return list(image_files)

        except Exception as e:
            print(f"Erro ao buscar arquivos de imagem: {e}")
            return []

    def upload_pdf_to_openai(self, pdf_file):
        """
        Faz upload do arquivo PDF para a OpenAI Files API
        """
        try:
            url = f"{self.base_url}/files"

            with open(pdf_file.file.path, 'rb') as f:
                files = {
                    'file': (pdf_file.file.name, f, 'application/pdf'),
                }
                data = {
                    'purpose': 'assistants'
                }

                response = requests.post(
                    url,
                    headers={'Authorization': f'Bearer {self.api_key}'},
                    files=files,
                    data=data,
                    timeout=60  # Upload pode demorar mais
                )

                if response.status_code == 200:
                    result = response.json()
                    file_id = result.get('id')

                    # Salvar o file_id no modelo
                    pdf_file.openai_file_id = file_id
                    pdf_file.save()

                    print(f"PDF {pdf_file.name} enviado para OpenAI. File ID: {file_id}")
                    return file_id
                else:
                    print(f"Erro ao fazer upload do PDF: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            print(f"Erro durante upload do PDF {pdf_file.name}: {e}")
            return None

    def ensure_pdfs_uploaded(self):
        """
        Garante que todos os PDFs de contexto estejam enviados para OpenAI
        """
        pdf_files = self._get_pdf_files()
        uploaded_files = []

        for pdf_file in pdf_files:
            if not pdf_file.openai_file_id:
                # Arquivo ainda não foi enviado
                file_id = self.upload_pdf_to_openai(pdf_file)
                if file_id:
                    uploaded_files.append((pdf_file, file_id))
            else:
                # Arquivo já foi enviado
                uploaded_files.append((pdf_file, pdf_file.openai_file_id))

        return uploaded_files

    def _get_available_files_with_urls(self):
        """
        Busca todos os arquivos de contexto ativos e suas URLs para envio
        """
        try:
            # Buscar todos os arquivos de contexto ativos e prontos
            all_files = AssistantContextFile.objects.filter(
                llm_config=self.llm_config,
                is_active=True,
                status='ready'
            ).order_by('name')

            available_files = []

            for file in all_files:
                file_info = {
                    'name': file.name,
                    'type': file.file_type,
                }

                # Tentar obter URL do arquivo
                try:
                    if hasattr(file.file, 'url'):
                        # Se o arquivo tem URL direta (ex: storage público)
                        file_url = file.file.url

                        # Converter URL relativa em absoluta se necessário
                        if file_url.startswith('/'):
                            # Construir URL absoluta usando settings
                            from django.conf import settings
                            base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
                            file_url = f"{base_url.rstrip('/')}{file_url}"

                        file_info['url'] = file_url
                        available_files.append(file_info)

                    elif hasattr(file.file, 'path'):
                        # Se só tem caminho local, criar URL baseada no Django MEDIA_URL
                        from django.conf import settings

                        # Obter o caminho relativo do arquivo
                        full_path = file.file.path
                        media_root = getattr(settings, 'MEDIA_ROOT', '')

                        if media_root and full_path.startswith(media_root):
                            relative_path = full_path[len(media_root):].lstrip('/')
                            media_url = getattr(settings, 'MEDIA_URL', '/media/')

                            # Construir URL completa
                            base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
                            file_url = f"{base_url.rstrip('/')}{media_url.rstrip('/')}/{relative_path}"

                            file_info['url'] = file_url
                            available_files.append(file_info)

                except Exception as url_error:
                    print(f"Erro ao obter URL do arquivo {file.name}: {url_error}")
                    continue

            return available_files

        except Exception as e:
            print(f"Erro ao buscar arquivos disponíveis: {e}")
            return []

    def _process_structured_response(self, ai_response):
        """
        Processa resposta da IA em formato JSON estruturado
        Formato esperado: {"text": "mensagem", "file": "url_do_arquivo"}
        """
        import json
        import re

        try:
            # Tentar encontrar JSON na resposta
            json_pattern = r'\{[^{}]*"text"[^{}]*"file"[^{}]*\}'
            json_match = re.search(json_pattern, ai_response)

            if json_match:
                json_str = json_match.group(0)
                try:
                    parsed_data = json.loads(json_str)

                    # Validar se tem os campos necessários
                    if "text" in parsed_data and "file" in parsed_data:
                        text = parsed_data.get("text", "").strip()
                        file_url = parsed_data.get("file", "").strip()

                        # Validar se ao menos um dos campos não está vazio
                        if text or file_url:
                            result = {
                                "type": "structured",
                                "text": text,
                                "file": file_url
                            }
                            print(f"Resposta estruturada detectada: texto='{text[:50]}...', arquivo='{file_url}'")
                            return result

                except json.JSONDecodeError:
                    pass

            # Tentar formato mais flexível sem JSON estrito
            text_match = re.search(r'"?text"?\s*:\s*"([^"]*)"', ai_response)
            file_match = re.search(r'"?file"?\s*:\s*"([^"]*)"', ai_response)

            if text_match or file_match:
                text = text_match.group(1) if text_match else ""
                file_url = file_match.group(1) if file_match else ""

                if text or file_url:
                    result = {
                        "type": "structured",
                        "text": text.strip(),
                        "file": file_url.strip()
                    }
                    print(f"Resposta estruturada (flexível) detectada: texto='{text[:50]}...', arquivo='{file_url}'")
                    return result

            return None

        except Exception as e:
            print(f"Erro ao processar resposta estruturada: {e}")
            return None

    def _build_enhanced_system_prompt(self):
        """
        Constrói um prompt de sistema melhorado que interpreta melhor as instruções do usuário
        """
        current_time = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

        # Começar com seção de identidade e contexto temporal
        system_prompt = f"=== CONTEXTO E IDENTIDADE ===\n"
        system_prompt += f"Data e hora atual: {current_time}\n\n"

        # Processar e estruturar as instruções do usuário
        # if self.llm_config.instructions and self.llm_config.instructions.strip():
        #     system_prompt += "=== INSTRUÇÕES PRINCIPAIS ===\n"

        # Detectar e melhorar diferentes tipos de instruções
        # enhanced_instructions = self._enhance_user_instructions(self.llm_config.instructions)
        enhanced_instructions = self.llm_config.instructions
        # system_prompt += enhanced_instructions + "\n\n"
        # else:
        # Instruções padrão se nenhuma foi fornecida
        # system_prompt += "=== INSTRUÇÕES PRINCIPAIS ===\n"
        # system_prompt += "Você é um assistente útil e prestativo. Responda de forma clara, precisa e educada às perguntas dos usuários.\n\n"

        # Adicionar diretrizes comportamentais padrão
        # system_prompt += "=== DIRETRIZES COMPORTAMENTAIS ===\n"
        # system_prompt += "• Seja sempre respeitoso e profissional\n"
        # system_prompt += "• Forneça respostas precisas e bem fundamentadas\n"
        # system_prompt += "• Se não tiver certeza sobre algo, admita e sugira alternativas\n"
        # system_prompt += "• Adapte seu tom e linguagem ao contexto da conversa\n"
        # system_prompt += "• Priorize a utilidade e clareza em suas respostas\n\n"

        return enhanced_instructions