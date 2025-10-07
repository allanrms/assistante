import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.text import slugify
from django.conf import settings

from .models import EvolutionInstance, MessageHistory
from .forms import InstanceForm, WebhookConfigForm, AuthorizedNumbersForm
from core.mixins import ClientRequiredMixin


class MessageHistoryListView(ClientRequiredMixin, LoginRequiredMixin, ListView):
    model = MessageHistory
    template_name = 'whatsapp_connector/message_list.html'
    context_object_name = 'messages'
    paginate_by = 50

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            owner=self.request.user.client
        )
        instance_id = self.request.GET.get('instance')
        if instance_id:
            queryset = queryset.filter(chat_session__evolution_instance_id=instance_id)
        return queryset


# === UTILITY FUNCTIONS ===

def generate_unique_instance_name(name, client=None, exclude_pk=None):
    """
    Gera um nome técnico único para a instância baseado no nome amigável

    Args:
        name: Nome da instância
        client: Client object (não mais User)
        exclude_pk: PK a ser excluída da verificação
    """
    # Gerar slug base
    base_slug = slugify(name).replace('-', '_')
    if not base_slug:
        base_slug = 'instancia'

    # Verificar se já existe
    queryset = EvolutionInstance.objects.all()
    if client:
        queryset = queryset.filter(owner=client)
    if exclude_pk:
        queryset = queryset.exclude(pk=exclude_pk)
    
    # Se não existe, usar o nome base
    if not queryset.filter(instance_name=base_slug).exists():
        return base_slug
    
    # Se existe, adicionar número sequencial
    counter = 1
    while queryset.filter(instance_name=f"{base_slug}_{counter}").exists():
        counter += 1
    
    return f"{base_slug}_{counter}"


# === INSTANCE VIEWS ===

class InstanceListView(ClientRequiredMixin, LoginRequiredMixin, ListView):
    """
    Lista todas as instâncias Evolution
    """
    model = EvolutionInstance
    template_name = 'whatsapp_connector/instances/list.html'
    context_object_name = 'instances'
    paginate_by = 20

    def get_queryset(self):
        queryset = EvolutionInstance.objects.filter(
            owner=self.request.user.client  # Mostrar apenas instâncias do cliente atual
        ).annotate(
            message_count=Count('id')  # Placeholder - precisa implementar contagem correta se necessário
        ).order_by('-created_at')
        
        # Filtro por status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filtro por busca
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(instance_name__icontains=search) |
                Q(profile_name__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = EvolutionInstance.STATUS_CHOICES
        context['current_status'] = self.request.GET.get('status', '')
        context['search_query'] = self.request.GET.get('search', '')
        return context


class InstanceDetailView(ClientRequiredMixin, LoginRequiredMixin, DetailView):
    """
    Detalhes de uma instância específica
    """
    model = EvolutionInstance
    template_name = 'whatsapp_connector/instances/detail.html'
    context_object_name = 'instance'

    def get_queryset(self):
        """Retorna apenas instâncias do cliente atual"""
        return EvolutionInstance.objects.filter(owner=self.request.user.client)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        instance = self.get_object()

        # Estatísticas da instância - buscar mensagens do cliente logado relacionadas a esta instância
        recent_messages = MessageHistory.objects.filter(
            owner=self.request.user.client,
            chat_session__evolution_instance=instance
        ).select_related('chat_session').order_by('-received_at')[:10]

        context['message_count'] = MessageHistory.objects.filter(
            owner=self.request.user.client,
            chat_session__evolution_instance=instance
        ).count()
        context['recent_messages'] = recent_messages
        
        # Status detalhado via API Evolution
        try:
            url = f"{instance.base_url}/instance/connectionState/{instance.instance_name}"
            headers = {'apikey': instance.api_key}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                context['api_info'] = response.json()
        except Exception as e:
            context['api_error'] = str(e)
        
        # Verificar webhook atual na Evolution API
        try:
            webhook_url = f"{instance.base_url}/webhook/find/{instance.instance_name}"
            webhook_response = requests.get(webhook_url, headers={'apikey': instance.api_key}, timeout=10)
            
            if webhook_response.status_code == 200:
                webhook_data = webhook_response.json()
                context['current_webhook'] = webhook_data
                
                # Se o webhook está configurado na API mas não no modelo local, atualizar
                if webhook_data.get('url') and not instance.webhook_url:
                    instance.webhook_url = webhook_data.get('url')
                    instance.save(update_fields=['webhook_url'])
            else:
                context['current_webhook'] = None
        except Exception as e:
            context['webhook_error'] = str(e)
            context['current_webhook'] = None
        
        return context


class InstanceCreateView(ClientRequiredMixin, LoginRequiredMixin, CreateView):
    """
    Class-based view para criar uma nova instância Evolution
    """
    model = EvolutionInstance
    form_class = InstanceForm
    template_name = 'whatsapp_connector/instances/create.html'
    success_url = reverse_lazy('whatsapp_connector:instance_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['client'] = self.request.user.client
        return kwargs

    def form_valid(self, form):
        try:
            # Criar a instância no banco com o cliente atual como owner
            self.object = form.save(commit=False)
            self.object.owner = self.request.user.client  # Define o cliente logado como owner

            # Gerar nome técnico automaticamente
            self.object.instance_name = generate_unique_instance_name(
                self.object.name,
                client=self.request.user.client
            )

            # Preencher valores padrão de base_url e api_key
            if not self.object.base_url:
                self.object.base_url = getattr(settings, 'EVOLUTION_API_BASE_URL', '')
            if not self.object.api_key:
                self.object.api_key = getattr(settings, 'EVOLUTION_API_TOKEN', '')

            # Primeiro criar a instância na Evolution API para obter o instance_evolution_id
            url = f"{self.object.base_url}/instance/create"
            headers = {
                'apikey': self.object.api_key,
                'Content-Type': 'application/json'
            }
            data = {
                'instanceName': self.object.instance_name,
                'webhook': self.object.webhook_url or '',
                'webhookByEvents': False,
                'websocket': False,
                "groupsIgnore": True,
                "alwaysOnline": True,
                "readMessages": True,
                "readStatus": True,
                "integration": "WHATSAPP-BAILEYS"
            }

            response = requests.post(url, json=data, headers=headers, timeout=30)

            if response.status_code in [200, 201]:
                # Extrair instance_evolution_id da resposta da API
                api_response_data = response.json()
                print(f"🔍 Resposta da Evolution API: {api_response_data}")

                # Tentar diferentes caminhos para obter o instanceId
                instance_id = None
                if isinstance(api_response_data, dict):
                    # Tentar vários campos possíveis
                    instance_id = (
                        api_response_data.get('instance', {}).get('instanceId') or
                        api_response_data.get('hash') or
                        api_response_data.get('instanceId') or
                        api_response_data.get('id')
                    )

                # Se encontrou um ID válido (não vazio), usar ele
                # Caso contrário, deixar como None para ser preenchido depois via fetch_and_update_connection_info
                if instance_id and instance_id != '':
                    self.object.instance_evolution_id = instance_id
                    print(f"✅ instance_evolution_id definido como: {instance_id}")
                else:
                    self.object.instance_evolution_id = None
                    print(f"⚠️ API não retornou instanceId, será preenchido posteriormente via sincronização")

                # Agora salvar no banco com o instance_evolution_id preenchido
                self.object.save()

                messages.success(self.request, f'Instância "{self.object.name}" criada com sucesso!')
            else:
                error_message = f'Falha ao criar instância na Evolution API: {response.text}'
                messages.error(self.request, error_message)

                # Se for requisição AJAX, retornar JSON com o erro
                if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    from django.http import JsonResponse
                    return JsonResponse({
                        'success': False,
                        'error': error_message,
                        'message': error_message
                    }, status=400)

                return self.form_invalid(form)

            # Se for requisição AJAX, retornar JSON com o ID da instância
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                from django.http import JsonResponse
                return JsonResponse({
                    'success': True,
                    'instance_id': str(self.object.pk),
                    'message': f'Instância "{self.object.name}" criada com sucesso!'
                })

            return redirect('whatsapp_connector:instance_detail', pk=self.object.pk)

        except Exception as e:
            messages.error(self.request, f'Erro ao criar instância: {str(e)}')

            # Se for requisição AJAX, retornar JSON com o erro
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                from django.http import JsonResponse
                return JsonResponse({
                    'success': False,
                    'error': str(e),
                    'message': f'Erro ao criar instância: {str(e)}'
                }, status=400)

            return self.form_invalid(form)


class InstanceUpdateView(ClientRequiredMixin, LoginRequiredMixin, UpdateView):
    """
    Class-based view para editar uma instância Evolution
    """
    model = EvolutionInstance
    form_class = InstanceForm
    template_name = 'whatsapp_connector/instances/edit.html'
    context_object_name = 'instance'

    def get_queryset(self):
        """Retorna apenas instâncias do cliente atual"""
        return EvolutionInstance.objects.filter(owner=self.request.user.client)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['client'] = self.request.user.client
        return kwargs

    def get_success_url(self):
        return reverse_lazy('whatsapp_connector:instance_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        # Se o nome foi alterado, regenerar o instance_name
        if form.has_changed() and 'name' in form.changed_data:
            form.instance.instance_name = generate_unique_instance_name(
                form.instance.name,
                client=self.request.user.client,
                exclude_pk=form.instance.pk
            )

        messages.success(self.request, f'Instância "{form.instance.name}" atualizada com sucesso!')
        return super().form_valid(form)


class InstanceDeleteView(ClientRequiredMixin, LoginRequiredMixin, DeleteView):
    """
    Class-based view para deletar uma instância Evolution
    """
    model = EvolutionInstance
    template_name = 'whatsapp_connector/instances/confirm_delete.html'
    success_url = reverse_lazy('whatsapp_connector:instance_list')
    context_object_name = 'instance'

    def get_queryset(self):
        """Retorna apenas instâncias do cliente atual"""
        return EvolutionInstance.objects.filter(owner=self.request.user.client)
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        instance_name = self.object.name
        
        try:
            # Tentar deletar da Evolution API primeiro
            api_deleted = False
            
            try:
                print(f"🗑️ Tentando deletar instância '{self.object.name}' ({self.object.instance_name})")
                
                # Primeiro verificar se a instância existe na Evolution API
                check_url = f"{self.object.base_url}/instance/connectionState/{self.object.instance_name}"
                print(f"   Verificando se instância existe: {check_url}")
                
                check_response = requests.get(check_url, headers={'apikey': self.object.api_key}, timeout=10)
                print(f"   Status da verificação: {check_response.status_code}")
                
                if check_response.status_code == 404:
                    print(f"   Instância não existe na Evolution API, pulando deleção")
                    messages.info(request, f'Instância não encontrada na Evolution API (já foi removida)')
                    api_deleted = True
                elif check_response.status_code != 200:
                    print(f"   Erro ao verificar instância: {check_response.text}")
                
                if not api_deleted:
                    # Tentar diferentes formatos de URL da Evolution API para deleção
                    urls_to_try = [
                        f"{self.object.base_url}/instance/delete/{self.object.instance_name}",
                        f"{self.object.base_url}/instance/{self.object.instance_name}/delete",
                        f"{self.object.base_url}/instances/delete/{self.object.instance_name}",
                    ]
                
                headers = {'apikey': self.object.api_key}
                
                for i, url in enumerate(urls_to_try, 1):
                    try:
                        print(f"   Tentativa {i}/3 - URL: {url}")
                        
                        response = requests.delete(url, headers=headers, timeout=30)
                        
                        print(f"   Status Code: {response.status_code}")
                        
                        if response.status_code == 200:
                            try:
                                response_data = response.json()
                                messages.info(request, f'Instância removida da Evolution API: {response_data.get("message", "Deletada com sucesso")}')
                                print(f"✅ Instância '{self.object.name}' deletada com sucesso da Evolution API")
                                print(f"   Response JSON: {response_data}")
                            except:
                                messages.info(request, f'Instância removida da Evolution API')
                                print(f"✅ Instância '{self.object.name}' deletada com sucesso da Evolution API")
                            api_deleted = True
                            break
                        elif response.status_code == 404:
                            print(f"   Endpoint não encontrado (404), tentando próxima URL...")
                            continue
                        else:
                            print(f"   Response: {response.text}")
                            # Se é a última tentativa, mostrar o erro
                            if i == len(urls_to_try):
                                messages.warning(request, f'Evolution API retornou HTTP {response.status_code}: {response.text}')
                            
                    except requests.RequestException as req_error:
                        print(f"   Erro na tentativa {i}: {str(req_error)}")
                        if i == len(urls_to_try):  # Última tentativa
                            raise req_error
                        continue
                
                if not api_deleted:
                    error_message = f'Falha ao remover da Evolution API - Todos os endpoints testados falharam'
                    messages.warning(request, error_message)
                    print(f"❌ {error_message}")
                    
            except requests.RequestException as e:
                error_message = f'Erro ao conectar com Evolution API: {str(e)}'
                messages.warning(request, error_message)
                print(f"❌ {error_message}")
            
            # Deletar do banco de dados
            response = super().delete(request, *args, **kwargs)
            messages.success(request, f'Instância "{instance_name}" removida com sucesso!')
            
            return response
            
        except Exception as e:
            messages.error(request, f'Erro ao deletar instância: {str(e)}')
            return redirect('whatsapp_connector:instance_list')


# === INSTANCE FUNCTIONS ===

@login_required
@require_http_methods(["POST"])
def connect_instance(request, pk):
    """
    Conecta uma instância ao WhatsApp
    """
    try:
        instance = get_object_or_404(EvolutionInstance, pk=pk, owner=request.user)
        
        # Conectar via Evolution API
        url = f"{instance.base_url}/instance/connect/{instance.instance_name}"
        headers = {
            'apikey': instance.api_key,
            'Content-Type': 'application/json'
        }
        
        response = requests.post(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            instance.status = 'connecting'
            instance.save()
            messages.success(request, 'Processo de conexão iniciado com sucesso!')
        else:
            messages.error(request, f'Erro ao conectar: {response.text}')
            
    except Exception as e:
        messages.error(request, f'Erro inesperado: {str(e)}')
    
    return redirect('whatsapp_connector:instance_detail', pk=pk)


@login_required
@require_http_methods(["POST"]) 
def logout_instance(request, pk):
    """
    Faz logout de uma instância WhatsApp
    """
    try:
        instance = get_object_or_404(EvolutionInstance, pk=pk, owner=request.user)
        
        # Logout via Evolution API
        url = f"{instance.base_url}/instance/logout/{instance.instance_name}"
        headers = {
            'apikey': instance.api_key
        }
        
        response = requests.delete(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            instance.status = 'disconnected'
            instance.phone_number = None
            instance.profile_name = None
            instance.profile_pic_url = None
            instance.save()
            messages.success(request, 'Instância desconectada com sucesso!')
        else:
            messages.error(request, f'Erro ao desconectar: {response.text}')
            
    except Exception as e:
        messages.error(request, f'Erro inesperado: {str(e)}')
    
    return redirect('whatsapp_connector:instance_detail', pk=pk)


@login_required
def get_qr_code(request, pk):
    """
    API endpoint para obter QR Code de uma instância
    """
    instance = get_object_or_404(EvolutionInstance, pk=pk)
    
    try:
        # Obter QR Code via Evolution API
        url = f"{instance.base_url}/instance/connect/{instance.instance_name}"
        headers = {'apikey': instance.api_key}
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            qr_code = data.get('base64')
            
            if qr_code:
                return JsonResponse({
                    'success': True,
                    'qr_code': qr_code,
                    'message': 'QR Code obtido com sucesso'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'QR Code não disponível. A instância pode já estar conectada.'
                })
        else:
            return JsonResponse({
                'success': False,
                'message': f'Erro ao obter QR Code: {response.text}'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Erro ao obter QR Code: {str(e)}'
        })


@login_required
def sync_instances(request):
    """
    Sincroniza status de todas as instâncias
    """
    try:
        instances = EvolutionInstance.objects.filter(is_active=True)
        updated = 0
        errors = 0
        
        for instance in instances:
            try:
                # Verificar status via API
                url = f"{instance.base_url}/instance/connectionState/{instance.instance_name}"
                headers = {'apikey': instance.api_key}
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    state = data.get('instance', {}).get('state', 'unknown')
                    
                    # Mapear estado da API para status do modelo
                    status_mapping = {
                        'open': 'connected',
                        'connecting': 'connecting', 
                        'close': 'disconnected'
                    }
                    
                    new_status = status_mapping.get(state, 'error')
                    
                    if instance.status != new_status:
                        instance.status = new_status
                        instance.save()
                        updated += 1

                    if instance.status == 'connected':
                        instance.fetch_and_update_connection_info()
                        instance.save()
                        
                else:
                    errors += 1
                    
            except Exception:
                errors += 1
        
        messages.success(
            request,
            f'Sincronização concluída: {updated} atualizadas, '
            f'{errors} com erro, {instances.count()} total'
        )
        
    except Exception as e:
        messages.error(request, f'Erro na sincronização: {str(e)}')
    
    return redirect('whatsapp_connector:instance_list')


@login_required
def sync_phone_numbers(request):
    """
    Sincroniza números de telefone de todas as instâncias conectadas
    """
    try:
        connected_instances = EvolutionInstance.objects.filter(
            status='connected', 
            is_active=True
        )
        
        updated = 0
        errors = 0
        
        for instance in connected_instances:
            try:
                if instance.fetch_and_update_connection_info():
                    updated += 1
            except Exception as e:
                print(f"Error syncing connection info for {instance.name}: {e}")
                errors += 1
        
        if updated > 0:
            messages.success(
                request,
                f'Sincronização de números concluída: {updated} número(s) capturado(s), '
                f'{errors} erro(s), {connected_instances.count()} instância(s) verificada(s)'
            )
        else:
            messages.info(
                request,
                f'Nenhum número novo encontrado. {connected_instances.count()} instância(s) verificada(s)'
            )
        
    except Exception as e:
        messages.error(request, f'Erro na sincronização de números: {str(e)}')
    
    return redirect('whatsapp_connector:instance_list')


@login_required
def instance_status(request, pk):
    """
    API endpoint para obter status atualizado de uma instância
    """
    instance = get_object_or_404(EvolutionInstance, pk=pk)
    
    try:
        # Verificar status via Evolution API
        url = f"{instance.base_url}/instance/connectionState/{instance.instance_name}"
        headers = {'apikey': instance.api_key}
        response = requests.get(url, headers=headers, timeout=10)
        
        updated = False
        if response.status_code == 200:
            data = response.json()
            state = data.get('instance', {}).get('state', 'unknown')
            
            # Mapear estado da API para status do modelo
            status_mapping = {
                'open': 'connected',
                'connecting': 'connecting', 
                'close': 'disconnected'
            }
            
            new_status = status_mapping.get(state, 'error')
            
            if instance.status != new_status:
                instance.status = new_status
                if new_status == 'connected':
                    instance.last_connection = timezone.now()
                instance.save()
                updated = True


            if instance.status == 'connected':
                instance.fetch_and_update_connection_info()
                instance.save()

        
        return JsonResponse({
            'success': True,
            'updated': updated,
            'status': instance.status,
            'status_display': instance.get_status_display(),
            'last_connection': instance.last_connection.isoformat() if instance.last_connection else None,
            'connection_info': instance.connection_info
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def configure_webhook(request, pk):
    """
    Página para configurar webhook da instância
    """
    instance = get_object_or_404(EvolutionInstance, pk=pk, owner=request.user)
    
    if request.method == 'POST':
        # Se é uma requisição JSON (via AJAX)
        if request.content_type == 'application/json':
            import json
            data = json.loads(request.body)
            webhook_url = data.get('webhook_url')
            enabled = data.get('enabled', True)
            events = data.get('events', [])
        else:
            # Formulário HTML padrão
            form = WebhookConfigForm(request.POST)
            if not form.is_valid():
                # Se o formulário não é válido, renderizar com erros
                context = {
                    'instance': instance,
                    'form': form,
                    'current_config': {},
                    'EVOLUTION_API_BASE_URL': getattr(settings, 'EVOLUTION_API_BASE_URL', ''),
                    'all_events': [
                        ('APPLICATION_STARTUP', 'Inicialização da Aplicação'),
                        ('QRCODE_UPDATED', 'QR Code Atualizado'),
                        ('MESSAGES_SET', 'Mensagens Definidas'),
                        ('MESSAGES_UPSERT', 'Mensagens Recebidas/Enviadas'),
                        ('MESSAGES_UPDATE', 'Mensagens Atualizadas'),
                        ('MESSAGES_DELETE', 'Mensagens Deletadas'),
                        ('SEND_MESSAGE', 'Envio de Mensagem'),
                        ('CONTACTS_SET', 'Contatos Definidos'),
                        ('CONTACTS_UPSERT', 'Contatos Atualizados'),
                        ('CONTACTS_UPDATE', 'Atualização de Contatos'),
                        ('PRESENCE_UPDATE', 'Status de Presença'),
                        ('CHATS_SET', 'Conversas Definidas'),
                        ('CHATS_UPSERT', 'Conversas Criadas'),
                        ('CHATS_UPDATE', 'Conversas Atualizadas'),
                        ('CHATS_DELETE', 'Conversas Deletadas'),
                        ('GROUPS_UPSERT', 'Grupos Criados'),
                        ('GROUP_UPDATE', 'Grupos Atualizados'),
                        ('GROUP_PARTICIPANTS_UPDATE', 'Participantes de Grupo'),
                        ('CONNECTION_UPDATE', 'Status de Conexão'),
                        ('CALL', 'Chamadas'),
                        ('NEW_JWT_TOKEN', 'Novo Token JWT'),
                        ('TYPEBOT_START', 'Typebot Iniciado'),
                        ('TYPEBOT_CHANGE_STATUS', 'Status Typebot Alterado'),
                    ]
                }
                return render(request, 'whatsapp_connector/instances/webhook_config.html', context)
            
            webhook_url = form.cleaned_data['webhook_url']
            enabled = form.cleaned_data['enabled']
            events = form.cleaned_data['events']
        
        try:
            # Configurar webhook na Evolution API
            url = f"{instance.base_url}/webhook/set/{instance.instance_name}"
            headers = {
                'apikey': instance.api_key,
                'Content-Type': 'application/json'
            }
            data = {
                'url': webhook_url,
                'enabled': enabled,
                'events': events
            }
            
            response = requests.post(url, json=data, headers=headers, timeout=30)
            
            if response.status_code in [200, 201]:
                # Salvar URL do webhook na instância
                instance.webhook_url = webhook_url
                instance.save(update_fields=['webhook_url'])
                
                if request.content_type == 'application/json':
                    return JsonResponse({'success': True, 'message': 'Webhook configurado com sucesso!'})
                # Removido messages.success para evitar mensagem duplicada no navegador
            else:
                error_msg = f'Erro ao configurar webhook na Evolution API: {response.text}'
                if request.content_type == 'application/json':
                    return JsonResponse({'success': False, 'message': error_msg})
                # Removido messages.error para evitar mensagem duplicada no navegador
                    
        except Exception as e:
            error_msg = f'Erro ao configurar webhook: {str(e)}'
            if request.content_type == 'application/json':
                return JsonResponse({'success': False, 'message': error_msg})
            # Removido messages.error para evitar mensagem duplicada no navegador
        
        if request.content_type != 'application/json':
            return redirect('whatsapp_connector:instance_detail', pk=instance.pk)
        
    elif request.method == 'GET':
        # Buscar configurações atuais do webhook
        try:
            url = f"{instance.base_url}/webhook/find/{instance.instance_name}"
            headers = {'apikey': instance.api_key}
            response = requests.get(url, headers=headers, timeout=10)
            
            current_config = {}
            if response.status_code == 200:
                current_config = response.json()
        except:
            current_config = {}
        
        # Preencher formulário com valores atuais
        webhook_url = current_config.get('url') or instance.webhook_url
        
        # Preparar dados iniciais
        current_events = current_config.get('events', [])
        if not current_events:
            # Se não há eventos configurados, usar MESSAGES_UPSERT por padrão
            current_events = ['MESSAGES_UPSERT']
        
        initial_data = {
            'enabled': current_config.get('enabled', True),
            'events': current_events
        }
        
        # Se há URL configurada, usar ela. Caso contrário, deixar que o formulário defina o padrão
        if webhook_url:
            initial_data['webhook_url'] = webhook_url
        
        form = WebhookConfigForm(initial=initial_data)
        
        context = {
            'instance': instance,
            'form': form,
            'current_config': current_config,
            'EVOLUTION_API_BASE_URL': getattr(settings, 'EVOLUTION_API_BASE_URL', ''),
            'all_events': [
                ('APPLICATION_STARTUP', 'Inicialização da Aplicação'),
                ('QRCODE_UPDATED', 'QR Code Atualizado'),
                ('MESSAGES_SET', 'Mensagens Definidas'),
                ('MESSAGES_UPSERT', 'Mensagens Recebidas/Enviadas'),
                ('MESSAGES_UPDATE', 'Mensagens Atualizadas'),
                ('MESSAGES_DELETE', 'Mensagens Deletadas'),
                ('SEND_MESSAGE', 'Envio de Mensagem'),
                ('CONTACTS_SET', 'Contatos Definidos'),
                ('CONTACTS_UPSERT', 'Contatos Atualizados'),
                ('CONTACTS_UPDATE', 'Atualização de Contatos'),
                ('PRESENCE_UPDATE', 'Status de Presença'),
                ('CHATS_SET', 'Conversas Definidas'),
                ('CHATS_UPSERT', 'Conversas Criadas'),
                ('CHATS_UPDATE', 'Conversas Atualizadas'),
                ('CHATS_DELETE', 'Conversas Deletadas'),
                ('GROUPS_UPSERT', 'Grupos Criados'),
                ('GROUP_UPDATE', 'Grupos Atualizados'),
                ('GROUP_PARTICIPANTS_UPDATE', 'Participantes de Grupo'),
                ('CONNECTION_UPDATE', 'Status de Conexão'),
                ('CALL', 'Chamadas'),
                ('NEW_JWT_TOKEN', 'Novo Token JWT'),
                ('TYPEBOT_START', 'Typebot Iniciado'),
                ('TYPEBOT_CHANGE_STATUS', 'Status Typebot Alterado'),
            ]
        }
        
        return render(request, 'whatsapp_connector/instances/webhook_config.html', context)


@login_required
def configure_contacts(request, pk):
    """
    Página para configurar contatos autorizados da instância
    """
    instance = get_object_or_404(EvolutionInstance, pk=pk, owner=request.user)
    
    if request.method == 'POST':
        form = AuthorizedNumbersForm(request.POST)
        if form.is_valid():
            # Salva os números autorizados na instância
            instance.authorized_numbers = form.cleaned_data['authorized_numbers']
            instance.save()
            
            # Mensagem de sucesso
            if form.cleaned_data['authorized_numbers']:
                numbers_count = len(instance.get_authorized_numbers_list())
                messages.success(
                    request,
                    f'Configuração salva! {numbers_count} número(s) autorizado(s) para a instância "{instance.name}".'
                )
            else:
                messages.success(
                    request,
                    f'Configuração salva! Todos os números podem interagir com a instância "{instance.name}".'
                )
            
            return redirect('whatsapp_connector:instance_detail', pk=instance.pk)
    else:
        # Preencher formulário com valores atuais
        # Converter formato de vírgula para quebras de linha para melhor UX
        current_numbers_text = ''
        if instance.authorized_numbers:
            numbers_list = instance.get_authorized_numbers_list()
            current_numbers_text = '\n'.join(numbers_list)
        
        form = AuthorizedNumbersForm(initial={
            'authorized_numbers': current_numbers_text
        })
    
    context = {
        'instance': instance,
        'form': form,
        'current_numbers': instance.get_authorized_numbers_list(),
    }
    
    return render(request, 'whatsapp_connector/instances/contacts_config.html', context)


@login_required
def update_connection_info(request, pk):
    """
    API endpoint para forçar atualização das informações de conexão
    """
    instance = get_object_or_404(EvolutionInstance, pk=pk, owner=request.user)
    
    try:
        success = instance.fetch_and_update_connection_info()
        
        if success:
            return JsonResponse({
                'success': True,
                'message': 'Informações atualizadas com sucesso',
                'phone_number': instance.phone_number,
                'profile_name': instance.profile_name,
                'connection_info': instance.connection_info
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Nenhuma informação nova encontrada ou instância não conectada'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_http_methods(["POST"])
def toggle_ignore_own_messages(request, pk):
    """
    API endpoint para alternar o campo ignore_own_messages
    """
    try:
        instance = get_object_or_404(EvolutionInstance, pk=pk, owner=request.user)
        
        # Alternar o valor
        instance.ignore_own_messages = not instance.ignore_own_messages
        instance.save(update_fields=['ignore_own_messages'])
        
        return JsonResponse({
            'success': True,
            'ignore_own_messages': instance.ignore_own_messages,
            'message': f'Filtro de mensagens próprias {"ativado" if instance.ignore_own_messages else "desativado"}'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@require_http_methods(["POST"])
def toggle_instance_active(request, pk):
    """
    API endpoint para alternar o campo is_active
    """
    try:
        instance = get_object_or_404(EvolutionInstance, pk=pk, owner=request.user)
        
        # Alternar o valor
        instance.is_active = not instance.is_active
        instance.save(update_fields=['is_active'])
        
        return JsonResponse({
            'success': True,
            'is_active': instance.is_active,
            'message': f'Instância {"ativada" if instance.is_active else "desativada"} com sucesso'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })