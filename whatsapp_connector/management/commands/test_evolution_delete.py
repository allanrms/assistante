import requests
from django.core.management.base import BaseCommand
from whatsapp_connector.models import EvolutionInstance


class Command(BaseCommand):
    help = 'Testa a deleção de instâncias na Evolution API'

    def add_arguments(self, parser):
        parser.add_argument('instance_name', type=str, help='Nome técnico da instância para testar deleção')
        parser.add_argument('--dry-run', action='store_true', help='Apenas simula, não executa a deleção')

    def handle(self, *args, **options):
        instance_name = options['instance_name']
        dry_run = options['dry_run']
        
        try:
            # Buscar instância no banco
            instance = EvolutionInstance.objects.get(instance_name=instance_name)
            
            self.stdout.write(f"🔍 Instância encontrada: {instance.name} ({instance.instance_name})")
            self.stdout.write(f"   Base URL: {instance.base_url}")
            self.stdout.write(f"   API Key: {instance.api_key[:10]}...")
            
            if dry_run:
                self.stdout.write(self.style.WARNING("🧪 Modo DRY-RUN ativo - não executando deleção real"))
            
            # Verificar se instância existe na Evolution API
            check_url = f"{instance.base_url}/instance/connectionState/{instance.instance_name}"
            self.stdout.write(f"\n🔍 Verificando existência: {check_url}")
            
            headers = {'apikey': instance.api_key}
            check_response = requests.get(check_url, headers=headers, timeout=10)
            
            self.stdout.write(f"   Status: {check_response.status_code}")
            if check_response.status_code == 200:
                self.stdout.write(self.style.SUCCESS("   ✅ Instância existe na Evolution API"))
            elif check_response.status_code == 404:
                self.stdout.write(self.style.WARNING("   ⚠️ Instância NÃO encontrada na Evolution API"))
                return
            else:
                self.stdout.write(f"   Response: {check_response.text}")
            
            if not dry_run:
                # Tentar deletar usando diferentes endpoints
                delete_urls = [
                    f"{instance.base_url}/instance/delete/{instance.instance_name}",
                    f"{instance.base_url}/instance/{instance.instance_name}/delete",  
                    f"{instance.base_url}/instances/delete/{instance.instance_name}",
                ]
                
                self.stdout.write(f"\n🗑️ Testando deleção...")
                
                for i, url in enumerate(delete_urls, 1):
                    self.stdout.write(f"\n   Tentativa {i}/{len(delete_urls)}: {url}")
                    
                    try:
                        response = requests.delete(url, headers=headers, timeout=30)
                        self.stdout.write(f"   Status: {response.status_code}")
                        
                        if response.status_code == 200:
                            self.stdout.write(self.style.SUCCESS(f"   ✅ SUCESSO! Instância deletada"))
                            self.stdout.write(f"   Response: {response.text}")
                            break
                        elif response.status_code == 404:
                            self.stdout.write(self.style.WARNING(f"   ⚠️ Endpoint não encontrado"))
                            self.stdout.write(f"   Response: {response.text}")
                        else:
                            self.stdout.write(self.style.ERROR(f"   ❌ Falha HTTP {response.status_code}"))
                            self.stdout.write(f"   Response: {response.text}")
                            
                    except requests.RequestException as e:
                        self.stdout.write(self.style.ERROR(f"   ❌ Erro de requisição: {e}"))
            else:
                self.stdout.write(f"\n🧪 Simularia deleção nos endpoints:")
                delete_urls = [
                    f"{instance.base_url}/instance/delete/{instance.instance_name}",
                    f"{instance.base_url}/instance/{instance.instance_name}/delete",  
                    f"{instance.base_url}/instances/delete/{instance.instance_name}",
                ]
                for url in delete_urls:
                    self.stdout.write(f"   - {url}")
                
        except EvolutionInstance.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ Instância '{instance_name}' não encontrada no banco de dados"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erro inesperado: {e}"))