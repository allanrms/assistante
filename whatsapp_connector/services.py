import os
import traceback
import json

import requests
import base64
import io
import hmac
import hashlib

from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import HKDF
from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image
from io import BytesIO
from .models import ImageProcessingJob
from .utils import clean_number_whatsapp


class EvolutionAPIService:
    def __init__(self, instance):
        self.base_url = settings.EVOLUTION_API_BASE_URL
        self.instance = instance

    def check_whatsapp_numbers(self, numbers):
        """Check if numbers have WhatsApp using Evolution API"""
        url = f"{self.base_url}/chat/whatsappNumbers/{self.instance.instance_name}"

        headers = {
            "apikey": self.instance.api_key,
            "Content-Type": "application/json"
        }

        # Clean numbers and ensure they're in list format
        if isinstance(numbers, str):
            numbers = [numbers]

        clean_numbers = [clean_number_whatsapp(num) for num in numbers]
        payload = {"numbers": clean_numbers}

        try:
            print(f"🔍 Verificando números no WhatsApp: {clean_numbers}")
            response = requests.post(url, json=payload, headers=headers, timeout=10)

            if response.status_code == 200:
                result = response.json()
                print(f"✅ Verificação de números concluída: {result}")
                return result
            else:
                print(f"⚠️ Erro na verificação de números: {response.status_code} - {response.text}")
                return None

        except requests.RequestException as e:
            print(f"❌ Erro ao verificar números no WhatsApp: {e}")
            return None

    def send_text_message(self, to_number, message):
        """Send text message using Evolution API"""
        url = f"{self.base_url}/message/sendText/{self.instance.instance_name}"

        headers = {
            "apikey": self.instance.api_key,
            "Content-Type": "application/json"
        }
        
        # Clean up the number format - remove @s.whatsapp.net if present
        clean_number = clean_number_whatsapp(to_number)

        payload = {
            "number": clean_number,
            "text": message,
            "options": {
                "delay": 1200,
                "presence": "composing",
                "linkPreview": False
            }
        }
        
        print(f"📤 Enviando mensagem via Evolution API:")
        print(f"   URL: {url}")
        print(f"   Número original: {to_number}")
        print(f"   Número limpo: {clean_number}")
        print(f"   Mensagem: {message}")
        print(f"   Payload: {payload}")
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            print(f"   Status: {response.status_code}")
            if response.status_code != 200:
                print(f"   Response body1: {response.text}")

            # Verificar se houve erro específico do WhatsApp antes de raise_for_status
            if response.status_code == 400:
                try:
                    error_data = response.json()
                    if 'response' in error_data and 'message' in error_data['response']:
                        messages = error_data['response']['message']
                        if isinstance(messages, list) and len(messages) > 0:
                            message_info = messages[0]
                            if message_info.get('exists') is False:
                                number = message_info.get('number', clean_number)
                                print(f"⚠️ Número {number} não tem WhatsApp ou não existe")
                                return {'error': 'number_not_exists', 'number': number, 'message': 'Número não tem WhatsApp'}
                except:
                    pass  # Se não conseguir parsear, continua com o fluxo normal

            response.raise_for_status()
            # print(f"✅ Mensagem enviada com sucesso: {response.text}")

            return response.json()
        except requests.RequestException as e:
            print(f"❌ Erro ao enviar mensagem: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Response status: {e.response.status_code}")
                print(f"   Response body2: {e.response.text}")

                # Tentar extrair informação mais específica do erro
                try:
                    error_data = e.response.json()
                    if e.response.status_code == 400 and 'response' in error_data and 'message' in error_data['response']:
                        messages = error_data['response']['message']
                        if isinstance(messages, list) and len(messages) > 0:
                            message_info = messages[0]
                            if message_info.get('exists') is False:
                                number = message_info.get('number', clean_number)
                                return {'error': 'number_not_exists', 'number': number, 'message': 'Número não tem WhatsApp'}
                except:
                    pass

            traceback.print_exc()
            return None
    
    def send_file_message(self, to_number, file_url_or_path, caption=None):
        """Send file message using Evolution API with base64 encoding"""
        url = f"{self.base_url}/message/sendMedia/{self.instance.instance_name}"

        headers = {
            "apikey": self.instance.api_key,
            "Content-Type": "application/json"
        }
        
        # Clean up the number format
        clean_number = clean_number_whatsapp(to_number)
        
        try:
            # Determinar se é URL ou caminho local e baixar/ler o arquivo
            if file_url_or_path.startswith(('http://', 'https://')):
                # É uma URL - fazer download
                print(f"📥 Baixando arquivo de: {file_url_or_path}")
                file_response = requests.get(file_url_or_path, timeout=30)
                file_response.raise_for_status()
                file_data = file_response.content
                
                # Tentar detectar tipo de arquivo pelo Content-Type
                content_type = file_response.headers.get('content-type', '').lower()
                if 'image' in content_type:
                    media_type = "image"
                    file_name = "downloaded_image.jpg"
                elif 'video' in content_type:
                    media_type = "video"
                    file_name = "downloaded_video.mp4"
                elif 'audio' in content_type:
                    media_type = "audio"
                    file_name = "downloaded_audio.mp3"
                else:
                    media_type = "document"
                    file_name = "downloaded_file.pdf"
                    
                # Tentar obter nome real do arquivo da URL
                file_name = self._get_real_filename_from_url(file_url_or_path, file_name)
                    
            else:
                # É caminho local - ler arquivo
                print(f"📁 Lendo arquivo local: {file_url_or_path}")
                with open(file_url_or_path, 'rb') as file:
                    file_data = file.read()
                
                # Detectar tipo pelo nome do arquivo
                file_extension = file_url_or_path.lower().split('.')[-1]
                file_name = file_url_or_path.split('/')[-1]
                
                if file_extension in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                    media_type = "image"
                elif file_extension in ['mp4', 'avi', 'mov', 'webm']:
                    media_type = "video"
                elif file_extension in ['mp3', 'wav', 'ogg', 'm4a']:
                    media_type = "audio"
                else:
                    media_type = "document"
            
            # Converter para base64
            base64_string = base64.b64encode(file_data).decode('utf-8')
            
            # Para imagens, SEMPRE converter para JPEG (WhatsApp funciona melhor)
            if media_type == "image":
                print(f"🔄 Processando imagem para WhatsApp...")
                try:
                    from PIL import Image
                    from io import BytesIO
                    
                    # Reabrir a imagem e processar
                    image = Image.open(BytesIO(file_data))
                    original_size = image.size
                    original_mode = image.mode
                    print(f"📊 Imagem original: {original_size} - {original_mode}")
                    
                    # SEMPRE redimensionar se muito grande (WhatsApp tem limites)
                    max_size = 1024
                    if max(image.size) > max_size:
                        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                        print(f"📐 Redimensionado: {original_size} → {image.size}")
                    
                    # SEMPRE converter para RGB/JPEG (remove transparência, PNG, etc)
                    if image.mode in ('RGBA', 'LA', 'P'):
                        print(f"🎨 Convertendo {original_mode} → RGB (removendo transparência)")
                        background = Image.new('RGB', image.size, (255, 255, 255))
                        if image.mode == 'P':
                            image = image.convert('RGBA')
                        background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
                        image = background
                    elif image.mode != 'RGB':
                        print(f"🎨 Convertendo {original_mode} → RGB")
                        image = image.convert('RGB')
                    
                    # SEMPRE salvar como JPEG otimizado para WhatsApp
                    optimized_buffer = BytesIO()
                    # Usar qualidade mais alta se arquivo não é muito grande
                    quality = 85 if len(file_data) < 500000 else 70  # 500KB threshold
                    image.save(optimized_buffer, format='JPEG', quality=quality, optimize=True)
                    optimized_data = optimized_buffer.getvalue()
                    base64_string = base64.b64encode(optimized_data).decode('utf-8')
                    file_data = optimized_data  # Atualizar para logs
                    
                    # Atualizar nome do arquivo para .jpg
                    if not file_name.lower().endswith(('.jpg', '.jpeg')):
                        file_name = file_name.rsplit('.', 1)[0] + '.jpg' if '.' in file_name else file_name + '.jpg'
                    
                    print(f"✅ Imagem convertida para JPEG: {len(file_data)} bytes ({len(base64_string)} chars base64)")
                    print(f"📱 Nome final: {file_name}")
                    
                except Exception as e:
                    print(f"⚠️ Erro ao processar imagem: {e}")
                    # Continua com imagem original
            
            # Preparar payload no formato unificado da Evolution API
            # payload = {
            #     "number": clean_number,
            #     "mediaMessage": {
            #         "mediatype": media_type,
            #         "media": base64_string,
            #         "fileName": file_name
            #     },
            #     "options": {
            #         "delay": 100,
            #         "presence": "composing"
            #     }
            # }

            payload = {
                "number": clean_number,
                "mediatype": media_type,
                "mimetype": "image/png",
                "caption": caption if caption else os.path.splitext(file_name)[0],
                "media": base64_string,
                "fileName": file_name,
            }
            
            print(f"📎 Enviando arquivo via Evolution API:")
            print(f"   URL: {url}")
            print(f"   Número: {clean_number}")
            print(f"   Tipo: {media_type}")
            print(f"   Nome: {file_name}")
            print(f"   Tamanho: {len(file_data)} bytes")
            print(f"   Caption: {caption}")
            
            response = requests.post(url, json=payload, headers=headers)
            print(f"   Status: {response.status_code}")
            if response.status_code != 200:
                print(f"   Response body: {response.text}")
            response.raise_for_status()
            print(f"✅ Arquivo enviado com sucesso: {response.text}")

            return response.json()
            
        except requests.RequestException as e:
            print(f"❌ Erro ao processar/enviar arquivo: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Response status: {e.response.status_code}")
                print(f"   Response body: {e.response.text}")
            traceback.print_exc()
            return None
        except FileNotFoundError:
            print(f"❌ Arquivo não encontrado: {file_url_or_path}")
            return None
        except Exception as e:
            print(f"❌ Erro inesperado ao enviar arquivo: {e}")
            traceback.print_exc()
            return None
    
    def _get_real_filename_from_url(self, file_url, fallback_name):
        """
        Tenta extrair o nome real do arquivo da URL, buscando no banco de dados
        """
        try:
            # Importar apenas quando necessário para evitar circular imports
            from agents.models import AssistantContextFile
            
            # Buscar arquivo no banco pela URL
            context_file = AssistantContextFile.objects.filter(
                file__icontains=file_url.split('/')[-1].split('.')[0]  # Buscar pelo nome sem extensão
            ).first()
            
            if context_file and context_file.name:
                print(f"✓ Nome real encontrado no banco: {context_file.name}")
                return context_file.name
            
            # Se não encontrou no banco, tentar extrair da URL
            try:
                from urllib.parse import unquote
                url_parts = file_url.split('/')
                if len(url_parts) > 0:
                    filename_from_url = unquote(url_parts[-1])  # Decodificar URL encoding
                    if '.' in filename_from_url and len(filename_from_url) > 3:
                        print(f"✓ Nome extraído da URL: {filename_from_url}")
                        return filename_from_url
            except Exception as e:
                print(f"Erro ao extrair nome da URL: {e}")
            
            print(f"Usando nome fallback: {fallback_name}")
            return fallback_name
            
        except Exception as e:
            print(f"Erro ao buscar nome real do arquivo: {e}")
            return fallback_name
    
    def decrypt_whatsapp_audio(self, message_data):
        """Decrypt WhatsApp audio message using the same logic from assistante"""
        try:
            # Extract audio message info - handle both direct message data and webhook data
            if 'message' in message_data and 'audioMessage' in message_data['message']:
                # Direct message structure
                audio_msg = message_data['message']['audioMessage']
            elif 'data' in message_data and 'message' in message_data['data']:
                # Webhook structure - extract from data.message
                message_obj = message_data['data']['message']
                if 'audioMessage' in message_obj:
                    audio_msg = message_obj['audioMessage']
                else:
                    print("audioMessage not found in webhook data structure")
                    return None
            elif 'audioMessage' in message_data:
                # Direct audioMessage structure
                audio_msg = message_data['audioMessage']
            else:
                print(f"Could not find audioMessage in data structure. Available keys: {list(message_data.keys())}")
                return None
            enc_url = audio_msg['url']
            media_key_b64 = audio_msg['mediaKey']

            # 1) Download encrypted media
            enc_data = requests.get(enc_url).content

            # 2) HKDF (112 bytes) with Audio type info
            media_key = base64.b64decode(media_key_b64)
            info = b"WhatsApp Audio Keys"

            derived = HKDF(master=media_key, key_len=112, salt=None, hashmod=SHA256, context=info)

            # Correct order:
            iv = derived[0:16]
            cipher_key = derived[16:48]
            mac_key = derived[48:80]
            # derived[80:112] is unused

            # 3) Separate ciphertext and tag (last 10 bytes)
            file_data = enc_data[:-10]  # ciphertext (still with padding)
            mac_tag = enc_data[-10:]   # 10-byte tag

            # 4) Verify MAC (include IV in calculation)
            calc_mac = hmac.new(mac_key, iv + file_data, hashlib.sha256).digest()[:10]
            if calc_mac != mac_tag:
                raise ValueError("Invalid MAC")

            # 5) Decrypt AES-CBC with PKCS#7
            cipher = AES.new(cipher_key, AES.MODE_CBC, iv)
            decrypted = cipher.decrypt(file_data)

            # Remove PKCS#7 padding
            pad_len = decrypted[-1]
            if pad_len < 1 or pad_len > 16:
                raise ValueError("Invalid padding")
            decrypted = decrypted[:-pad_len]

            # 6) Return audio bytes as BytesIO
            return io.BytesIO(decrypted)
            
        except Exception as e:
            print(f"Error decrypting audio: {e}")
            traceback.print_exc()
            return None
    
    def decrypt_whatsapp_image(self, message_data):
        """Decrypt WhatsApp image message using similar logic to audio"""
        try:
            # Extract image message info - handle both direct message data and webhook data
            if 'message' in message_data and 'imageMessage' in message_data['message']:
                # Direct message structure
                image_msg = message_data['message']['imageMessage']
            elif 'data' in message_data and 'message' in message_data['data']:
                # Webhook structure - extract from data.message
                message_obj = message_data['data']['message']
                if 'imageMessage' in message_obj:
                    image_msg = message_obj['imageMessage']
                else:
                    print("imageMessage not found in webhook data structure")
                    return None
            elif 'imageMessage' in message_data:
                # Direct imageMessage structure
                image_msg = message_data['imageMessage']
            else:
                print(f"Could not find imageMessage in data structure. Available keys: {list(message_data.keys())}")
                return None
            enc_url = image_msg['url']
            media_key_b64 = image_msg['mediaKey']

            print(f"Decriptografando imagem de: {enc_url}")
            
            # 1) Download encrypted media
            enc_data = requests.get(enc_url).content
            print(f"Downloaded encrypted data: {len(enc_data)} bytes")

            # 2) HKDF (112 bytes) with Image type info
            media_key = base64.b64decode(media_key_b64)
            print(f"Media key length: {len(media_key)} bytes")
            info = b"WhatsApp Image Keys"  # Different from audio
            try:
                derived = HKDF(media_key, 112, salt=None, info=info, hashmod=SHA256)
                print(f"HKDF derived key length: {len(derived)} bytes")
            except Exception as hkdf_error:
                print(f"HKDF derivation failed: {hkdf_error}")
                return None

            # Correct order:
            iv = derived[0:16]
            cipher_key = derived[16:48]
            mac_key = derived[48:80]
            # derived[80:112] is unused

            # 3) Separate ciphertext and tag (last 10 bytes)
            file_data = enc_data[:-10]  # ciphertext (still with padding)
            mac_tag = enc_data[-10:]   # 10-byte tag

            # 4) Verify MAC (include IV in calculation)
            calc_mac = hmac.new(mac_key, iv + file_data, hashlib.sha256).digest()[:10]
            print(f"Calculated MAC: {calc_mac.hex()}")
            print(f"Expected MAC: {mac_tag.hex()}")
            if calc_mac != mac_tag:
                print("MAC validation failed - trying different MAC calculation methods")
                # Try without IV (some implementations don't include IV)
                calc_mac_no_iv = hmac.new(mac_key, file_data, hashlib.sha256).digest()[:10]
                print(f"MAC without IV: {calc_mac_no_iv.hex()}")
                if calc_mac_no_iv != mac_tag:
                    print("All MAC validation methods failed")
                    return None
                else:
                    print("MAC validation succeeded without IV")
            else:
                print("MAC validation succeeded with IV")

            # 5) Decrypt AES-CBC with PKCS#7
            cipher = AES.new(cipher_key, AES.MODE_CBC, iv)
            decrypted = cipher.decrypt(file_data)

            # Remove PKCS#7 padding
            pad_len = decrypted[-1]
            if pad_len < 1 or pad_len > 16:
                raise ValueError("Invalid padding")
            decrypted = decrypted[:-pad_len]

            print(f"Successfully decrypted image: {len(decrypted)} bytes")
            print(f"First 20 bytes of decrypted: {decrypted[:20].hex()}")
            
            # Validate that decrypted data is a valid image
            try:
                from PIL import Image
                test_image = Image.open(io.BytesIO(decrypted))
                print(f"✓ Decrypted image is valid: {test_image.format} {test_image.mode} {test_image.size}")
                test_image.close()
            except Exception as img_error:
                print(f"✗ Decrypted data is not a valid image: {img_error}")
                # Try different padding removal approaches
                for pad_attempt in [1, 2, 3, 4, 8, 16]:
                    try:
                        test_decrypted = decrypted[:-pad_attempt] if len(decrypted) > pad_attempt else decrypted
                        test_image = Image.open(io.BytesIO(test_decrypted))
                        print(f"✓ Valid image found with padding adjustment -{pad_attempt}: {test_image.format}")
                        decrypted = test_decrypted
                        test_image.close()
                        break
                    except:
                        continue
                else:
                    print("Could not create valid image even with padding adjustments")
                    return None
            
            # 6) Return image bytes as BytesIO
            return io.BytesIO(decrypted)
            
        except Exception as e:
            print(f"Error decrypting image: {e}")
            traceback.print_exc()
            return None


class N8NService:
    def __init__(self):
        self.webhook_url = getattr(settings, 'N8N_WEBHOOK_URL')
    
    def send_image_for_processing(self, image_data, message_data):
        """Send image data to n8n webhook for processing"""
        if not self.webhook_url or self.webhook_url == 'http://localhost:5678/webhook/whatsapp-image':
            print("N8N webhook URL não configurada corretamente")
            return None
            
        try:
            payload = {
                'image_data': image_data,
                'message_id': message_data.get('message_id'),
                'from_number': message_data.get('from_number'),
                'timestamp': message_data.get('timestamp'),
                'action': 'processImage'
            }
            
            print(f"Enviando para n8n: {self.webhook_url}")
            response = requests.post(self.webhook_url, json=payload, timeout=30)
            
            if response.status_code == 404:
                print(f"Webhook n8n não encontrado (404): {self.webhook_url}")
                return None
            elif response.status_code == 200:
                print("Enviado para n8n com sucesso")
                return response.json()
            else:
                print(f"N8n retornou status {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            print("Timeout ao conectar com n8n")
            return None
        except requests.RequestException as e:
            print(f"Error sending to n8n: {e}")
            print(f"URL tentativa: {self.webhook_url}")
            return None
    
    def send_message_to_n8n(self, sender_jid, sender_name, text_message):
        """Send message to n8n using the same format as assistante app"""
        import datetime
        
        payload = {
            "sessionId": sender_jid,
            "whatsappReponse": f'+{str(sender_jid).split("@")[0]}',
            "action": "sendMessage",
            "chatInput": text_message,
            "senderName": sender_name,
            "now": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        
        try:
            response = requests.post(self.webhook_url, json=payload)

            print(self.webhook_url)
            print(payload)
            print(response)

            if response.status_code == 200:
                result = response.json()
                if result.get('message') == 'Workflow was started':
                    print("Enviado para o n8n com sucesso!")
                    return result
                else:
                    print("N8n workflow não foi iniciado")
                    return None
            else:
                print(f"N8n error: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            print(f"Error sending to n8n: {e}")
            traceback.print_exc()
            return None


class AIVisionService:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        # Lista de modelos para tentar, do mais recente para o mais antigo
        self.models = [
            'gpt-4o',  # Modelo mais recente com visão
            'gpt-4o-mini',  # Modelo mini com visão
            'gpt-4-turbo',  # Versão turbo
            'gpt-4-vision-preview'  # Modelo antigo (deprecated but still works)
        ]
        self.model = getattr(settings, 'AI_MODEL', self.models[0])
    
    def _process_and_validate_image(self, image_data):
        """Processa e valida a imagem para garantir compatibilidade com OpenAI"""
        try:
            # Decodificar base64 para bytes
            image_bytes = base64.b64decode(image_data)
            
            # Abrir a imagem usando PIL para validar e converter
            image = Image.open(BytesIO(image_bytes))
            
            print(f"Imagem original: {image.format} {image.mode} {image.size}")
            
            # Converter para RGB se necessário (remove transparência, etc)
            if image.mode in ('RGBA', 'LA', 'P'):
                print(f"Convertendo imagem de {image.mode} para RGB")
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Verificar tamanho e redimensionar se necessário
            max_dimension = 2048  # OpenAI recomenda máximo 2048px
            width, height = image.size
            
            if width > max_dimension or height > max_dimension:
                print(f"Redimensionando imagem de {width}x{height}")
                
                # Calcular nova dimensão mantendo aspect ratio
                if width > height:
                    new_width = max_dimension
                    new_height = int(height * max_dimension / width)
                else:
                    new_height = max_dimension
                    new_width = int(width * max_dimension / height)
                
                # Redimensionar
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                print(f"Imagem redimensionada para {new_width}x{new_height}")
            
            # Converter para JPEG de alta qualidade
            buffer = BytesIO()
            image.save(buffer, format='JPEG', quality=90, optimize=True)
            processed_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            print(f"Imagem processada: tamanho final ~{len(processed_b64) * 3/4 / 1024 / 1024:.2f} MB")
            return processed_b64
            
        except Exception as e:
            print(f"Erro ao processar imagem: {e}")
            traceback.print_exc()
            return image_data
    
    def _try_model(self, model, image_data, prompt):
        """Tenta analisar imagem com um modelo específico"""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        # Debug: verificar tamanho da imagem
        image_size_mb = len(image_data) * 3/4 / 1024 / 1024  # Aproximado do tamanho em MB
        print(f"Tamanho da imagem base64 original: ~{image_size_mb:.2f} MB")
        
        # Sempre processar e validar a imagem para garantir compatibilidade
        image_data = self._process_and_validate_image(image_data)
        
        # Validar prompt
        if not prompt or len(prompt.strip()) == 0:
            prompt = """Você é um assistente inteligente que analisa faturas de energia elétrica em imagens. Sua tarefa é descrever o que você vê e extrair os seguintes dados em português:

1. Nome e endereço do cliente
2. Valor total a pagar
3. Consumo em kWh

Por favor, forneça as informações de forma clara, separadas e organizadas. Se algum dado não estiver visível ou não puder ser identificado com certeza, indique 'Não encontrado'."""
        
        # Use the standard OpenAI Chat Completions API format
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}",
                                "detail": "auto"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 300
        }
        
        print(f"Enviando payload com modelo {model}, prompt: '{prompt[:50]}...'")
        print(f"Tamanho do payload: {len(json.dumps(payload))} bytes")
        
        # Use only the standard OpenAI Chat Completions endpoint
        endpoint = 'https://api.openai.com/v1/chat/completions'
        
        print(f"Enviando requisição para: {endpoint}")
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=30
            )
        except requests.exceptions.RequestException as e:
            print(f"Erro na requisição: {e}")
            return None
        
        return response

    def analyze_image(self, image_data, prompt=None):
        """Analisa imagem usando OpenAI Vision API com fallback de modelos"""
        
        # Verificar se a API key está configurada
        if not self.api_key or self.api_key in ['your_ai_api_key', 'your_openai_api_key_here', None, '']:
            print("OpenAI API key não configurada. Configure OPENAI_API_KEY no arquivo .env")
            return "Análise de imagem não disponível (API key não configurada)"
        
        # Verificar se a API key tem formato válido (deve começar com sk-)
        if not self.api_key.startswith('sk-'):
            print(f"API key inválida - deve começar com 'sk-'. Atual: {self.api_key[:10]}...")
            return "Erro: Chave da API OpenAI inválida (formato incorreto)"
        
        # Primeiro tenta com o modelo configurado
        models_to_try = [self.model] + [m for m in self.models if m != self.model]
        
        for model in models_to_try:
            try:
                print(f"Tentando análise com modelo: {model}")
                response = self._try_model(model, image_data, prompt)
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"Resposta recebida: {list(result.keys())}")
                    
                    # Standard OpenAI Chat Completions API format
                    if 'choices' in result and len(result['choices']) > 0:
                        print(f"Análise bem-sucedida com modelo: {model}")
                        return result['choices'][0]['message']['content']
                    else:
                        print(f"Resposta inesperada do modelo {model}: {result}")
                        continue
                
                elif response.status_code == 401:
                    print("Erro 401: Chave da API OpenAI inválida")
                    return "Erro: Chave da API OpenAI inválida"
                
                elif response.status_code == 400:
                    error_detail = response.json().get('error', {}).get('message', 'Erro desconhecido')
                    print(f"Erro 400 com modelo {model}: {error_detail}")
                    # Para erro 400, não tenta outros modelos pois o problema é com os dados
                    return f"Erro na requisição: {error_detail}"
                
                elif response.status_code == 404:
                    print(f"Modelo {model} não disponível (404), tentando próximo...")
                    continue
                
                elif response.status_code == 429:
                    print("Erro 429: Limite de rate da API OpenAI excedido")
                    return "Erro: Muitas requisições para a API"
                
                else:
                    print(f"Erro {response.status_code} com modelo {model}")
                    try:
                        error_detail = response.json().get('error', {}).get('message', 'Erro desconhecido')
                        print(f"Detalhes do erro: {error_detail}")
                    except:
                        print(f"Response body: {response.text}")
                    continue
                    
            except requests.exceptions.Timeout:
                print(f"Timeout com modelo {model}, tentando próximo...")
                continue
            except requests.exceptions.RequestException as e:
                print(f"Erro de requisição com modelo {model}: {e}")
                continue
            except Exception as e:
                print(f"Erro inesperado com modelo {model}: {e}")
                continue
        
        # Se chegou aqui, todos os modelos falharam
        print("Todos os modelos falharam")
        return "Erro: Nenhum modelo de IA disponível no momento"


class ImageProcessingService:
    def __init__(self, evolution_instance=None):
        self.evolution_instance = evolution_instance
        self.evolution_api = EvolutionAPIService(evolution_instance) if evolution_instance else None
        self.n8n_service = N8NService()
        self.ai_service = AIVisionService()
    
    def download_and_save_image(self, media_url, message):
        """Download image from WhatsApp URL and save it"""
        try:
            print(f"Baixando imagem de: {media_url}")
            
            # Headers para simular um browser real
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(media_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            print(f"Response status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type')}")
            print(f"Content-Length: {len(response.content)} bytes")
            print(f"Response headers: {dict(response.headers)}")
            
            # Verificar se realmente é uma imagem
            content = response.content
            
            if len(content) < 100:  # Muito pequeno para ser uma imagem
                print(f"Conteúdo muito pequeno: {len(content)} bytes")
                return False
            
            # Debug detalhado do conteúdo
            print(f"Primeiros 50 bytes (hex): {content[:50].hex()}")
            print(f"Primeiros 50 bytes (repr): {repr(content[:50])}")
            
            # Se começar com HTML, pode ser uma página de erro
            if content[:100].lower().startswith(b'<!doctype') or content[:100].lower().startswith(b'<html'):
                print("ERRO: Resposta parece ser HTML, não uma imagem")
                print(f"Início da resposta: {content[:200].decode('utf-8', errors='ignore')}")
                return False
            
            # Verificar magic numbers de formatos de imagem
            file_extension = "jpg"  # Padrão
            if content.startswith(b'\xff\xd8\xff'):
                print("Formato detectado por magic number: JPEG")
                file_extension = "jpg"
            elif content.startswith(b'\x89PNG\r\n\x1a\n'):
                print("Formato detectado por magic number: PNG")
                file_extension = "png"
            elif content.startswith(b'GIF8'):
                print("Formato detectado por magic number: GIF")
                file_extension = "gif"
            elif content.startswith(b'RIFF') and b'WEBP' in content[:12]:
                print("Formato detectado por magic number: WEBP")
                file_extension = "webp"
            else:
                print("AVISO: Formato não reconhecido pelos magic numbers")
                # Tentar inferir do Content-Type
                content_type = response.headers.get('content-type', '').lower()
                if 'jpeg' in content_type or 'jpg' in content_type:
                    file_extension = "jpg"
                elif 'png' in content_type:
                    file_extension = "png"
                elif 'gif' in content_type:
                    file_extension = "gif"
                elif 'webp' in content_type:
                    file_extension = "webp"
                else:
                    print(f"Content-Type também não reconhecido: {content_type}")
            
            # Validar se é uma imagem válida usando PIL - mais detalhado
            try:
                print("Tentando abrir imagem com PIL...")
                test_image = Image.open(BytesIO(content))
                print(f"✓ PIL conseguiu abrir: format={test_image.format}, mode={test_image.mode}, size={test_image.size}")
                actual_format = test_image.format.lower() if test_image.format else 'unknown'
                test_image.close()
                
                # Usar o formato detectado pelo PIL se válido
                if actual_format in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                    file_extension = 'jpg' if actual_format == 'jpeg' else actual_format
                    print(f"Usando extensão baseada no PIL: {file_extension}")
                
            except Exception as img_error:
                print(f"✗ PIL falhou ao validar imagem: {img_error}")
                print(f"Tipo do erro: {type(img_error).__name__}")
                
                # Análise adicional quando PIL falha
                print("Fazendo análise adicional do conteúdo...")
                
                # Verificar se pode ser um arquivo corrompido
                if len(content) > 1000:
                    # Verificar se há padrões típicos de corrupção
                    null_count = content.count(b'\x00')
                    print(f"Bytes nulos encontrados: {null_count}")
                    
                    # Verificar se parece com dados binários válidos
                    try:
                        # Tenta decodificar como texto - se funcionar, provavelmente não é imagem
                        text_content = content.decode('utf-8')
                        print("ERRO: Conteúdo pode ser decodificado como texto UTF-8!")
                        print(f"Primeiros 200 chars: {text_content[:200]}")
                        return False
                    except UnicodeDecodeError:
                        print("✓ Conteúdo parece ser binário (não é texto)")
                
                # Mesmo com erro PIL, tenta salvar para debug
                print(f"Tentando salvar mesmo assim como {file_extension} para análise posterior")
            
            # Create a file from the downloaded content
            file_content = ContentFile(content)
            file_name = f"whatsapp_image_{message.message_id}.{file_extension}"
            
            print(f"Salvando como: {file_name}")
            message.media_file.save(file_name, file_content)
            message.save()
            
            print("✓ Arquivo salvo com sucesso")
            return True
            
        except requests.exceptions.Timeout:
            print("Timeout ao baixar imagem")
            return False
        except requests.exceptions.RequestException as e:
            print(f"Erro de requisição ao baixar imagem: {e}")
            return False
        except Exception as e:
            print(f"Erro inesperado ao baixar imagem: {e}")
            traceback.print_exc()
            return False
    
    def save_decrypted_image(self, decrypted_image_io, message):
        """Save decrypted image BytesIO to the message"""
        try:
            # Read the decrypted image content
            decrypted_image_io.seek(0)
            image_content = decrypted_image_io.read()
            
            print(f"Salvando imagem descriptografada: {len(image_content)} bytes")
            print(f"Primeiros 20 bytes: {image_content[:20].hex()}")
            
            # Validate it's a proper image using PIL
            try:
                test_image = Image.open(BytesIO(image_content))
                print(f"✓ Imagem descriptografada válida: {test_image.format} {test_image.mode} {test_image.size}")
                format_extension = test_image.format.lower() if test_image.format else 'jpg'
                if format_extension == 'jpeg':
                    format_extension = 'jpg'
                test_image.close()
            except Exception as img_error:
                print(f"✗ Imagem descriptografada inválida: {img_error}")
                return False
            
            # Create a file from the decrypted content
            file_content = ContentFile(image_content)
            file_name = f"whatsapp_image_decrypted_{message.message_id}.{format_extension}"
            
            print(f"Salvando como: {file_name}")
            message.media_file.save(file_name, file_content)
            message.save()
            
            print("✓ Imagem descriptografada salva com sucesso")
            return True
            
        except Exception as e:
            print(f"Erro ao salvar imagem descriptografada: {e}")
            traceback.print_exc()
            return False
    
    def process_image_message(self, message):
        """Process an image message with AI and/or n8n"""
        try:
            # First, download the image if we don't have it locally
            if not message.media_file and message.media_url:
                print(f"Baixando imagem de: {message.media_url}")
                if not self.download_and_save_image(message.media_url, message):
                    print("Falhou ao baixar a imagem")
                    message.processing_status = 'failed'
                    message.save()
                    return False
            
            if not message.media_file:
                print("Nenhuma imagem disponível para processar")
                message.processing_status = 'failed'
                message.save()
                return False
            
            # Convert image to base64
            print("Convertendo imagem para base64...")
            with message.media_file.open('rb') as image_file:
                image_content = image_file.read()
                
            # Validar se é uma imagem válida
            try:
                print("Validando imagem salva com PIL...")
                print(f"Tamanho do arquivo: {len(image_content)} bytes")
                print(f"Primeiros 20 bytes: {image_content[:20].hex()}")
                
                test_image = Image.open(BytesIO(image_content))
                print(f"✓ Imagem válida: format={test_image.format}, mode={test_image.mode}, size={test_image.size}")
                test_image.close()
                
            except Exception as img_error:
                print(f"✗ Primeira validação de imagem falhou: {img_error}")
                print(f"Tipo do erro: {type(img_error).__name__}")
                
                # Debug adicional do conteúdo do arquivo salvo
                if len(image_content) < 100:
                    print(f"ERRO: Arquivo muito pequeno: {len(image_content)} bytes")
                elif image_content[:100].lower().startswith(b'<!doctype') or image_content[:100].lower().startswith(b'<html'):
                    print("ERRO: Arquivo salvo contém HTML, não é uma imagem")
                    print(f"Conteúdo: {image_content[:200].decode('utf-8', errors='ignore')}")
                else:
                    print("Arquivo parece ser binário, mas PIL não consegue abrir")
                
                # Tentar baixar novamente se ainda temos a URL
                if message.media_url:
                    print("Tentando baixar a imagem novamente...")
                    if self.download_and_save_image(message.media_url, message):
                        # Tentar validar novamente
                        try:
                            with message.media_file.open('rb') as image_file:
                                new_image_content = image_file.read()
                            print(f"Novo conteúdo: {len(new_image_content)} bytes")
                            print(f"Novos primeiros 20 bytes: {new_image_content[:20].hex()}")
                            
                            test_image = Image.open(BytesIO(new_image_content))
                            print(f"✓ Imagem válida após re-download: {test_image.format} {test_image.mode} {test_image.size}")
                            image_content = new_image_content  # Usar o novo conteúdo
                            test_image.close()
                        except Exception as retry_error:
                            print(f"✗ Re-validação também falhou: {retry_error}")
                            print(f"Tipo do erro: {type(retry_error).__name__}")
                            message.processing_status = 'failed'
                            message.save()
                            return False
                    else:
                        print("✗ Re-download também falhou")
                        message.processing_status = 'failed'
                        message.save()
                        return False
                else:
                    print("✗ Não é possível re-baixar a imagem (sem URL)")
                    message.processing_status = 'failed' 
                    message.save()
                    return False
            
            image_data = base64.b64encode(image_content).decode('utf-8')
            print(f"Imagem convertida para base64: {len(image_data)} caracteres")
            
            # Create processing job for AI
            ai_job = ImageProcessingJob.objects.create(
                message=message,
                processor_type='ai',
                status='queued'
            )
            
            # Process with AI
            ai_job.status = 'processing'
            ai_job.save()
            
            ai_result = self.ai_service.analyze_image(image_data)
            if ai_result and not ai_result.startswith("Erro"):
                ai_job.result = {'analysis': ai_result}
                ai_job.status = 'completed'
                message.ai_response = ai_result

                # Send AI response back to WhatsApp
                if self.evolution_api:
                    self.evolution_api.send_text_message(
                        message.chat_session.from_number,
                        f"⚡ Análise da Fatura de Energia:\n\n{ai_result}"
                    )
            else:
                ai_job.status = 'failed'
                ai_job.error_message = ai_result or 'Failed to analyze image with AI'

                # Send error message back to WhatsApp
                if self.evolution_api:
                    self.evolution_api.send_text_message(
                        message.chat_session.from_number,
                        f"❌ Erro na Análise da Fatura:\n\n{ai_result or 'Não foi possível analisar a fatura de energia. Verifique se a imagem está clara e legível.'}"
                    )
            
            ai_job.save()
            
            # # Process with n8n
            # n8n_job.status = 'processing'
            # n8n_job.save()
            #
            # message_data = {
            #     'message_id': message.message_id,
            #     'from_number': message.from_number,
            #     'timestamp': message.timestamp.isoformat()
            # }
            #
            # n8n_result = self.n8n_service.send_image_for_processing(image_data, message_data)
            # if n8n_result:
            #     n8n_job.result = n8n_result
            #     n8n_job.status = 'completed'
            #     message.n8n_response = n8n_result
            # else:
            #     n8n_job.status = 'failed'
            #     n8n_job.error_message = 'Failed to send to n8n'
            #
            # n8n_job.save()
            #
            message.processing_status = 'completed'
            message.save()
            #
            return True
            
        except Exception as e:
            print(f"Error processing image: {e}")
            traceback.print_exc()
            message.processing_status = 'failed'
            message.save()
            return False

    def process_image_message_and_return_text(self, message):
        """Process an image message with AI and return the response text instead of sending directly"""
        try:
            # First, download the image if we don't have it locally
            if not message.media_file and message.media_url:
                print(f"Baixando imagem de: {message.media_url}")
                if not self.download_and_save_image(message.media_url, message):
                    print("Falhou ao baixar a imagem")
                    message.processing_status = 'failed'
                    message.save()
                    return "❌ Falha ao baixar a imagem"

            if not message.media_file:
                print("Nenhuma imagem disponível para processar")
                message.processing_status = 'failed'
                message.save()
                return "❌ Nenhuma imagem disponível para processar"

            # Convert image to base64
            print("Convertendo imagem para base64...")
            with message.media_file.open('rb') as image_file:
                image_content = image_file.read()

            # Validar se é uma imagem válida
            try:
                print("Validando imagem salva com PIL...")
                test_image = Image.open(BytesIO(image_content))
                print(f"✓ Imagem válida: {test_image.format} {test_image.mode} {test_image.size}")
                test_image.close()
            except Exception as validation_error:
                print(f"✗ Erro na validação da imagem: {validation_error}")
                message.processing_status = 'failed'
                message.save()
                return "❌ Arquivo de imagem inválido"

            image_data = base64.b64encode(image_content).decode('utf-8')
            print(f"Imagem convertida para base64: {len(image_data)} caracteres")

            # Create processing job for AI
            ai_job = ImageProcessingJob.objects.create(
                message=message,
                processor_type='ai',
                status='processing'
            )

            # Process with AI
            ai_result = self.ai_service.analyze_image(image_data)
            if ai_result and not ai_result.startswith("Erro"):
                ai_job.result = {'analysis': ai_result}
                ai_job.status = 'completed'
                message.ai_response = ai_result
                message.processing_status = 'completed'
                message.save()
                ai_job.save()

                # Return formatted response instead of sending directly
                return f"⚡ Análise da Fatura de Energia:\n\n{ai_result}"
            else:
                ai_job.status = 'failed'
                ai_job.error_message = ai_result or 'Failed to analyze image with AI'
                message.processing_status = 'failed'
                message.save()
                ai_job.save()

                # Return error message instead of sending directly
                return f"❌ Erro na Análise da Fatura:\n\n{ai_result or 'Não foi possível analisar a fatura de energia. Verifique se a imagem está clara e legível.'}"

        except Exception as e:
            print(f"Error processing image: {e}")
            traceback.print_exc()
            message.processing_status = 'failed'
            message.save()
            return f"❌ Erro ao processar imagem: {str(e)}"


