from django.contrib import admin
from django.utils.html import format_html
from .models import Agent, AgentFile, AgentDocument, Conversation, Message, ConversationSummary, LongTermMemory


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    """
    Admin para configurações de LLM (Agent)
    """
    list_display = ['display_name', 'owner', 'provider_badge', 'model', 'temperature', 'max_tokens', 'has_calendar_tools', 'created_at']
    list_filter = ['owner', 'name', 'has_calendar_tools', 'created_at']
    search_fields = ['display_name', 'model', 'system_prompt', 'owner__full_name', 'owner__email']
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
            'fields': ('system_prompt',),
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


@admin.register(AgentFile)
class AgentFileAdmin(admin.ModelAdmin):
    """
    Admin para arquivos de contexto dos agents
    """
    list_display = ['name', 'agent', 'file_type_badge', 'status_badge', 'file_size_display', 'is_active', 'vectorized', 'created_at']
    list_filter = ['file_type', 'status', 'is_active', 'vectorized', 'created_at', 'agent']
    search_fields = ['name', 'agent__display_name', 'extracted_content']
    readonly_fields = ['file_size', 'extracted_content', 'error_message', 'created_at', 'updated_at']
    raw_id_fields = ['agent']

    fieldsets = (
        ('Informações Básicas', {
            'fields': ('agent', 'name', 'file', 'is_active')
        }),
        ('Processamento', {
            'fields': ('file_type', 'status', 'error_message', 'file_size', 'vectorized')
        }),
        ('OpenAI', {
            'fields': ('openai_file_id',),
            'classes': ('collapse',)
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
            'html': 'dark',
            'jpg': 'primary',
            'png': 'primary',
            'gif': 'primary',
            'webp': 'primary',
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


@admin.register(AgentDocument)
class AgentDocumentAdmin(admin.ModelAdmin):
    """
    Admin para documentos vetorizados dos agents
    """
    list_display = ['id', 'agent', 'content_preview', 'created_at']
    list_filter = ['agent', 'created_at']
    search_fields = ['content', 'metadata']
    readonly_fields = ['created_at', 'embedding']
    raw_id_fields = ['agent']

    fieldsets = (
        ('Agent', {
            'fields': ('agent',)
        }),
        ('Conteúdo', {
            'fields': ('content', 'metadata')
        }),
        ('Embedding', {
            'fields': ('embedding',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )

    def content_preview(self, obj):
        """Retorna uma prévia do conteúdo"""
        if len(obj.content) > 100:
            return obj.content[:100] + '...'
        return obj.content
    content_preview.short_description = 'Conteúdo'


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """
    Admin para conversas
    """
    list_display = ['id', 'contact', 'from_number', 'to_number', 'status_badge', 'created_at', 'updated_at']
    list_filter = ['status', 'created_at', 'updated_at']
    search_fields = ['from_number', 'to_number', 'contact__name', 'contact__phone_number']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['contact']

    fieldsets = (
        ('Contato', {
            'fields': ('contact',)
        }),
        ('Números', {
            'fields': ('from_number', 'to_number')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def status_badge(self, obj):
        """Retorna badge colorido para status"""
        colors = {
            'ai': 'info',
            'human': 'warning',
            'closed': 'secondary'
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """
    Admin para mensagens (cada mensagem tem content do usuário e response da IA)
    """
    list_display = ['id', 'conversation', 'content_preview', 'response_preview', 'created_at']
    list_filter = ['created_at']
    search_fields = ['content', 'response']
    readonly_fields = ['created_at']
    raw_id_fields = ['conversation']

    fieldsets = (
        ('Conversa', {
            'fields': ('conversation',)
        }),
        ('Mensagem', {
            'fields': ('content', 'response')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )

    def content_preview(self, obj):
        """Retorna uma prévia do conteúdo do usuário"""
        if len(obj.content) > 80:
            return obj.content[:80] + '...'
        return obj.content
    content_preview.short_description = 'Usuário'

    def response_preview(self, obj):
        """Retorna uma prévia da resposta da IA"""
        if not obj.response:
            return '-'
        if len(obj.response) > 80:
            return obj.response[:80] + '...'
        return obj.response
    response_preview.short_description = 'IA'


@admin.register(ConversationSummary)
class ConversationSummaryAdmin(admin.ModelAdmin):
    """
    Admin para resumos de conversas
    """
    list_display = ['id', 'conversation', 'summary_preview', 'updated_at']
    list_filter = ['updated_at']
    search_fields = ['summary']
    readonly_fields = ['updated_at']
    raw_id_fields = ['conversation']

    fieldsets = (
        ('Conversa', {
            'fields': ('conversation',)
        }),
        ('Resumo', {
            'fields': ('summary',)
        }),
        ('Timestamps', {
            'fields': ('updated_at',)
        }),
    )

    def summary_preview(self, obj):
        """Retorna uma prévia do resumo"""
        if len(obj.summary) > 100:
            return obj.summary[:100] + '...'
        return obj.summary
    summary_preview.short_description = 'Resumo'


@admin.register(LongTermMemory)
class LongTermMemoryAdmin(admin.ModelAdmin):
    """
    Admin para memória de longo prazo
    """
    list_display = ['id', 'contact', 'content_preview', 'created_at']
    list_filter = ['created_at']
    search_fields = ['content', 'contact__name', 'contact__phone_number']
    readonly_fields = ['created_at', 'embedding']
    raw_id_fields = ['contact']

    fieldsets = (
        ('Contato', {
            'fields': ('contact',)
        }),
        ('Conversa Origem', {
            'fields': ('conversation',)
        }),
        ('Conteúdo', {
            'fields': ('content',)
        }),
        ('Embedding', {
            'fields': ('embedding',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )

    def content_preview(self, obj):
        """Retorna uma prévia do conteúdo"""
        if len(obj.content) > 100:
            return obj.content[:100] + '...'
        return obj.content
    content_preview.short_description = 'Conteúdo'