import traceback
from datetime import datetime
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from agents.langchain.agente import ask_agent
from agents.models import Message, Conversation
from core.exceptions import WhatsAppConnectorException
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

    @extend_schema(
        request=OpenApiTypes.OBJECT,
        description="Webhook endpoint para receber mensagens da Evolution API"
    )
    def post(self, request, *args, **kwargs):
        """
        Processa webhooks recebidos da Evolution API
        """
        try:
            # Ler dados do request
            try:
                data = request.data
                logger.info("Webhook recebido - dados parseados com sucesso")
            except Exception as e:
                logger.error(f"Erro ao parsear dados do request: {e}")
                traceback.print_exc()
                return Response({'error': 'Failed to parse request data'}, status=400)

            # Filtro rápido de mensagens inválidas
            early_ignore = self._should_ignore_message_early(data)
            if early_ignore:
                logger.info("Mensagem ignorada por filtro rápido")
                return early_ignore

            # Extrair dados da mensagem
            try:
                message_data = self._extract_message_data(data)
                logger.info(f"Dados da mensagem extraídos: {message_data.get('message_id') if message_data else 'None'}")
            except Exception as e:
                logger.error(f"Erro ao extrair dados da mensagem: {e}")
                traceback.print_exc()
                return Response(
                    {'status': 'error', 'reason': 'Failed to extract message data'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            if not message_data:
                logger.info("Mensagem inválida - dados vazios")
                return Response({'status': 'ignored', 'reason': 'Not a valid message'}, status=status.HTTP_200_OK)

            # Buscar e validar instância Evolution (já inclui validação de ativa e agente)
            try:
                evolution_instance, error_response = self._get_evolution_instance(message_data)
                if error_response:
                    logger.warning(f"Erro na validação da instância: {error_response.data}")
                    return error_response
                logger.info(f"Instância Evolution encontrada: {evolution_instance.name}")
            except Exception as e:
                logger.error(f"Erro ao buscar instância Evolution: {e}")
                raise

            # Validar número autorizado
            from_number = clean_number_whatsapp(message_data['from_number'])
            auth_check = self._check_number_authorized(evolution_instance, from_number)
            if auth_check:
                logger.info(f"Número {from_number} não autorizado")
                return auth_check

            # Salvar mensagem no banco
            try:
                message = self._save_message(message_data, evolution_instance)
                logger.info(f"Mensagem salva: {message.message_id}")
            except Exception as e:
                logger.error(f"Erro ao salvar mensagem: {e}")
                raise

            # Processar comandos administrativos
            if message_data.get('from_me'):
                admin_response = self._process_admin_commands(message, evolution_instance)
                if admin_response:
                    logger.info("Comando administrativo processado")
                    return admin_response

            # Processar mensagens from_me (enviadas pela instância)
            if message_data.get('from_me'):
                from_me_response = self._process_from_me_message(message, message_data)
                if from_me_response:
                    logger.info("Mensagem from_me processada")
                    return from_me_response

            # Verificar se conversa está em atendimento humano
            human_status_check = self._check_conversation_human_status(message)
            if human_status_check:
                logger.info("Conversa em atendimento humano")
                return human_status_check


            # Processar mensagem por tipo (áudio, imagem, texto)
            try:
                message = self._process_message_by_type(message, message_data, data, evolution_instance)
                logger.info(f"Mensagem processada por tipo: {message.message_type}")
            except Exception as e:
                logger.error(f"Erro ao processar mensagem por tipo: {e}")
                raise

            # Processar com agente e enviar resposta
            try:
                response = self._process_agent_and_send_response(message, evolution_instance, from_number)
                logger.info("Resposta processada e enviada com sucesso")
                return response
            except Exception as e:
                logger.error(f"Erro ao processar com agente e enviar resposta: {e}")
                raise

        except Exception as e:
            # Log detalhado do erro
            error_details = traceback.format_exc()
            logger.error(f"Erro no webhook Evolution: {str(e)}\n{error_details}")
            traceback.print_exc()
            raise WhatsAppConnectorException(f"Erro interno: {str(e)}", original_exception=e)

    def _check_number_authorized(self, evolution_instance, from_number):
        """
        Verifica se o número está autorizado na instância
        Retorna Response se não autorizado, None se autorizado
        """
        if evolution_instance and not evolution_instance.is_number_authorized(from_number):
            return Response({
                'status': 'unauthorized',
                'reason': f'Número {from_number} não autorizado'
            }, status=status.HTTP_200_OK)
        return None

    def _process_from_me_message(self, message, message_data):
        """
        Processa mensagens enviadas pela própria instância (fromMe==True)
        Marca a conversa como atendimento humano
        Retorna Response se processado, None se deve continuar
        """
        # Transferir conversation para atendimento humano
        message.conversation.status = 'human'
        message.conversation.save(update_fields=['status'])

        # Salvar conteúdo no campo response (não em content)
        message.response = message_data.get('content', '')
        message.content = ''  # Limpar content
        message.processing_status = 'completed'
        message.responded_by = 'human'
        message.save()

        return Response({
            'status': 'success',
            'message': 'Mensagem manual detectada, conversation marcada como human',
        }, status=status.HTTP_200_OK)

    def _check_conversation_human_status(self, message):
        """
        Verifica se a conversa está em atendimento humano
        Retorna Response se em atendimento humano, None se deve continuar
        """
        if message.conversation.status == 'human':
            message.processing_status = "completed"
            message.responded_by = message.conversation.status
            message.response = "resposta será gerada por humano"
            message.save()
            return Response({
                'status': 'success',
                'message': '',
            }, status=status.HTTP_200_OK)
        return None

    def _process_message_by_type(self, message, message_data, data, evolution_instance):
        """
        Processa a mensagem de acordo com seu tipo (áudio, imagem ou texto)
        Retorna a mensagem processada
        """
        evolution_api = EvolutionAPIService(evolution_instance)

        if message_data.get('has_audio') or message.message_type == 'audio':
            return self._process_audio_message(message, evolution_api, data)

        elif message_data.get('has_image') or message.message_type == 'image':
            return self._process_image_message(message, data, evolution_instance)

        elif message.content or message.message_type == 'text':
            message.processing_status = 'processing'
            message.save()
            return message

        return message

    def _process_agent_and_send_response(self, message, evolution_instance, from_number):
        """
        Processa a mensagem com o agente e envia a resposta ao WhatsApp
        Retorna Response com o resultado
        """
        evolution_api = EvolutionAPIService(evolution_instance)

        # Processar mensagem com o agente
        try:
            result = ask_agent(message, evolution_instance.agent)
            response_msg = result.get("answer", "")
        except Exception as e:
            logger.error(f"Erro LangChain Agent - Usuário: {from_number} | Erro: {e}", exc_info=True)
            response_msg = "⚠️ Erro ao processar sua mensagem. Por favor, tente novamente."

        # Enviar resposta ao WhatsApp
        if response_msg:
            send_result = self._send_response_to_whatsapp(evolution_api, message.conversation.from_number, response_msg)

            if send_result:
                message.response = response_msg
                message.processing_status = 'completed'
                message.save()

                return Response({
                    'status': 'success',
                    'message': 'Message sent successfully',
                    'result': send_result
                }, status=status.HTTP_200_OK)
            else:
                message.processing_status = 'failed'
                message.save()

                return Response({
                    'status': 'error',
                    'message': 'Failed to send message'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            message.processing_status = 'completed'
            message.save()

            return Response({
                'status': 'success',
                'message': 'Message sent successfully',
                'result': True
            }, status=status.HTTP_200_OK)

    def _should_ignore_message_early(self, data):
        """
        Filtro rápido de mensagens que não precisam ser processadas
        Retorna Response se deve ignorar, None se deve continuar
        """
        key_data = data.get('key', {})
        remote_jid = key_data.get('remoteJid', '')
        message_type = data.get('messageType', '')

        if remote_jid in ['status@broadcast'] or message_type in ['group']:
            return Response({
                'status': 'ignored',
                'reason': f'{remote_jid} / {message_type}'
            }, status=status.HTTP_200_OK)

        return None

    def _extract_message_data(self, webhook_data):
        """Extrair dados da mensagem do payload do webhook"""
        try:
            data = webhook_data.get('data', {})

            if not data:
                return None

            # Extract basic info like assistante app
            key_data = data.get('key', {})
            sender_jid = key_data.get('remoteJid', '')
            from_me = key_data.get('fromMe', False)

            # Se remoteJid termina com @lid, o número correto está em remoteJidAlt
            if sender_jid.endswith('@lid'):
                sender_jid = key_data.get('remoteJidAlt', sender_jid)

            sender_name = data.get('pushName', '')
            source = data.get('source', '')
            message_timestamp = data.get('messageTimestamp', 0)

            # Capturar sender do nível raiz do webhook (número da instância)
            instance_number = webhook_data.get('sender', '')

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

                # Determinar from_number e to_number baseado em fromMe
                if from_me:
                    # Mensagem ENVIADA pela instância (Instância → Cliente)
                    # Isso indica que um humano está atendendo manualmente
                    final_from_number = instance_number  # Instância enviou
                    final_to_number = sender_jid  # Cliente recebeu
                else:
                    # Mensagem RECEBIDA pela instância (Cliente → Instância)
                    final_from_number = sender_jid  # Cliente enviou
                    final_to_number = instance_number  # Instância recebeu

                return {
                    'message_id': data.get('key', {}).get('id'),
                    'from_number': final_from_number,
                    'to_number': final_to_number,
                    'message_type': self._get_message_type(message_data),
                    'content': text_message or self._get_message_content(message_data),
                    'media_url': self._get_media_url(message_data),
                    'timestamp': timezone.make_aware(
                        datetime.fromtimestamp(message_timestamp)) if message_timestamp else timezone.now(),
                    'sender_name': sender_name,
                    'source': source,
                    'raw_data': data,
                    'has_audio': bool(audio_message),
                    'has_image': bool(image_message),
                    'from_me': from_me  # Incluir fromMe para uso posterior
                }

            return None

        except Exception as e:
            print(f"Error extracting message data: {e}")
            return None

    def _get_message_type(self, message):
        """Determinar tipo da mensagem a partir do objeto message"""
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
        """Extrair conteúdo de texto da mensagem"""
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
        """Extrair URL de mídia da mensagem"""
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
        """Salvar mensagem no banco de dados usando Conversation e Message"""
        from agents.models import Conversation, Message
        from core.models import Contact

        # Get or create contact first
        from_number = clean_number_whatsapp(message_data['from_number'])
        to_number = clean_number_whatsapp(message_data.get('to_number', ''))
        from_me = message_data.get('from_me', False)

        # Criar ou buscar contato a partir dos dados do WhatsApp
        sender_name = message_data.get('sender_name', '')
        contact_data = {}
        if sender_name:
            contact_data['profile_name'] = sender_name

        # Vincular ao cliente (owner) da instância Evolution
        if evolution_instance and evolution_instance.owner:
            contact_data['client'] = evolution_instance.owner

        # Se from_me=True, o contato é o destinatário (to_number)
        # Se from_me=False, o contato é o remetente (from_number)
        contact_number = to_number if from_me else from_number

        contact, contact_created = Contact.get_or_create_from_whatsapp(
            phone_number=contact_number,
            **contact_data
        )

        # Se o contato existe mas não tem cliente vinculado, vincular agora
        if not contact.client and evolution_instance and evolution_instance.owner:
            contact.client = evolution_instance.owner
            contact.save(update_fields=['client'])

        # Normalizar from_number e to_number para a conversa
        # A conversa sempre usa: from_number = cliente, to_number = instância
        if from_me:
            # Se from_me=True, inverter os números
            conversation_from = to_number  # Cliente
            conversation_to = from_number  # Instância
        else:
            # Se from_me=False, manter os números
            conversation_from = from_number  # Cliente
            conversation_to = to_number  # Instância

        # Buscar conversação ativa (ai ou human) ou criar nova com status 'ai'
        conversation, session_created = Conversation.get_or_create_active_session(
            contact=contact,
            from_number=conversation_from,
            to_number=conversation_to,
            evolution_instance=evolution_instance
        )

        # Vincular contato à conversação se ainda não estiver vinculado
        if not conversation.contact:
            conversation.contact = contact
            conversation.save(update_fields=['contact'])

        # Extract data for database saving (remove helper fields)
        save_data = message_data.copy()
        save_data.pop('has_audio', None)
        save_data.pop('has_image', None)
        save_data.pop('from_number', None)  # Remove since it's in conversation
        save_data.pop('to_number', None)  # Remove since it's in conversation
        save_data.pop('from_me', None)  # Remove campo auxiliar que não existe no modelo

        # Check if instance is inactive and mark the message
        if evolution_instance and not evolution_instance.is_active:
            save_data['received_while_inactive'] = True
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
        """Processar mensagem de áudio e retornar o texto da transcrição"""
        try:
            message.processing_status = 'processing'
            message.save()

            # Decrypt audio using the same logic as assistante
            audio_bytes = evolution_api.decrypt_whatsapp_audio(raw_data)

            if audio_bytes:
                # Transcribe audio
                transcription = transcribe_audio_from_bytes(audio_bytes.read())

                message.audio_transcription = transcription
                message.content = transcription  # Use transcription as message content
                message.save()

                # Retornar apenas a transcrição
                # message.processing_status = 'completed'
                message.save()

                return message
            else:
                message.processing_status = 'failed'
                message.content = "❌ Falha ao processar áudio"
                message.save()
                return message

        except Exception as e:
            logger.error(f"Erro processamento áudio: {e}", exc_info=True)

            message.processing_status = 'failed'
            message.content = f"❌ Erro ao processar áudio: {str(e)}"
            message.save()

            return message

    def _process_image_message(self, message, raw_data=None, evolution_instance=None):
        """Processar mensagem de imagem e retornar texto da resposta da IA"""
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
                        # Process the decrypted image and return message
                        image_response = processing_service.process_image_message_and_return_text(message)
                        if image_response:
                            message.content = image_response
                            message.save()
                        return message
                    else:
                        message.processing_status = 'failed'
                        message.content = "❌ Falha ao salvar imagem"
                        message.save()
                        return message
                else:
                    # Fallback to direct download
                    if message.media_url and processing_service.download_and_save_image(message.media_url, message):
                        image_response = processing_service.process_image_message_and_return_text(message)
                        if image_response:
                            message.content = image_response
                            message.save()
                        return message
                    else:
                        message.processing_status = 'failed'
                        message.content = "❌ Falha ao baixar imagem"
                        message.save()
                        return message
            else:
                # No raw data, try direct download
                if message.media_url and processing_service.download_and_save_image(message.media_url, message):
                    image_response = processing_service.process_image_message_and_return_text(message)
                    if image_response:
                        message.content = image_response
                        message.save()
                    return message
                else:
                    message.processing_status = 'failed'
                    message.content = "❌ Falha ao processar imagem"
                    message.save()
                    return message

        except Exception as e:
            logger.error(f"Erro processamento imagem: {e}", exc_info=True)

            message.processing_status = 'failed'
            message.content = f"❌ Erro ao processar imagem: {str(e)}"
            message.save()

            return message

    def _get_evolution_instance(self, message_data):
        """
        Busca e valida a instância Evolution baseada no instanceId da mensagem
        Retorna tupla (evolution_instance, error_response)
        - Se tudo ok: (instance, None)
        - Se houver erro: (None ou instance, Response)
        """
        raw_data = message_data.get('raw_data', {})
        instance_id = raw_data.get('instanceId')
        owner = raw_data.get('owner')

        evolution_instance = None

        # Buscar instância por instanceId
        if instance_id:
            try:
                evolution_instance = EvolutionInstance.objects.get(instance_evolution_id=instance_id)
            except Exception as e:
                pass

        # Validar se a instância foi encontrada
        if not evolution_instance:
            return None, Response({
                'status': 'error',
                'reason': 'Instância Evolution não encontrada'
            }, status=status.HTTP_404_NOT_FOUND)

        # Validar se a instância está ativa
        from_me = message_data.get('from_me', False)
        if from_me == False:
            if not evolution_instance.is_active:
                return evolution_instance, Response({
                    'status': 'ignored',
                    'reason': 'Instância está inativa'
                }, status=status.HTTP_200_OK)

        # Validar se tem agente configurado
        if not hasattr(evolution_instance, 'agent') or not evolution_instance.agent:
            return evolution_instance, Response({
                'status': 'error',
                'reason': 'Agente não configurado para esta instância'
            }, status=status.HTTP_400_BAD_REQUEST)

        return evolution_instance, None

    def _process_admin_commands(self, message_history, evolution_instance):
        """
        Processa comandos administrativos enviados pelo próprio número da instância
        Retorna Response se comando foi processado, None caso contrário
        """
        sender_number = message_history.conversation.from_number
        message_content = message_history.content.strip().lower() if message_history.content else ""

        if not message_content:
            return None

        evolution_api = EvolutionAPIService(evolution_instance)

        # Comandos especiais (começam com símbolos)
        if message_content.startswith('<<<'):
            return self._transfer_to_human(sender_number, message_history)

        if message_content.startswith('>>>'):
            return self._transfer_to_ai(evolution_api, sender_number, message_content, message_history)

        if message_content.startswith('[]'):
            return self._close_session(evolution_api, sender_number, message_content, message_history)

        if sender_number == evolution_instance.phone_number:
            # Comandos de controle da instância
            if message_content in ['ativar', 'ativar instancia', 'ligar', 'on']:
                return self._toggle_instance(evolution_instance, evolution_api, sender_number, True)

            if message_content in ['desativar', 'desativar instancia', 'desligar', 'off']:
                return self._toggle_instance(evolution_instance, evolution_api, sender_number, False)

            if message_content in ['status', 'estado', 'info']:
                return self._send_status(evolution_instance, evolution_api, sender_number)

        return None

    def _toggle_instance(self, evolution_instance, evolution_api, sender_number, activate):
        """Ativa ou desativa a instância"""
        if evolution_instance.is_active == activate:
            status_text = "ativa" if activate else "desativada"
            evolution_api.send_text_message(sender_number, f"ℹ️ A instância já está {status_text}.")
            return Response({'status': 'ignored'}, status=status.HTTP_200_OK)

        evolution_instance.is_active = activate
        evolution_instance.save(update_fields=['is_active'])

        icon = "✅" if activate else "🔴"
        action = "ativada" if activate else "desativada"
        evolution_api.send_text_message(sender_number, f"{icon} Instância '{evolution_instance.name}' foi {action}!")

        return Response({'status': 'success'}, status=status.HTTP_200_OK)

    def _send_status(self, evolution_instance, evolution_api, sender_number):
        """Envia status da instância"""
        icon = "✅" if evolution_instance.is_active else "🔴"
        status_text = "ativa" if evolution_instance.is_active else "desativada"

        msg = f"{icon} Instância '{evolution_instance.name}' está {status_text}.\n\n"
        msg += f"📱 Número: {evolution_instance.phone_number}\n"
        msg += f"🔗 Status: {evolution_instance.get_status_display()}\n\n"
        msg += "💬 Comandos:\n• ativar/desativar\n• status\n• >>> (retornar para IA)\n• [] (encerrar sessão)"

        evolution_api.send_text_message(sender_number, msg)
        return Response({'status': 'success'}, status=status.HTTP_200_OK)

    def _transfer_to_human(self, sender_number, message_history):
        """Transfere sessão para atendimento humano"""
        Conversation.objects.filter(
            evolution_instance=message_history.conversation.evolution_instance,
            from_number=sender_number
        ).update(status='human')

        return Response({'status': 'success'}, status=status.HTTP_200_OK)

    def _transfer_to_ai(self, evolution_api, sender_number, message_content, message_history):
        """Retorna sessão para atendimento por IA"""
        parts = message_content.strip().split()
        target = clean_number_whatsapp(parts[1]) if len(parts) > 1 else sender_number

        updated = Conversation.objects.filter(
            from_number=target,
            evolution_instance=message_history.conversation.evolution_instance,
            status='human'
        ).update(status='ai')

        if not updated:
            evolution_api.send_text_message(sender_number, f"❌ Nenhuma sessão HUMAN encontrada para {target}")
            return Response({'status': 'error'}, status=status.HTTP_404_NOT_FOUND)

        return Response({'status': 'success'}, status=status.HTTP_200_OK)

    def _close_session(self, evolution_api, sender_number, message_content, message_history):
        """Encerra uma sessão"""
        parts = message_content.strip().split()
        target = clean_number_whatsapp(parts[1]) if len(parts) > 1 else sender_number

        updated = Conversation.objects.filter(
            from_number=target,
            evolution_instance=message_history.conversation.evolution_instance
        ).update(status='closed')

        if not updated:
            evolution_api.send_text_message(sender_number, f"❌ Nenhuma sessão encontrada para {target}")
            return Response({'status': 'error'}, status=status.HTTP_404_NOT_FOUND)

        evolution_api.send_text_message(sender_number, f"✅ Sessão de {target} foi encerrada")
        return Response({'status': 'success'}, status=status.HTTP_200_OK)

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

        results = []

        # Enviar texto primeiro se não estiver vazio
        if text:
            text_result = evolution_api.send_text_message(to_number, text)
            results.append(text_result)

        # Enviar arquivo depois se não estiver vazio
        if file_url:
            # Verificar se é URL válida
            if file_url.startswith(('http://', 'https://')):
                file_result = evolution_api.send_file_message(to_number, file_url)
                results.append(file_result)
            else:
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



