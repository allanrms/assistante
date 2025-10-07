from django.contrib import admin
from django.utils.html import format_html
from .models import LLMProviderConfig, ChatHistory, AssistantContextFile


@admin.register(LLMProviderConfig)
class LLMProviderConfigAdmin(admin.ModelAdmin):
    """
    Admin para configurações de LLM
    """
    list_display = ['display_name', 'owner', 'provider_badge', 'model', 'temperature', 'max_tokens', 'has_calendar_tools', 'created_at']
    list_filter = ['owner', 'name', 'has_calendar_tools', 'created_at']
    search_fields = ['display_name', 'model', 'instructions', 'owner__full_name', 'owner__email']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['owner']

    fieldsets = (
        ('Proprietário', {
            'fields': ('owner',)
        }),
        ('Configuração Básica', {
            'fields': ('display_name', 'name', 'model')
        }),
        ('Parâmetros do Modelo', {
            'fields': ('temperature', 'max_tokens', 'top_p', 'presence_penalty', 'frequency_penalty')
        }),
        ('Ferramentas', {
            'fields': ('has_calendar_tools',)
        }),
        ('Instruções', {
            'fields': ('instructions',),
            'classes': ('wide',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def provider_badge(self, obj):
        """Exibe o provedor com badge colorido"""
        colors = {
            'openai': 'success',
            'anthropic': 'info',
            'google': 'warning',
            'mistral': 'primary',
            'cohere': 'secondary',
            'meta': 'dark',
            'xai': 'light',
            'other': 'secondary'
        }
        color = colors.get(obj.name, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_name_display()
        )
    provider_badge.short_description = 'Provedor'

    def get_queryset(self, request):
        """Otimiza queryset com select_related para owner."""
        qs = super().get_queryset(request)
        return qs.select_related('owner')


@admin.register(ChatHistory)
class ChatHistoryAdmin(admin.ModelAdmin):
    """
    Admin para histórico de chats
    """
    list_display = ['session_id', 'type', 'external_id', 'message', 'created_at', 'closed']
    list_filter = ['type', 'closed', 'created_at']
    search_fields = ['session_id']
    readonly_fields = ['created_at', 'message', ]
    
    # fieldsets = (
    #     ('Informações da Sessão', {
    #         'fields': ('session_id', 'message',)
    #     }),
    #     ('Mensagem Completa', {
    #         'fields': ('message',),
    #         'classes': ('collapse',)
    #     }),
    #     ('Timestamps', {
    #         'fields': ('created_at',)
    #     }),
    # )
    
    def message_type(self, obj):
        """Retorna o tipo da mensagem"""
        return obj.message.get('type', 'unknown')
    message_type.short_description = 'Tipo'
    
    # def content_preview(self, obj):
    #     """Retorna uma prévia do conteúdo"""
    #     content = obj.message.get('content', '')
    #     if len(content) > 100:
    #         return content[:100] + '...'
    #     return content
    # content_preview.short_description = 'Conteúdo'


@admin.register(AssistantContextFile)
class AssistantContextFileAdmin(admin.ModelAdmin):
    """
    Admin para arquivos de contexto dos assistants
    """
    list_display = ['name', 'llm_config', 'file_type_badge', 'status_badge', 'file_size_display', 'is_active', 'created_at']
    list_filter = ['file_type', 'status', 'is_active', 'created_at', 'llm_config']
    search_fields = ['name', 'llm_config__display_name', 'extracted_content']
    readonly_fields = ['file_size', 'extracted_content', 'error_message', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('llm_config', 'name', 'file', 'is_active')
        }),
        ('Processamento', {
            'fields': ('file_type', 'status', 'error_message', 'file_size')
        }),
        ('Conteúdo Extraído', {
            'fields': ('extracted_content',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def file_type_badge(self, obj):
        """Retorna badge colorido para tipo de arquivo"""
        colors = {
            'pdf': 'danger',
            'docx': 'primary', 
            'txt': 'secondary',
            'md': 'info',
            'csv': 'success',
            'json': 'warning',
            'html': 'dark'
        }
        color = colors.get(obj.file_type, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_file_type_display()
        )
    file_type_badge.short_description = 'Tipo'
    file_type_badge.admin_order_field = 'file_type'
    
    def status_badge(self, obj):
        """Retorna badge colorido para status"""
        colors = {
            'ready': 'success',
            'processing': 'warning',
            'error': 'danger',
            'uploading': 'info'
        }
        icons = {
            'ready': 'bi-check-circle',
            'processing': 'bi-clock',
            'error': 'bi-exclamation-triangle',
            'uploading': 'bi-upload'
        }
        color = colors.get(obj.status, 'secondary')
        icon = icons.get(obj.status, 'bi-question')
        return format_html(
            '<span class="badge bg-{} d-inline-flex align-items-center"><i class="{} me-1"></i>{}</span>',
            color,
            icon,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def file_size_display(self, obj):
        """Retorna o tamanho do arquivo formatado"""
        return obj.get_file_size_display()
    file_size_display.short_description = 'Tamanho'
    file_size_display.admin_order_field = 'file_size'
