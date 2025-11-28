from datetime import datetime
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from agents.langchain.agente import ask_agent
from agents.models import Message, Conversation
from whatsapp_connector.models import EvolutionInstance
from whatsapp_connector.services import ImageProcessingService, EvolutionAPIService
from whatsapp_connector.utils import transcribe_audio_from_bytes, clean_number_whatsapp
import logging

logger = logging.getLogger(__name__)

# Configurar loggers específicos
langchain_logger = logging.getLogger('assistante.langchain_agent')
media_logger = logging.getLogger('assistante.media_processing')
webhook_logger = logging.getLogger('assistante.webhook')


# @method_decorator(csrf_exempt, name='dispatch')
class EvolutionWebhookView(APIView):
    permission_classes = (AllowAny,)
    
    def post(self, request, *args, **kwargs):
        """
        Handle incoming webhooks from Evolution API
        """
        try:
            # 1️⃣ Ler os dados do request
            try:
                data = request.data
            except Exception as data_error:
                return Response({'error': 'Failed to parse request data'}, status=400)

            # Filtrar mensagens que não precisam ser processadas
            key_data = data.get('key', {})
            remote_jid = key_data.get('remoteJid', '')
            from_me = key_data.get('fromMe', False)
            message_type = data.get('messageType', '')

            if remote_jid in ['status@broadcast'] or message_type in ['group']:
                # Responde rápido antes de qualquer parse/log/download
                return Response({'status': 'ignored', 'reason': f'{remote_jid} / {message_type}'}, status=200)

            # Validate webhook data
            if not self._validate_webhook_data(data):
                return Response(
                    {'error': 'Invalid webhook data'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Extract message data
            try:
                message_data = self._extract_message_data(data)
            except Exception as extract_error:
                logger.error(f"Erro ao extrair message data: {extract_error}", exc_info=True)
                return Response(
                    {'status': 'error', 'reason': 'Failed to extract message data'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            if not message_data:
                return Response(
                    {'status': 'ignored', 'reason': 'Not a valid message'},
                    status=status.HTTP_200_OK
                )

            message_id = message_data.get('message_id')

            # ✅ DEDUPLICAÇÃO: Verificar se mensagem já foi processada (com try/except para cache)
            try:
                cache_key = f"webhook_msg_{message_id}"
                if cache.get(cache_key):
                    return Response({
                        'status': 'ignored',
                        'reason': 'Mensagem duplicada'
                    }, status=status.HTTP_200_OK)

                # Marcar como processada por 5 minutos (300 segundos)
                cache.set(cache_key, True, 300)
            except Exception as cache_error:
                # Continuar mesmo sem cache
                pass

            # Get Evolution instance
            evolution_instance = self._get_evolution_instance(message_data)

            # Verifique se a instância está ativa
            if evolution_instance and not evolution_instance.is_active:
                return Response({
                    'status': 'ignored',
                    'reason': 'Instância está inativa'
                }, status=status.HTTP_200_OK)

            # Validar autorização
            from_number = clean_number_whatsapp(message_data['from_number'])
            if evolution_instance and not evolution_instance.is_number_authorized(from_number):
                return Response({
                    'status': 'unauthorized',
                    'reason': f'Número {from_number} não autorizado'
                }, status=status.HTTP_200_OK)

            # Save message to database
            message = self._save_message(message_data, evolution_instance)

            if message.conversation.status == 'human':
                message.processing_status = "completed"
                message.responded_by = message.conversation.status
                message.response = "resposta será gerada por humano"
                message.save()
                return Response({
                    'status': 'success',
                    'message': '',
                }, status=status.HTTP_200_OK)


            # Check admin commands (activate/deactivate instance)
            admin_response = self._process_admin_commands(message, evolution_instance)
            if admin_response:
                return admin_response

            # Verifique se deve ignorar as próprias mensagens (resposta manual)
            ignore_response = self._should_ignore_own_message(message, evolution_instance, from_me)
            if ignore_response:
                return ignore_response

            # Inicializar serviços
            evolution_api = EvolutionAPIService(evolution_instance)

            if message_data.get('has_audio') or message.message_type == 'audio':
                message = self._process_audio_message(message, evolution_api, data)

            elif message_data.get('has_image') or message.message_type == 'image':
                message = self._process_image_message(message, data, evolution_instance)

            elif message.content or message.message_type == 'text':
                message.processing_status = 'processing'
                message.save()

            try:
                result = ask_agent(message, evolution_instance.agent)
                response_msg = result.get("answer", "")
            except Exception as e:
                logger.error(f"Erro LangChain Agent - Usuário: {from_number} | Erro: {e}", exc_info=True)
                response_msg = "⚠️ Erro ao processar sua mensagem. Por favor, tente novamente."

            result = False

            if response_msg:
                result = self._send_response_to_whatsapp(evolution_api, message.conversation.from_number,
                                                         response_msg)

                if result:
                    message.response = response_msg
                    message.processing_status = 'completed'
                    message.save()
                else:
                    message.processing_status = 'failed'
                    message.save()
            else:
                message.processing_status = 'completed'
                message.save()
                result = True

            if result:
                return Response({
                    'status': 'success',
                    'message': 'Message sent successfully',
                    'result': result
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'status': 'error',
                    'message': 'Failed to send message'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Erro crítico no webhook: {e}", exc_info=True)

            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    def _validate_webhook_data(self, data):
        """Validate that webhook data has required fields"""
        return isinstance(data, dict) and 'data' in data
    
    def _extract_message_data(self, webhook_data):
        """Extract message data from webhook payload - integrated with assistante logic"""
        try:
            data = webhook_data.get('data', {})
            
            if not data:
                return None
                
            # Extract basic info like assistante app
            sender_jid = data.get('key', {}).get('remoteJid', '')
            sender_name = data.get('pushName', '')
            source = data.get('source', '')
            message_timestamp = data.get('messageTimestamp', 0)
            
            # Apply same filtering logic as assistante (customize as needed)
            # if sender_name != "Allan Ramos" and sender_jid != "558399330465@s.whatsapp.net":
            #     return None
            
            # Handle different webhook event types
            if 'message' in data:
                message_data = data['message']
                
                # Extract content based on message type like assistante
                text_message = None
                audio_message = None
                image_message = None
                
                # Detectar tipo de mensagem baseado na estrutura real
                if 'conversation' in message_data:
                    text_message = message_data['conversation']
                elif 'extendedTextMessage' in message_data:
                    text_message = message_data['extendedTextMessage'].get('text')
                elif 'imageMessage' in message_data:
                    image_message = message_data['imageMessage']
                    # Para imagens, o caption é o texto da mensagem
                    text_message = message_data['imageMessage'].get('caption', '')
                elif 'audioMessage' in message_data:
                    audio_message = message_data['audioMessage'].get('url')
                elif 'videoMessage' in message_data:
                    image_message = message_data['videoMessage']  # Tratar vídeo similar a imagem para processamento
                elif 'documentMessage' in message_data:
                    image_message = message_data['documentMessage']
                
                # Buscar to_number a partir do owner da instância
                to_number = data.get('instance', '')
                owner = data.get('owner')
                if not to_number and owner:
                    # Tentar buscar o phone_number da instância Evolution pelo owner
                    try:
                        from whatsapp_connector.models import EvolutionInstance
                        evolution_instance = EvolutionInstance.objects.get(instance_name=owner)
                        to_number = evolution_instance.phone_number or owner
                    except EvolutionInstance.DoesNotExist:
                        to_number = owner
                
                return {
                    'message_id': data.get('key', {}).get('id'),
                    'from_number': sender_jid,
                    'to_number': to_number,
                    'message_type': self._get_message_type(message_data),
                    'content': text_message or self._get_message_content(message_data),
                    'media_url': self._get_media_url(message_data),
                    'timestamp': timezone.make_aware(datetime.fromtimestamp(message_timestamp)) if message_timestamp else timezone.now(),
                    'sender_name': sender_name,
                    'source': source,
                    'raw_data': data,
                    'has_audio': bool(audio_message),
                    'has_image': bool(image_message)
                }
            
            return None
            
        except Exception as e:
            print(f"Error extracting message data: {e}")
            return None
    
    def _get_message_type(self, message):
        """Determine message type from message object"""
        # Primeiro verifica se é um objeto message direto
        if 'imageMessage' in message:
            return 'image'
        elif 'audioMessage' in message:
            return 'audio'
        elif 'videoMessage' in message:
            return 'video'
        elif 'documentMessage' in message:
            return 'document'
        # Senão verifica dentro de message.message (estrutura aninhada)
        elif 'imageMessage' in message.get('message', {}):
            return 'image'
        elif 'audioMessage' in message.get('message', {}):
            return 'audio'
        elif 'videoMessage' in message.get('message', {}):
            return 'video'
        elif 'documentMessage' in message.get('message', {}):
            return 'document'
        else:
            return 'text'
    
    def _get_message_content(self, message):
        """Extract text content from message"""
        # Primeiro verifica se é um objeto message direto
        if 'conversation' in message:
            return message['conversation']
        elif 'extendedTextMessage' in message:
            return message['extendedTextMessage'].get('text', '')
        elif 'imageMessage' in message:
            return message['imageMessage'].get('caption', '')
        
        # Senão verifica dentro de message.message (estrutura aninhada)
        msg_content = message.get('message', {})
        if 'conversation' in msg_content:
            return msg_content['conversation']
        elif 'extendedTextMessage' in msg_content:
            return msg_content['extendedTextMessage'].get('text', '')
        elif 'imageMessage' in msg_content:
            return msg_content['imageMessage'].get('caption', '')
        
        return ''
    
    def _get_media_url(self, message):
        """Extract media URL from message"""
        # Primeiro verifica se é um objeto message direto
        if 'imageMessage' in message:
            return message['imageMessage'].get('url', '')
        elif 'audioMessage' in message:
            return message['audioMessage'].get('url', '')
        elif 'videoMessage' in message:
            return message['videoMessage'].get('url', '')
        elif 'documentMessage' in message:
            return message['documentMessage'].get('url', '')
        
        # Senão verifica dentro de message.message (estrutura aninhada)
        msg_content = message.get('message', {})
        if 'imageMessage' in msg_content:
            return msg_content['imageMessage'].get('url', '')
        elif 'audioMessage' in msg_content:
            return msg_content['audioMessage'].get('url', '')
        elif 'videoMessage' in msg_content:
            return msg_content['videoMessage'].get('url', '')
        elif 'documentMessage' in msg_content:
            return msg_content['documentMessage'].get('url', '')
        
        return None

    def _save_message(self, message_data, evolution_instance=None):
        """Save message to database using Conversation and Message from agents app"""
        from agents.models import Conversation, Message
        from core.models import Contact

        # Get or create contact first
        from_number = clean_number_whatsapp(message_data['from_number'])
        to_number = clean_number_whatsapp(message_data.get('to_number', ''))

        print(f'from_number {from_number} to_number {to_number}')

        # Criar ou buscar contato a partir dos dados do WhatsApp
        sender_name = message_data.get('sender_name', '')
        contact_data = {}
        if sender_name:
            contact_data['profile_name'] = sender_name

        # Vincular ao cliente (owner) da instância Evolution
        if evolution_instance and evolution_instance.owner:
            contact_data['client'] = evolution_instance.owner

        contact, contact_created = Contact.get_or_create_from_whatsapp(
            phone_number=from_number,
            **contact_data
        )

        if contact_created:
            print(f"✅ Novo contato criado: {contact} (Cliente: {contact.client})")
        else:
            print(f"ℹ️ Contato existente: {contact} (Total mensagens: {contact.total_messages})")

            # Se o contato existe mas não tem cliente vinculado, vincular agora
            if not contact.client and evolution_instance and evolution_instance.owner:
                contact.client = evolution_instance.owner
                contact.save(update_fields=['client'])
                print(f"🔗 Cliente {evolution_instance.owner} vinculado ao contato {contact}")

        # Buscar conversação ativa (ai ou human) ou criar nova com status 'ai'
        conversation, session_created = Conversation.get_or_create_active_session(
            contact=contact,
            from_number=from_number,
            to_number=to_number,
            evolution_instance=evolution_instance
        )

        # Vincular contato à conversação se ainda não estiver vinculado
        if not conversation.contact:
            conversation.contact = contact
            conversation.save(update_fields=['contact'])
            print(f"🔗 Contato {contact} vinculado à conversação {conversation.id}")

        if session_created:
            print(f"✅ Nova conversação criada para {from_number} com status 'ai'")
        else:
            print(f"ℹ️ Usando conversação existente para {from_number} (status: {conversation.get_status_display()})")

        # Extract data for database saving (remove helper fields)
        save_data = message_data.copy()
        save_data.pop('has_audio', None)
        save_data.pop('has_image', None)
        save_data.pop('from_number', None)  # Remove since it's in conversation
        save_data.pop('to_number', None)    # Remove since it's in conversation

        # Check if instance is inactive and mark the message
        if evolution_instance and not evolution_instance.is_active:
            save_data['received_while_inactive'] = True
            print(f"🔴 Marcando mensagem como recebida com instância inativa: {evolution_instance.name}")
        else:
            save_data['received_while_inactive'] = False

        # Add conversation
        save_data['conversation'] = conversation

        # Add owner from evolution_instance
        if evolution_instance and hasattr(evolution_instance, 'owner'):
            save_data['owner'] = evolution_instance.owner

        # Set received_at from timestamp if available
        if 'timestamp' in save_data:
            save_data['received_at'] = save_data.pop('timestamp')

        message, created = Message.objects.get_or_create(
            message_id=message_data['message_id'],
            defaults=save_data
        )
        return message
    
    def _process_audio_message(self, message, evolution_api, raw_data):
        """Process audio message and return the transcription text"""
        try:
            print("Mensagem de áudio detectada")
            message.processing_status = 'processing'
            message.save()

            # Decrypt audio using the same logic as assistante
            audio_bytes = evolution_api.decrypt_whatsapp_audio(raw_data)

            if audio_bytes:
                # Transcribe audio
                transcription = transcribe_audio_from_bytes(audio_bytes.read())
                print(f"Texto transcrito: {transcription}")

                message.audio_transcription = transcription
                message.content = transcription  # Use transcription as message content
                message.save()

                # Retornar apenas a transcrição
                # message.processing_status = 'completed'
                message.save()
                print(f"✅ Áudio transcrito para {message.conversation.from_number}")

                return message
            else:
                print("❌ Falha ao descriptografar áudio")
                message.processing_status = 'failed'
                message.save()
                return "❌ Falha ao processar áudio"

        except Exception as e:
            # Usar logger do Django para erro de processamento de áudio
            media_logger.error(
                f"Erro processamento áudio - Usuário: {message.conversation.from_number} | "
                f"Audio URL: {message.media_url} | Erro: {str(e)}",
                exc_info=True,
                extra={
                    'usuario': message.conversation.from_number,
                    'media_url': message.media_url,
                    'tipo_media': 'audio',
                    'erro': str(e),
                    'message_id': message.message_id
                }
            )

            message.processing_status = 'failed'
            message.save()

            return f"❌ Erro ao processar áudio: {str(e)}"
    
    def _process_text_message(self, message, n8n_service):
        """Process text message like assistante app"""
        try:
            print(f"Mensagem de texto detectada {message}")
            message.processing_status = 'processing'
            message.save()
            
            # Send to n8n
            n8n_result = n8n_service.send_message_to_n8n(
                message.from_number, 
                message.sender_name, 
                message.content
            )
            
            if n8n_result:
                message.n8n_response = n8n_result
                message.processing_status = 'completed'
            else:
                message.processing_status = 'failed'
                
            message.save()
            
        except Exception as e:
            print(f"Error processing text message: {e}")
            message.processing_status = 'failed'
            message.save()
    
    def _process_image_message(self, message, raw_data=None, evolution_instance=None):
        """Process image message and return the AI response text"""
        try:
            print("Mensagem de imagem detectada")
            message.processing_status = 'processing'
            message.save()

            processing_service = ImageProcessingService(evolution_instance)
            evolution_api = EvolutionAPIService(evolution_instance) if evolution_instance else None

            # Try to decrypt the image first if we have raw_data
            if raw_data:
                print("Tentando descriptografar imagem...")
                print(f"Raw data structure keys: {list(raw_data.keys())}")
                if 'data' in raw_data:
                    print(f"Data structure keys: {list(raw_data['data'].keys())}")
                    if 'message' in raw_data['data']:
                        print(f"Message structure keys: {list(raw_data['data']['message'].keys())}")

                decrypted_image = evolution_api.decrypt_whatsapp_image(raw_data)

                if decrypted_image:
                    print("✓ Descriptografia bem-sucedida")
                    # Save decrypted image directly
                    if processing_service.save_decrypted_image(decrypted_image, message):
                        # Process the decrypted image and return response
                        return processing_service.process_image_message_and_return_text(message)
                    else:
                        print("✗ Falha ao salvar imagem descriptografada")
                        message.processing_status = 'failed'
                        message.save()
                        return "❌ Falha ao salvar imagem"
                else:
                    print("Falha na descriptografia, tentando download direto...")
                    # Fallback to direct download
                    if message.media_url and processing_service.download_and_save_image(message.media_url, message):
                        return processing_service.process_image_message_and_return_text(message)
                    else:
                        print("✗ Download direto também falhou")
                        message.processing_status = 'failed'
                        message.save()
                        return "❌ Falha ao baixar imagem"
            else:
                # No raw data, try direct download
                if message.media_url and processing_service.download_and_save_image(message.media_url, message):
                    return processing_service.process_image_message_and_return_text(message)
                else:
                    message.processing_status = 'failed'
                    message.save()
                    return "❌ Falha ao processar imagem"

        except Exception as e:
            # Usar logger do Django para erro de processamento de imagem
            media_logger.error(
                f"Erro processamento imagem - Usuário: {message.conversation.from_number} | "
                f"Image URL: {message.media_url} | Caption: {message.content} | Erro: {str(e)}",
                exc_info=True,
                extra={
                    'usuario': message.conversation.from_number,
                    'media_url': message.media_url,
                    'caption': message.content,
                    'tipo_media': 'image',
                    'erro': str(e),
                    'message_id': message.message_id
                }
            )

            message.processing_status = 'failed'
            message.save()

            return f"❌ Erro ao processar imagem: {str(e)}"


    def _get_evolution_instance(self, message_data):
        """
        Busca a instância Evolution baseada no instanceId da mensagem
        """
        raw_data = message_data.get('raw_data', {})
        instance_id = raw_data.get('instanceId')
        owner = raw_data.get('owner')

        evolution_instance = None

        # Primeiro tentar por instanceId
        if instance_id:
            try:
                # Buscar por algum campo que corresponda ao instanceId
                # Como não temos um campo instanceId no modelo, vamos usar uma abordagem diferente
                print(f"🔍 Buscando instância por instanceId: {instance_id}")

                # Buscar todas as instâncias e verificar via API qual corresponde ao instanceId
                evolution_instance = EvolutionInstance.objects.get(instance_evolution_id=instance_id)

            except Exception as e:
                print(f"❌ Erro ao buscar instância por instanceId: {e}")


        return evolution_instance
    
    def _process_admin_commands(self, message_history, evolution_instance):
        """
        Processa comandos administrativos enviados pelo próprio número da instância
        Retorna Response se comando foi processado, None caso contrário
        """
        sender_number = message_history.conversation.from_number

        # Processar comandos administrativos
        message_content = message_history.content.strip().lower() if message_history.content else ""
        evolution_api = EvolutionAPIService(evolution_instance)

        print(f'sender_number {sender_number} {evolution_instance.phone_number}')

        # Verificar se a mensagem é do próprio número da instância (usando sender_number da sessão)
        if (evolution_instance and evolution_instance.phone_number) and sender_number == evolution_instance.phone_number:

            if message_content.startswith('<<<'):
                return self._handle_transfer_to_human_command(evolution_instance, evolution_api, sender_number,
                                                              message_history, message_content)

            elif message_content.startswith('>>>'):
                return self._handle_transfer_to_ai_command(evolution_instance, evolution_api, sender_number,
                                                           message_history, message_content)

            elif message_content.startswith('[]'):
                return self._handle_close_session_command(evolution_instance, evolution_api, sender_number, message_history, message_content)

        # Verificar se a mensagem é do próprio número da instância
        if not (evolution_instance and 
                evolution_instance.phone_number and 
                sender_number == evolution_instance.phone_number):
            return None

        if message_content in ['ativar', 'ativar instancia', 'ligar', 'on']:
            return self._handle_activate_command(evolution_instance, evolution_api, sender_number, message_history)
            
        elif message_content in ['desativar', 'desativar instancia', 'desligar', 'off']:
            return self._handle_deactivate_command(evolution_instance, evolution_api, sender_number, message_history)
            
        elif message_content in ['status', 'estado', 'info']:
            return self._handle_status_command(evolution_instance, evolution_api, sender_number, message_history)

        return None

    def _process_calendar_commands(self, message_history, evolution_instance):
        """
        Processa comandos relacionados ao Google Calendar usando GoogleCalendarAIAssistant
        Retorna Response se comando foi processado, None caso contrário
        """
        if not message_history.content:
            return None

        message_content = message_history.content.strip()
        sender_number = message_history.conversation.from_number
        evolution_api = EvolutionAPIService(evolution_instance)

        # Verificar se a mensagem contém palavras-chave relacionadas a calendário
        calendar_keywords = [
            'calendario', 'calendar', 'agenda', 'evento', 'eventos', 'compromisso', 'compromissos',
            'reunião', 'reunioes', 'agendar', 'marcar', 'criar evento', 'novo evento',
            'meus eventos', 'eventos hoje', 'agenda hoje', 'conectar calendario',
            'integrar calendario', 'google calendar', 'ajuda calendario'
        ]

        # Padrões de data
        date_patterns = [
            r'\d{1,2}/\d{1,2}', r'\d{1,2}-\d{1,2}', r'amanhã', r'hoje', r'segunda', r'terça',
            r'quarta', r'quinta', r'sexta', r'sabado', r'domingo', r'próxima', r'próximo'
        ]

        contains_calendar_keywords = any(keyword.lower() in message_content.lower() for keyword in calendar_keywords)

        import re
        contains_date_patterns = any(re.search(pattern, message_content.lower()) for pattern in date_patterns)

        # Se não contém indicadores de calendário, não processar
        if not (contains_calendar_keywords or contains_date_patterns):
            return None

        print(f"🗓️ Processando comando de calendário: {message_content}")

        # Tentar usar GoogleCalendarAIAssistant
        try:
            from google_calendar.ai_assistants import GoogleCalendarAIAssistant
        except ImportError as e:
            print(f"❌ Erro ao importar GoogleCalendarAIAssistant: {e}")
            error_msg = "❌ Serviço de calendário não está disponível no momento."
            evolution_api.send_text_message(sender_number, error_msg)
            return Response({
                'status': 'error',
                'reason': 'Serviço de calendário indisponível',
                'message_id': message_history.message_id
            }, status=status.HTTP_200_OK)

        # Criar instância do GoogleCalendarAIAssistant
        try:
            calendar_assistant = GoogleCalendarAIAssistant()
        except Exception as assistant_error:
            print(f"❌ Erro ao criar GoogleCalendarAIAssistant: {assistant_error}")
            error_msg = "❌ Erro ao inicializar assistente de calendário."
            evolution_api.send_text_message(sender_number, error_msg)
            return Response({
                'status': 'error',
                'reason': f'Erro interno: {str(assistant_error)}',
                'message_id': message_history.message_id
            }, status=status.HTTP_200_OK)

        # Preparar mensagem contextualizada
        contextualized_message = f"""Usuário WhatsApp {sender_number}: {message_content}

CONTEXTO IMPORTANTE:
- Este usuário está enviando mensagens via WhatsApp
- O número do WhatsApp é: {sender_number}
- Use sempre este número nas funções que requerem numero_whatsapp
- Seja direto e objetivo nas respostas
- Formate as respostas de forma amigável para WhatsApp
- Se o usuário solicitar criação de eventos, use os dados fornecidos ou peça os dados que faltam
- Para listar eventos, seja conciso mas informativo
- Para verificar disponibilidade, seja claro sobre conflitos"""

        try:
            # Usar o assistente de calendário
            calendar_response = calendar_assistant.run(
                message=contextualized_message
            )

            if calendar_response and hasattr(calendar_response, 'text') and calendar_response.text:
                response_text = calendar_response.text
                print(f"✅ Resposta do GoogleCalendarAIAssistant: {response_text[:100]}...")

                # Enviar resposta
                result = evolution_api.send_text_message(sender_number, response_text)

                if result:
                    message_history.response = response_text
                    message_history.processing_status = 'completed'
                    message_history.save()
                    print(f"✅ Comando de calendário processado e resposta enviada para {sender_number}")

                    return Response({
                        'status': 'success',
                        'reason': 'Comando de calendário processado',
                        'message_id': message_history.message_id
                    }, status=status.HTTP_200_OK)
                else:
                    message_history.processing_status = 'failed'
                    message_history.save()
                    print(f"❌ Falha ao enviar resposta do calendário")
            else:
                print("ℹ️ GoogleCalendarAIAssistant não retornou resposta")

        except Exception as e:
            print(f"❌ Erro ao executar GoogleCalendarAIAssistant: {e}")
            error_msg = "❌ Erro ao processar comando de calendário."
            evolution_api.send_text_message(sender_number, error_msg)
            return Response({
                'status': 'error',
                'reason': f'Erro interno: {str(e)}',
                'message_id': message_history.message_id
            }, status=status.HTTP_200_OK)

        return None

    def _handle_activate_command(self, evolution_instance, evolution_api, sender_number, message_history):
        """Handle activate instance command"""
        if not evolution_instance.is_active:
            evolution_instance.is_active = True
            evolution_instance.save(update_fields=['is_active'])
            print(f"✅ Instância ativada via comando: {evolution_instance.name}")
            
            confirmation_msg = f"✅ Instância '{evolution_instance.name}' foi ativada com sucesso!"
            evolution_api.send_text_message(sender_number, confirmation_msg)
            
            return Response({
                'status': 'success',
                'reason': 'Instância ativada via comando',
                'message_id': message_history.message_id
            }, status=status.HTTP_200_OK)
        else:
            info_msg = f"ℹ️ A instância '{evolution_instance.name}' já está ativa."
            evolution_api.send_text_message(sender_number, info_msg)
            
            return Response({
                'status': 'ignored',
                'reason': 'Instância já estava ativa',
                'message_id': message_history.message_id
            }, status=status.HTTP_200_OK)
    
    def _handle_deactivate_command(self, evolution_instance, evolution_api, sender_number, message_history):
        """Handle deactivate instance command"""
        if evolution_instance.is_active:
            evolution_instance.is_active = False
            evolution_instance.save(update_fields=['is_active'])
            print(f"🔴 Instância desativada via comando: {evolution_instance.name}")
            
            confirmation_msg = f"🔴 Instância '{evolution_instance.name}' foi desativada com sucesso!"
            evolution_api.send_text_message(sender_number, confirmation_msg)
            
            return Response({
                'status': 'success',
                'reason': 'Instância desativada via comando',
                'message_id': message_history.message_id
            }, status=status.HTTP_200_OK)
        else:
            info_msg = f"ℹ️ A instância '{evolution_instance.name}' já está desativada."
            evolution_api.send_text_message(sender_number, info_msg)
            
            return Response({
                'status': 'ignored',
                'reason': 'Instância já estava desativada',
                'message_id': message_history.message_id
            }, status=status.HTTP_200_OK)
    
    def _handle_status_command(self, evolution_instance, evolution_api, sender_number, message_history):
        """Handle status info command"""
        status_icon = "✅" if evolution_instance.is_active else "🔴"
        status_text = "ativa" if evolution_instance.is_active else "desativada"
        
        status_msg = f"{status_icon} Instância '{evolution_instance.name}' está {status_text}.\n\n"
        status_msg += f"📱 Número: {evolution_instance.phone_number}\n"
        status_msg += f"🔗 Status de conexão: {evolution_instance.get_status_display()}\n"
        
        if evolution_instance.ignore_own_messages:
            status_msg += "🛡️ Filtro de mensagens próprias: Ativo\n"
        else:
            status_msg += "⚠️ Filtro de mensagens próprias: Inativo\n"
            
        status_msg += "\n💬 Comandos disponíveis:\n• 'ativar' - Ativa a instância\n• 'desativar' - Desativa a instância\n• 'status' - Mostra este status\n• '<<< +5511999999999' - Transfere sessão para humano\n• '>>> +5511999999999' - Retorna sessão para IA\n• '[ +5511999999999' - Encerra sessão"
        
        evolution_api.send_text_message(sender_number, status_msg)
        
        return Response({
            'status': 'success',
            'reason': 'Status da instância enviado',
            'message_id': message_history.message_id
        }, status=status.HTTP_200_OK)

    def _handle_transfer_to_human_command(self, evolution_instance, evolution_api, sender_number, message_history, message_content):
        """Handle transfer session to human command (<<<)
        OBS: Validação de autorização já foi feita em _process_admin_commands

        Transfere a última sessão AI ativa desta instância para atendimento humano
        """
        try:
            # Buscar a última sessão AI ativa (exceto a do próprio sender)
            ai_session_from_number = Conversation.objects.filter(
                evolution_instance=evolution_instance,
                from_number=sender_number
            ).update(status='human')

            # evolution_api.send_text_message(sender_number, 'success_msg')

            return Response({
                'status': 'success',
                'reason': f'Sessão de {sender_number} transferida para humano',
                'message_id': message_history.message_id
            }, status=status.HTTP_200_OK)

        except Exception as e:
            error_msg = f"❌ Erro ao transferir sessão: {str(e)}"
            evolution_api.send_text_message(sender_number, error_msg)

            return Response({
                'status': 'error',
                'reason': f'Erro interno: {str(e)}',
                'message_id': message_history.message_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _handle_transfer_to_ai_command(self, evolution_instance, evolution_api, sender_number, message_history, message_content):
        """Handle transfer session to AI command (>>>)
        Formatos aceitos:
        - '>>>' : transfere a própria sessão do remetente
        - '>>> +5511999999999' : transfere a sessão do número especificado
        """
        try:
            # Extrair número do comando (se fornecido)
            parts = message_content.strip().split()
            if len(parts) > 1:
                target_number = clean_number_whatsapp(parts[1])
                print(f"🔄 Retornando sessão do número {target_number} para IA")
            else:
                target_number = sender_number
                print(f"🔄 Retornando própria sessão para IA")

            # Atualizar sessão para 'ai'
            updated_count = Conversation.objects.filter(
                from_number=target_number,
                evolution_instance=evolution_instance,
                status='human'
            ).update(status='ai')

            if updated_count > 0:
                success_msg = f"✅ Sessão de {target_number} retornada para atendimento por IA"
                # evolution_api.send_text_message(sender_number, success_msg)

                return Response({
                    'status': 'success',
                    'reason': f'Sessão de {target_number} retornada para AI',
                    'message_id': message_history.message_id
                }, status=status.HTTP_200_OK)
            else:
                error_msg = f"❌ Nenhuma sessão HUMAN encontrada para {target_number}"
                evolution_api.send_text_message(sender_number, error_msg)

                return Response({
                    'status': 'error',
                    'reason': f'Sessão não encontrada para {target_number}',
                    'message_id': message_history.message_id
                }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            error_msg = f"❌ Erro ao retornar sessão para AI: {str(e)}"
            evolution_api.send_text_message(sender_number, error_msg)

            return Response({
                'status': 'error',
                'reason': f'Erro interno: {str(e)}',
                'message_id': message_history.message_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _handle_close_session_command(self, evolution_instance, evolution_api, sender_number, message_history, message_content):
        """Handle close session command ([])
        Formatos aceitos:
        - '[]' : encerra a própria sessão do remetente
        - '[] +5511999999999' : encerra a sessão do número especificado
        """
        try:
            # Extrair número do comando (se fornecido)
            parts = message_content.strip().split()
            if len(parts) > 1:
                target_number = clean_number_whatsapp(parts[1])
                print(f"🔄 Encerrando sessão do número {target_number}")
            else:
                target_number = sender_number
                print(f"🔄 Encerrando própria sessão")

            # Atualizar sessão para 'closed'
            updated_count = Conversation.objects.filter(
                from_number=target_number,
                evolution_instance=evolution_instance
            ).update(status='closed')

            if updated_count > 0:
                success_msg = f"✅ Sessão de {target_number} foi encerrada"
                evolution_api.send_text_message(sender_number, success_msg)

                return Response({
                    'status': 'success',
                    'reason': f'Sessão de {target_number} encerrada',
                    'message_id': message_history.message_id
                }, status=status.HTTP_200_OK)
            else:
                error_msg = f"❌ Nenhuma sessão encontrada para {target_number}"
                evolution_api.send_text_message(sender_number, error_msg)

                return Response({
                    'status': 'error',
                    'reason': f'Sessão não encontrada para {target_number}',
                    'message_id': message_history.message_id
                }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            error_msg = f"❌ Erro ao encerrar sessão: {str(e)}"
            evolution_api.send_text_message(sender_number, error_msg)

            return Response({
                'status': 'error',
                'reason': f'Erro interno: {str(e)}',
                'message_id': message_history.message_id
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _should_ignore_own_message(self, message_history, evolution_instance, from_me=False):
        """
        Verifica se deve ignorar mensagem enviada pelo próprio número da instância
        Considera tanto o campo fromMe (mensagens respondidas manualmente)
        quanto o sender_name (mensagens enviadas pela própria instância)

        Retorna Response se deve ignorar, None caso contrário
        """
        # Só ignora se a configuração ignore_own_messages estiver ativa
        if not (evolution_instance and evolution_instance.ignore_own_messages):
            return None

        sender_name = message_history.sender_name

        # Verificar se é mensagem enviada manualmente (fromMe = true)
        if from_me:
            return Response({
                'status': 'ignored',
                'reason': 'Mensagem enviada manualmente pelo dono da instância (fromMe=true)',
                'message_id': message_history.message_id
            }, status=status.HTTP_200_OK)

        # Verificar se é mensagem enviada pela própria instância (por sender_name)
        if evolution_instance.profile_name and sender_name == evolution_instance.profile_name:
            return Response({
                'status': 'ignored',
                'reason': 'Mensagem enviada pela própria instância',
                'message_id': message_history.message_id
            }, status=status.HTTP_200_OK)

        return None
    
    def _send_response_to_whatsapp(self, evolution_api, to_number, response_msg):
        """
        Envia resposta para WhatsApp, detectando se é estruturada ou simples
        """
        if isinstance(response_msg, dict) and response_msg.get("type") == "structured":
            # Resposta estruturada - enviar texto e arquivo separadamente
            return self._send_structured_response(evolution_api, to_number, response_msg)
        else:
            # Resposta simples - enviar apenas texto
            return evolution_api.send_text_message(to_number, str(response_msg))
    
    def _send_structured_response(self, evolution_api, to_number, structured_response):
        """
        Envia resposta estruturada (texto + arquivo) separadamente
        """
        text = structured_response.get("text", "").strip()
        file_url = structured_response.get("file", "").strip()
        
        print(f"📤 Enviando resposta estruturada:")
        print(f"   Texto: {text[:100]}..." if len(text) > 100 else f"   Texto: {text}")
        print(f"   Arquivo: {file_url}")
        
        results = []
        
        # Enviar texto primeiro se não estiver vazio
        if text:
            text_result = evolution_api.send_text_message(to_number, text)
            results.append(text_result)
            print(f"✅ Texto enviado: {text_result}")
        
        # Enviar arquivo depois se não estiver vazio
        if file_url:
            # Verificar se é URL válida
            if file_url.startswith(('http://', 'https://')):
                file_result = evolution_api.send_file_message(to_number, file_url)
                results.append(file_result) 
                print(f"📎 Arquivo enviado: {file_result}")
            else:
                print(f"⚠️ URL de arquivo inválida: '{file_url}' - deve começar com http:// ou https://")
                # Enviar mensagem explicativa para o usuário
                error_message = f"❌ Não foi possível enviar o arquivo '{file_url}'. O sistema precisa de uma URL completa (ex: https://exemplo.com/arquivo.pdf)."
                error_result = evolution_api.send_text_message(to_number, error_message)
                results.append(error_result)
        
        # Retornar True se ao menos um envio foi bem sucedido
        return any(results)

class MessageListView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request):
        """List all WhatsApp messages"""
        from agents.models import Message
        messages = Message.objects.all()[:50]  # Last 50 messages

        data = []
        for message in messages:
            data.append({
                'message_id': message.message_id,
                'from_number': message.conversation.from_number if message.conversation else None,
                'to_number': message.conversation.to_number if message.conversation else None,
                'message_type': message.message_type,
                'content': message.content,
                'timestamp': message.created_at,
                'received_at': message.received_at,
                'processing_status': message.processing_status,
                'has_response': bool(message.response),
                'received_while_inactive': message.received_while_inactive,
            })

        return Response(data, status=status.HTTP_200_OK)

class MessageDetailView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request, message_id):
        """Get detailed information about a specific message"""
        from agents.models import Message
        try:
            message = Message.objects.get(message_id=message_id)

            data = {
                'message_id': message.message_id,
                'from_number': message.conversation.from_number if message.conversation else None,
                'to_number': message.conversation.to_number if message.conversation else None,
                'message_type': message.message_type,
                'content': message.content,
                'media_url': message.media_url,
                'timestamp': message.created_at,
                'received_at': message.received_at,
                'processing_status': message.processing_status,
                'response': message.response,
                'received_while_inactive': message.received_while_inactive,
            }

            return Response(data, status=status.HTTP_200_OK)

        except Message.DoesNotExist:
            return Response(
                {'error': 'Message not found'},
                status=status.HTTP_404_NOT_FOUND
            )



