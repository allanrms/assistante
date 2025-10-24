import traceback

import requests
import threading
from django.conf import settings
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from whatsapp_connector.models import ChatSession, EvolutionInstance


@receiver(post_save, sender=ChatSession, weak=False)
def post_save_chat_session(sender, instance: ChatSession, *args, **kwargs):
    if instance.status == 'closed':
        # TODO: Implementar lógica de fechamento de conversação se necessário
        # O modelo ChatHistory foi removido - verificar se precisa de nova implementação
        pass


def _configure_webhook_async(instance_pk, instance_name_for_log):
    """
    Função auxiliar para configurar webhook em thread separada
    """
    import time

    try:
        # Aguardar um pouco para dar tempo da instância ser criada na Evolution API
        print(f"⏰ Aguardando 5 segundos antes de configurar webhook para '{instance_name_for_log}'...")
        time.sleep(5)

        # Recarregar instância do banco para ter os dados mais recentes
        instance = EvolutionInstance.objects.get(pk=instance_pk)

        # Gerar URL padrão do webhook
        base_url = getattr(settings, 'BACKEND_BASE_URL', '').rstrip('/')
        if not base_url:
            print(
                f"❌ BACKEND_BASE_URL não configurado, abortando configuração de webhook para '{instance_name_for_log}'")
            return

        print(f"📍 BACKEND_BASE_URL: {base_url}")
        print(f"📍 Evolution API URL: {instance.base_url}")
        print(f"📍 Instance name: {instance.instance_name}")

        webhook_url = f"{base_url}/whatsapp_connector/v1/evolution/webhook/receiver"

        # Configurar webhook na Evolution API
        webhook_config_url = f"{instance.base_url}/webhook/set/{instance.instance_name}"
        headers = {
            'apikey': instance.api_key,
            'Content-Type': 'application/json'
        }
        data = {
            "webhook": {
                'url': webhook_url,
                'enabled': True,
                'events': ["MESSAGES_UPSERT"]
            }
        }

        # Primeiro verificar se a instância existe na Evolution API usando endpoint mais específico
        check_url = f"{instance.base_url}/instance/connectionState/{instance.instance_name}"
        print(f"🔍 Verificando se instância '{check_url}' existe na Evolution API...")

        check_response = requests.get(check_url, headers={'apikey': instance.api_key}, timeout=30)

        if check_response.status_code == 404:
            print(
                f"❌ Instância '{instance.instance_name}' não existe na Evolution API. Abortando configuração de webhook.")
            print(f"   Response: {check_response.text}")
            return
        elif check_response.status_code != 200:
            print(f"⚠️ Erro ao verificar instância na Evolution API (continuando mesmo assim): {check_response.text}")
            # Continua mesmo com erro pois pode ser um problema temporário
        else:
            print(f"✅ Instância '{instance.instance_name}' encontrada na Evolution API.")
        print(
            f"🔄 Configurando webhook automaticamente para instância '{instance_name_for_log}' ({instance.instance_name})...")

        response = requests.post(webhook_config_url, json=data, headers=headers, timeout=30)

        if response.status_code in [200, 201]:
            # Salvar URL do webhook na instância
            EvolutionInstance.objects.filter(pk=instance_pk).update(webhook_url=webhook_url)

            print(f"✅ Webhook configurado automaticamente para instância '{instance_name_for_log}': {webhook_url}")
            print(f"   Evento configurado: MESSAGES_UPSERT")
        else:
            print(f"❌ Falha ao configurar webhook para instância '{instance_name_for_log}': {response.text}")

    except requests.RequestException as e:
        print(f"❌ Erro de conexão ao configurar webhook para instância '{instance_name_for_log}': {str(e)}")
    except Exception as e:
        print(f"❌ Erro inesperado ao configurar webhook para instância '{instance_name_for_log}': {str(e)}")


@receiver(post_save, sender=EvolutionInstance)
def auto_configure_webhook(sender, instance, created, **kwargs):
    """
    Signal para configurar webhook automaticamente quando uma instância é criada
    """
    print(f"🔄 Signal post_save executado para instância '{instance.name}' (ID: {instance.pk})")
    print(f"   created={created}, base_url='{instance.base_url}', api_key={'***' if instance.api_key else 'None'}, instance_name='{instance.instance_name}'")

    if created and instance.base_url and instance.api_key and instance.instance_name:
        # Executar configuração em thread separada para não bloquear
        thread = threading.Thread(
            target=_configure_webhook_async,
            args=(instance.pk, instance.name),
            daemon=True
        )
        thread.start()
        print(f"🚀 Iniciando configuração automática de webhook para '{instance.name}' em background...")
    else:
        traceback.print_exc()
        print(f"⚠️ Signal executado para '{instance.name}' mas condições não atendidas:")
        print(f"   created={created}, base_url={bool(instance.base_url)}, api_key={bool(instance.api_key)}, instance_name={bool(instance.instance_name)}")

@receiver(pre_delete, sender=EvolutionInstance)
def delete_evolution_instance(sender, instance, **kwargs):
    """
    Signal para deletar instância da Evolution API quando removida localmente
    """
    try:
        print(f"🗑️ Deletando instância '{instance.name}' ({instance.instance_name}) da Evolution API...")
        
        # URL para deletar instância conforme documentação
        delete_url = f"{instance.base_url}/instance/delete/{instance.instance_name}"
        headers = {'apikey': instance.api_key}
        
        response = requests.delete(delete_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            print(f"✅ Instância '{instance.name}' deletada com sucesso da Evolution API")
        elif response.status_code == 404:
            print(f"ℹ️ Instância '{instance.name}' não encontrada na Evolution API (já foi removida)")
        else:
            print(f"❌ Erro ao deletar instância '{instance.name}' da Evolution API: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.RequestException as e:
        print(f"❌ Erro de conexão ao deletar instância '{instance.name}' da Evolution API: {str(e)}")
    except Exception as e:
        print(f"❌ Erro inesperado ao deletar instância '{instance.name}' da Evolution API: {str(e)}")
