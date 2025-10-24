"""
Formulários do Dashboard
Implementa validações e interface de usuário para gerenciamento de instâncias
"""

from django import forms
from django.core.validators import URLValidator
from django.conf import settings
from django.utils.text import slugify
from whatsapp_connector.models import EvolutionInstance
from agents.models import Agent
import re


class InstanceForm(forms.ModelForm):
    """
    Formulário para criação e edição de instâncias Evolution
    """
    
    class Meta:
        model = EvolutionInstance
        fields = ['name', 'agent', 'ignore_own_messages']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome amigável da instância (ex: WhatsApp Empresa)'
            }),
            'agent': forms.Select(attrs={
                'class': 'form-select',
                'placeholder': 'Selecione um agent'
            }),
            'ignore_own_messages': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        labels = {
            'name': 'Nome da Instância',
            'agent': 'Agent/IA',
            'ignore_own_messages': 'Ignorar Mensagens Próprias'
        }
        help_texts = {
            'name': 'Nome descritivo para identificar a instância',
            'agent': 'Selecione qual agent/IA será usado para responder mensagens (opcional)',
            'ignore_own_messages': 'Quando ativo, ignora mensagens enviadas pelo próprio número da instância'
        }
    
    def __init__(self, *args, **kwargs):
        # Aceita tanto 'user' (deprecated) quanto 'client' (novo)
        user = kwargs.pop('user', None)
        client = kwargs.pop('client', None)

        super().__init__(*args, **kwargs)

        # Marca campos obrigatórios
        self.fields['name'].required = True
        self.fields['agent'].required = False

        # Filtrar agents apenas do cliente logado
        # Se recebeu 'client', usar ele. Caso contrário, tentar 'user.client' (compatibilidade)
        filter_owner = client
        if not filter_owner and user and user.client:
            filter_owner = user.client

        if filter_owner:
            self.fields['agent'].queryset = Agent.objects.filter(owner=filter_owner)
        else:
            self.fields['agent'].queryset = Agent.objects.none()


class InstanceSearchForm(forms.Form):
    """
    Formulário de busca e filtros para instâncias
    """
    search = forms.CharField(
        label='Buscar',
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por nome, instância ou perfil...',
            'autocomplete': 'off'
        })
    )
    
    status = forms.ChoiceField(
        label='Status',
        choices=[('', 'Todos os status')] + list(EvolutionInstance.STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    active_only = forms.BooleanField(
        label='Apenas ativas',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )


class WebhookConfigForm(forms.Form):
    """
    Formulário para configuração de webhook
    """
    webhook_url = forms.URLField(
        label='URL do Webhook',
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://meusite.com/webhook/whatsapp'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Define URL padrão baseada no EVOLUTION_API_BASE_URL se não houver webhook_url nos dados iniciais
        initial_data = kwargs.get('initial', {})
        
        # Se não há URL nos dados iniciais, definir URL padrão
        if not initial_data.get('webhook_url'):
            base_url = getattr(settings, 'BACKEND_BASE_URL', '').rstrip('/')
            if base_url:
                default_webhook = f"{base_url}/whatsapp_connector/v1/evolution/webhook/receiver"
                # Atualizar o valor inicial do campo
                if hasattr(self.fields['webhook_url'], 'initial'):
                    self.fields['webhook_url'].initial = default_webhook
                # Definir valor no widget
                self.fields['webhook_url'].widget.attrs['value'] = default_webhook
                # Se há dados bound (formulário sendo reprocessado), atualizar também
                if not args and 'webhook_url' not in initial_data:
                    self.initial['webhook_url'] = default_webhook
    
    enabled = forms.BooleanField(
        label='Webhook Ativo',
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    events = forms.MultipleChoiceField(
        label='Eventos',
        choices=[
            ('MESSAGES_UPSERT', 'Mensagens Recebidas'),
            ('MESSAGES_UPDATE', 'Mensagens Atualizadas'),
            ('CONNECTION_UPDATE', 'Status de Conexão'),
            ('QRCODE_UPDATED', 'QR Code Atualizado'),
            ('CHATS_UPSERT', 'Conversas Criadas'),
            ('CONTACTS_UPSERT', 'Contatos Atualizados'),
        ],
        initial=['MESSAGES_UPSERT', 'CONNECTION_UPDATE'],
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        })
    )
    
    def clean_webhook_url(self):
        """
        Valida URL do webhook
        """
        webhook_url = self.cleaned_data.get('webhook_url')
        
        if webhook_url:
            # Remove barra final
            webhook_url = webhook_url.rstrip('/')
            
            # Recomenda HTTPS
            if not webhook_url.startswith('https://') and 'localhost' not in webhook_url:
                raise forms.ValidationError(
                    'Recomendado usar HTTPS para webhooks em produção'
                )
        
        return webhook_url


class AuthorizedNumbersForm(forms.Form):
    """
    Formulário para configuração de números autorizados
    """
    authorized_numbers = forms.CharField(
        label='Números Autorizados',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 8,
            'placeholder': 'Digite os números autorizados, um por linha ou separados por vírgula:\n\n5511999999999\n5511888888888\n5521777777777'
        }),
        required=False,
        help_text='Lista de números autorizados a interagir com este bot. Deixe vazio para permitir todos os números.'
    )
    
    def clean_authorized_numbers(self):
        """
        Valida e padroniza os números autorizados
        """
        numbers_text = self.cleaned_data.get('authorized_numbers', '').strip()
        
        if not numbers_text:
            return ''
        
        # Substitui quebras de linha por vírgulas e separa
        numbers_text = numbers_text.replace('\n', ',').replace('\r', '')
        numbers = [num.strip() for num in numbers_text.split(',')]
        
        # Remove números vazios
        numbers = [num for num in numbers if num]
        
        # Valida cada número
        validated_numbers = []
        for num in numbers:
            # Remove caracteres não numéricos
            clean_num = re.sub(r'[^\d]', '', num)
            
            if len(clean_num) < 10:
                raise forms.ValidationError(f'Número inválido: {num}. Use formato completo com DDI e DDD (ex: 5511999999999)')
            
            if len(clean_num) > 15:
                raise forms.ValidationError(f'Número muito longo: {num}')
            
            # Adiciona à lista se não estiver duplicado
            if clean_num not in validated_numbers:
                validated_numbers.append(clean_num)
        
        # Retorna como string separada por vírgula
        return ', '.join(validated_numbers)
