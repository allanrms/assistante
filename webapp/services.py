"""
Serviços para integração com Evolution API
Implementa padrão Service Layer para gerenciamento de instâncias
"""

import requests
import traceback
from typing import Dict, List, Optional, Tuple
from django.utils import timezone
from whatsapp_connector.models import EvolutionInstance


class EvolutionAPIError(Exception):
    """Exceção personalizada para erros da Evolution API"""
    pass


class EvolutionAPIService:
    """
    Serviço para interação com a Evolution API
    Implementa padrão Factory e Service Layer
    """
    
    def __init__(self, instance: EvolutionInstance = None):
        """
        Inicializa o serviço com uma instância específica
        
        Args:
            instance: Instância Evolution específica ou None para operações genéricas
        """
        self.instance = instance
        self.base_url = instance.base_url if instance else None
        self.api_key = instance.api_key if instance else None
        self.instance_name = instance.instance_name if instance else None
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None, 
                     base_url: str = None, api_key: str = None) -> Tuple[bool, Dict]:
        """
        Faz requisição HTTP para a Evolution API
        
        Args:
            method: Método HTTP (GET, POST, DELETE)
            endpoint: Endpoint da API
            data: Dados para envio (POST)
            base_url: URL base (sobrescreve a da instância)
            api_key: Chave da API (sobrescreve a da instância)
            
        Returns:
            Tuple (sucesso: bool, response: dict)
        """
        url_base = base_url or self.base_url
        key = api_key or self.api_key
        
        if not url_base or not key:
            return False, {'error': 'Base URL ou API Key não configurados'}
        
        headers = {
            'apikey': key,
            'Content-Type': 'application/json'
        }
        
        url = f"{url_base.rstrip('/')}{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                return False, {'error': f'Método {method} não suportado'}
            
            response.raise_for_status()
            return True, response.json()
            
        except requests.exceptions.Timeout:
            return False, {'error': 'Timeout na conexão com Evolution API'}
        except requests.exceptions.ConnectionError:
            return False, {'error': 'Erro de conexão com Evolution API'}
        except requests.exceptions.HTTPError as e:
            try:
                error_data = response.json()
                return False, error_data
            except:
                return False, {'error': f'Erro HTTP {response.status_code}: {str(e)}'}
        except Exception as e:
            return False, {'error': f'Erro inesperado: {str(e)}'}
    
    def create_instance(self, instance_name: str, base_url: str, api_key: str, **kwargs) -> Tuple[bool, str]:
        """
        Cria uma nova instância na Evolution API
        
        Args:
            instance_name: Nome da instância
            base_url: URL base da Evolution API
            api_key: Chave da API
            **kwargs: Configurações opcionais da instância
            
        Returns:
            Tuple (sucesso: bool, mensagem: str)
        """
        endpoint = f"/instance/create"
        
        # Configuração completa com valores padrão seguros
        data = {
            "instanceName": instance_name,
            "qrcode": kwargs.get("qrcode", True),
            "number": kwargs.get("number", ""),
            "integration": kwargs.get("integration", "WHATSAPP-BAILEYS"),
            "rejectCall": kwargs.get("rejectCall", False),
            "msgCall": kwargs.get("msgCall", ""),
            "groupsIgnore": kwargs.get("groupsIgnore", False),
            "alwaysOnline": kwargs.get("alwaysOnline", False),
            "readMessages": kwargs.get("readMessages", False),
            "readStatus": kwargs.get("readStatus", False),
            "syncFullHistory": kwargs.get("syncFullHistory", False)
        }
        
        # Configurações de webhook se fornecidas
        webhook_url = kwargs.get("webhook_url")
        if webhook_url:
            data["webhook"] = {
                "url": webhook_url,
                "byEvents": kwargs.get("webhook_byEvents", True),
                "base64": kwargs.get("webhook_base64", False),
                "events": kwargs.get("webhook_events", [
                    "MESSAGES_UPSERT",
                    "MESSAGES_UPDATE", 
                    "CONNECTION_UPDATE"
                ])
            }
        
        success, response = self._make_request('POST', endpoint, data, base_url, api_key)
        
        if success:
            return True, "Instância criada com sucesso na Evolution API"
        else:
            error_msg = response.get('message', response.get('error', 'Erro desconhecido'))
            return False, f"Erro ao criar instância: {error_msg}"
    
    def get_instance_info(self) -> Tuple[bool, Dict]:
        """
        Obtém informações da instância atual
        
        Returns:
            Tuple (sucesso: bool, dados: dict)
        """
        if not self.instance_name:
            return False, {'error': 'Nome da instância não configurado'}
        
        endpoint = f"/instance/fetchInstances"
        success, response = self._make_request('GET', endpoint)
        
        if success:
            # Procura pela instância específica na lista
            instances = response.get('instances', [])
            for inst in instances:
                if inst.get('instance', {}).get('instanceName') == self.instance_name:
                    return True, inst
            
            return False, {'error': 'Instância não encontrada'}
        
        return success, response
    
    def get_connection_state(self) -> Tuple[bool, Dict]:
        """
        Verifica o estado da conexão WhatsApp
        
        Returns:
            Tuple (sucesso: bool, estado: dict)
        """
        if not self.instance_name:
            return False, {'error': 'Nome da instância não configurado'}
        
        endpoint = f"/instance/connectionState/{self.instance_name}"
        return self._make_request('GET', endpoint)
    
    def connect_instance(self) -> Tuple[bool, Dict]:
        """
        Conecta a instância ao WhatsApp
        
        Returns:
            Tuple (sucesso: bool, dados_conexão: dict)
        """
        if not self.instance_name:
            return False, {'error': 'Nome da instância não configurado'}
        
        endpoint = f"/instance/connect/{self.instance_name}"
        return self._make_request('GET', endpoint)
    
    def get_qr_code(self) -> Tuple[bool, Dict]:
        """
        Obtém o código QR para conexão
        
        Returns:
            Tuple (sucesso: bool, qr_data: dict)
        """
        if not self.instance_name:
            return False, {'error': 'Nome da instância não configurado'}
        
        endpoint = f"/instance/qrcode/{self.instance_name}"
        return self._make_request('GET', endpoint)
    
    def delete_instance(self) -> Tuple[bool, str]:
        """
        Deleta a instância da Evolution API
        
        Returns:
            Tuple (sucesso: bool, mensagem: str)
        """
        if not self.instance_name:
            return False, "Nome da instância não configurado"
        
        endpoint = f"/instance/delete/{self.instance_name}"
        success, response = self._make_request('DELETE', endpoint)
        
        if success:
            return True, "Instância deletada com sucesso"
        else:
            error_msg = response.get('message', response.get('error', 'Erro desconhecido'))
            return False, f"Erro ao deletar instância: {error_msg}"
    
    def logout_instance(self) -> Tuple[bool, str]:
        """
        Faz logout da instância WhatsApp
        
        Returns:
            Tuple (sucesso: bool, mensagem: str)
        """
        if not self.instance_name:
            return False, "Nome da instância não configurado"
        
        endpoint = f"/instance/logout/{self.instance_name}"
        success, response = self._make_request('DELETE', endpoint)
        
        if success:
            return True, "Logout realizado com sucesso"
        else:
            error_msg = response.get('message', response.get('error', 'Erro desconhecido'))
            return False, f"Erro ao fazer logout: {error_msg}"


class InstanceManager:
    """
    Gerenciador de instâncias Evolution
    Implementa padrão Manager para operações CRUD
    """
    
    @staticmethod
    def create_instance_record(name: str, instance_name: str, base_url: str, 
                             api_key: str, webhook_url: str = None) -> EvolutionInstance:
        """
        Cria um registro de instância no banco de dados
        
        Args:
            name: Nome amigável da instância
            instance_name: Nome técnico da instância
            base_url: URL base da Evolution API
            api_key: Chave da API
            webhook_url: URL do webhook (opcional)
            
        Returns:
            EvolutionInstance: Instância criada
        """
        return EvolutionInstance.objects.create(
            name=name,
            instance_name=instance_name,
            base_url=base_url,
            api_key=api_key,
            webhook_url=webhook_url,
            status='disconnected'
        )
    
    @staticmethod
    def create_and_sync_instance(name: str, instance_name: str, base_url: str, 
                                api_key: str, webhook_url: str = None, 
                                **evolution_config) -> Tuple[bool, EvolutionInstance, str]:
        """
        Cria instância no banco local E na Evolution API de forma sincronizada
        
        Args:
            name: Nome amigável da instância
            instance_name: Nome técnico da instância  
            base_url: URL base da Evolution API
            api_key: Chave da API
            webhook_url: URL do webhook (opcional)
            **evolution_config: Configurações extras para Evolution API
            
        Returns:
            Tuple (sucesso: bool, instância: EvolutionInstance, mensagem: str)
        """
        try:
            # 1. Primeiro tenta criar na Evolution API
            service = EvolutionAPIService()
            
            # Configurações padrão para Evolution API
            config = {
                'qrcode': True,
                'webhook_url': webhook_url,
                'alwaysOnline': evolution_config.get('alwaysOnline', False),
                'readMessages': evolution_config.get('readMessages', False),
                'readStatus': evolution_config.get('readStatus', False),
                **evolution_config
            }
            
            success, message = service.create_instance(instance_name, base_url, api_key, **config)
            
            if not success:
                return False, None, f"Falha na Evolution API: {message}"
            
            # 2. Se sucesso na Evolution API, cria no banco local
            instance = InstanceManager.create_instance_record(
                name=name,
                instance_name=instance_name,
                base_url=base_url,
                api_key=api_key,
                webhook_url=webhook_url
            )
            
            # 3. Tenta conectar automaticamente
            service_instance = EvolutionAPIService(instance)
            connect_success, connect_data = service_instance.connect_instance()
            
            if connect_success:
                instance.status = 'connecting'
                instance.save()
                return True, instance, "Instância criada e conectando ao WhatsApp"
            else:
                return True, instance, "Instância criada, mas conexão automática falhou. Use o QR Code."
                
        except Exception as e:
            return False, None, f"Erro interno: {str(e)}"
    
    @staticmethod
    def update_instance_status(instance: EvolutionInstance) -> bool:
        """
        Atualiza o status da instância consultando a Evolution API
        
        Args:
            instance: Instância a ser atualizada
            
        Returns:
            bool: True se conseguiu atualizar, False caso contrário
        """
        try:
            service = EvolutionAPIService(instance)
            success, state_data = service.get_connection_state()
            
            if success:
                state = state_data.get('instance', {}).get('state', 'disconnected')
                
                # Mapear estados da API para nossos estados
                status_mapping = {
                    'open': 'connected',
                    'connecting': 'connecting',
                    'close': 'disconnected',
                    'closed': 'disconnected',
                }
                
                new_status = status_mapping.get(state.lower(), 'error')
                
                if new_status != instance.status:
                    instance.status = new_status
                    if new_status == 'connected':
                        instance.last_connection = timezone.now()
                    instance.save()
                
                return True
            
            # Se não conseguir obter o estado, marcar como erro
            instance.status = 'error'
            instance.save()
            return False
            
        except Exception as e:
            print(f"Erro ao atualizar status da instância {instance.name}: {e}")
            instance.status = 'error'
            instance.save()
            return False
    
    @staticmethod
    def sync_all_instances() -> Dict[str, int]:
        """
        Sincroniza o status de todas as instâncias ativas
        
        Returns:
            Dict com contadores de instâncias por status
        """
        instances = EvolutionInstance.objects.filter(is_active=True)
        counters = {'updated': 0, 'errors': 0, 'total': instances.count()}
        
        for instance in instances:
            if InstanceManager.update_instance_status(instance):
                counters['updated'] += 1
            else:
                counters['errors'] += 1
        
        return counters


class WebhookService:
    """
    Serviço para gerenciamento de webhooks
    """
    
    @staticmethod
    def setup_webhook(instance: EvolutionInstance, webhook_url: str) -> Tuple[bool, str]:
        """
        Configura webhook para uma instância
        
        Args:
            instance: Instância Evolution
            webhook_url: URL do webhook
            
        Returns:
            Tuple (sucesso: bool, mensagem: str)
        """
        service = EvolutionAPIService(instance)
        endpoint = f"/webhook/set/{instance.instance_name}"
        
        data = {
            "url": webhook_url,
            "enabled": True,
            "events": [
                "MESSAGES_UPSERT",
                "MESSAGES_UPDATE",
                "CONNECTION_UPDATE"
            ]
        }
        
        success, response = service._make_request('POST', endpoint, data)
        
        if success:
            instance.webhook_url = webhook_url
            instance.save()
            return True, "Webhook configurado com sucesso"
        else:
            error_msg = response.get('message', response.get('error', 'Erro desconhecido'))
            return False, f"Erro ao configurar webhook: {error_msg}"


# Exemplo de uso para criar instância sincronizada
"""
# No seu view ou código Django:

from nodes.services import InstanceManager

def criar_nova_instancia(request):
    try:
        # Criar e sincronizar instância
        success, instance, message = InstanceManager.create_and_sync_instance(
            name="Minha Instância",
            instance_name="instancia_001", 
            base_url="https://seu-evolution-server.com",
            api_key="sua-api-key",
            webhook_url="https://seu-site.com/webhook",
            alwaysOnline=True,
            readMessages=True,
            readStatus=True
        )
        
        if success:
            print(f"✅ {message}")
            print(f"Instância ID: {instance.id}")
            
            # Opcional: obter QR code se necessário
            if instance.status == 'disconnected':
                service = EvolutionAPIService(instance)
                qr_success, qr_data = service.get_qr_code()
                if qr_success:
                    print("QR Code disponível:", qr_data.get('qrcode'))
        else:
            print(f"❌ Erro: {message}")
            
    except Exception as e:
        print(f"❌ Erro interno: {e}")
"""