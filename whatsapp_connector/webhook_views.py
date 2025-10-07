from django.http import JsonResponse
from django.views import View
from .models import EvolutionInstance
import requests
import json


class ConfigureWebhookView(View):
    def post(self, request, pk):
        try:
            instance = EvolutionInstance.objects.get(pk=pk)
            
            # Extrair dados do request
            data = json.loads(request.body) if request.body else {}
            
            # Configurações do webhook
            webhook_config = {
                "enabled": data.get('enabled', True),
                "url": data.get('webhook_url', ''),
                "webhookByEvents": data.get('webhook_by_events', True),
                "webhookBase64": data.get('webhook_base64', True),
                "events": data.get('events', ['MESSAGES_UPSERT', 'CONNECTION_UPDATE'])
            }
            
            # Fazer requisição para configurar webhook
            url = f"{instance.base_url}/webhook/set/{instance.instance_name}"
            headers = {
                'apikey': instance.api_key,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, json=webhook_config, headers=headers, timeout=30)
            
            # Tratar diferentes códigos de resposta da Evolution API
            if response.status_code in [200, 201]:
                # Atualizar URL do webhook na instância se fornecida
                if webhook_config['url']:
                    instance.webhook_url = webhook_config['url']
                    instance.save()
                
                # Tentar parsear resposta da API
                try:
                    api_response = response.json()
                    return JsonResponse({
                        'success': True,
                        'message': 'Webhook configurado com sucesso',
                        'webhook_config': webhook_config,
                        'api_response': api_response
                    })
                except json.JSONDecodeError:
                    return JsonResponse({
                        'success': True,
                        'message': 'Webhook configurado com sucesso',
                        'webhook_config': webhook_config
                    })
            else:
                # Tentar parsear erro da API
                try:
                    error_data = response.json()
                    error_message = error_data.get('message', response.text)
                except:
                    error_message = response.text
                
                return JsonResponse({
                    'success': False,
                    'message': f'Erro ao configurar webhook: {error_message}'
                }, status=400)
                
        except EvolutionInstance.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Instância não encontrada'
            }, status=404)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Dados JSON inválidos'
            }, status=400)
        except requests.RequestException as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro de conexão: {str(e)}'
            }, status=500)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro inesperado: {str(e)}'
            }, status=500)
    
    def get(self, request, pk):
        """Retorna configurações atuais do webhook"""
        try:
            instance = EvolutionInstance.objects.get(pk=pk)
            
            # Obter configurações atuais do webhook via API
            url = f"{instance.base_url}/webhook/find/{instance.instance_name}"
            headers = {'apikey': instance.api_key}
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                webhook_data = response.json()
                return JsonResponse({
                    'success': True,
                    'webhook_config': webhook_data,
                    'available_events': self.get_available_events()
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': f'Erro ao obter configurações: {response.text}',
                    'available_events': self.get_available_events()
                })
                
        except EvolutionInstance.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Instância não encontrada'
            }, status=404)
        except requests.RequestException as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro de conexão: {str(e)}'
            }, status=500)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro inesperado: {str(e)}'
            }, status=500)
    
    def get_available_events(self):
        """Retorna lista de eventos disponíveis para webhook"""
        return [
            'APPLICATION_STARTUP',
            'QRCODE_UPDATED', 
            'MESSAGES_SET',
            'MESSAGES_UPSERT',
            'MESSAGES_UPDATE',
            'MESSAGES_DELETE',
            'SEND_MESSAGE',
            'CONTACTS_SET',
            'CONTACTS_UPSERT',
            'CONTACTS_UPDATE',
            'PRESENCE_UPDATE',
            'CHATS_SET',
            'CHATS_UPSERT',
            'CHATS_UPDATE',
            'CHATS_DELETE',
            'GROUPS_UPSERT',
            'GROUP_UPDATE',
            'GROUP_PARTICIPANTS_UPDATE',
            'CONNECTION_UPDATE',
            'CALL',
            'NEW_JWT_TOKEN',
            'TYPEBOT_START',
            'TYPEBOT_CHANGE_STATUS'
        ]


    # https://f77d25c53a10.ngrok-free.app/whatsapp_connector/v1/send/message