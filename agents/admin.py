from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Q
from .models import Agent, AgentFile, AgentDocument, Conversation, Message, ConversationSummary, LongTermMemory, \
    GlobalSettings, LangchainCollection, LangchainEmbedding, LLMUsage


class AgentFileInline(admin.TabularInline):
    """Inline para arquivos do agent"""
    model = AgentFile
    extra = 0
    fields = ('name', 'file', 'file_type', 'status', 'is_active')
    readonly_fields = ('status',)
    show_change_link = True

@admin.register(LangchainCollection)
class LangchainCollectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'agent_display', 'uuid', 'documents_count']
    search_fields = ['name']
    readonly_fields = ['uuid', 'name', 'cmetadata', 'agent_display']

    def agent_display(self, obj):
        agent = obj.agent
        if agent:
            return format_html('<a href="/admin/langchain_poc/agent/{}/change/">{}</a>', agent.id, agent.display_name)
        return '-'
    agent_display.short_description = 'Agente'

    def documents_count(self, obj):
        return obj.langchainembedding_set.count()
    documents_count.short_description = 'Documentos'

    def has_add_permission(self, request):
        return False


@admin.register(LangchainEmbedding)
class LangchainEmbeddingAdmin(admin.ModelAdmin):
    list_display = ['id_short', 'source_display', 'page_display', 'content_short', 'collection']
    list_filter = ['collection']
    search_fields = ['document', 'id']
    readonly_fields = ['id', 'collection', 'document', 'cmetadata']

    def id_short(self, obj):
        return obj.id[:12] + '...'
    id_short.short_description = 'ID'

    def source_display(self, obj):
        if obj.cmetadata and isinstance(obj.cmetadata, dict):
            return obj.cmetadata.get('source', 'N/A')
        return 'N/A'
    source_display.short_description = 'Fonte'

    def page_display(self, obj):
        if obj.cmetadata and isinstance(obj.cmetadata, dict):
            return obj.cmetadata.get('page', '-')
        return '-'
    page_display.short_description = 'Pagina'

    def content_short(self, obj):
        if obj.document:
            text = obj.document[:100] + '...' if len(obj.document) > 100 else obj.document
            return text
        return ''
    content_short.short_description = 'Conteudo'

    def has_add_permission(self, request):
        return False

@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    """
    Admin para configurações de LLM (Agent)
    """
    list_display = ['display_name', 'owner', 'provider_badge', 'model', 'temperature', 'max_tokens', 'has_calendar_tools', 'files_count', 'created_at']
    list_filter = ['owner', 'name', 'has_calendar_tools', 'created_at']
    search_fields = ['display_name', 'model', 'role', 'available_tools', 'input_context', 'steps', 'expectation',
                     'anti_hallucination_policies', 'applied_example', 'useful_default_messages', 'owner__full_name',
                     'owner__email']
    readonly_fields = ['created_at', 'updated_at', 'files_count']
    raw_id_fields = ['owner']
    inlines = [AgentFileInline]
    actions = ['duplicate_agent']

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
        ('Instruções (RISE Framework)', {
            'fields': ('role', 'available_tools', 'input_context', 'steps', 'expectation', 'anti_hallucination_policies',
                       'applied_example', 'useful_default_messages'),
            'classes': ('wide',),
            'description': 'Estes campos constroem o prompt do agente. Preencha para customizar o comportamento.'
        }),
        ('Estatísticas', {
            'fields': ('files_count',),
            'classes': ('collapse',)
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

    def files_count(self, obj):
        """Exibe a contagem de arquivos"""
        if hasattr(obj, 'files_total'):
            total = obj.files_total
            active = obj.files_active
        else:
            total = obj.files.count()
            active = obj.files.filter(is_active=True).count()

        return format_html(
            '{} arquivo(s) <span class="text-muted">({} ativo(s))</span>',
            total, active
        )
    files_count.short_description = 'Arquivos'

    def duplicate_agent(self, request, queryset):
        """Action para duplicar agentes"""
        count = 0
        for agent in queryset:
            agent.pk = None
            agent.display_name = f"{agent.display_name} (Cópia)"
            agent.save()
            count += 1

        self.message_user(request, f'{count} agente(s) duplicado(s) com sucesso.')
    duplicate_agent.short_description = 'Duplicar agentes selecionados'

    def get_queryset(self, request):
        """Otimiza queryset com select_related e annotations."""
        qs = super().get_queryset(request)
        return qs.select_related('owner').annotate(
            files_total=Count('files'),
            files_active=Count('files', filter=Q(files__is_active=True))
        )


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


class MessageInline(admin.TabularInline):
    """Inline para mensagens da conversa"""
    model = Message
    extra = 0
    fields = ('message_type', 'content_preview', 'response_preview', 'processing_status', 'created_at')
    readonly_fields = ('content_preview', 'response_preview', 'created_at')
    can_delete = False
    show_change_link = True

    def content_preview(self, obj):
        """Prévia do conteúdo"""
        if not obj.content:
            return '-'
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Mensagem'

    def response_preview(self, obj):
        """Prévia da resposta"""
        if not obj.response:
            return '-'
        return obj.response[:50] + '...' if len(obj.response) > 50 else obj.response
    response_preview.short_description = 'Resposta'

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """
    Admin para conversas
    """
    list_display = ['id', 'contact_display', 'from_number', 'to_number', 'evolution_instance', 'status_badge', 'messages_count', 'created_at', 'updated_at']
    list_filter = ['status', 'evolution_instance', 'created_at', 'updated_at']
    search_fields = ['from_number', 'to_number', 'contact__name', 'contact__phone_number']
    readonly_fields = ['created_at', 'updated_at', 'messages_count']
    raw_id_fields = ['contact', 'evolution_instance']
    inlines = [MessageInline]
    actions = ['change_to_ai', 'change_to_human', 'close_conversations']

    fieldsets = (
        ('Contato e Instância', {
            'fields': ('contact', 'evolution_instance')
        }),
        ('Números', {
            'fields': ('from_number', 'to_number')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Resumo do Contato', {
            'fields': ('contact_summary',),
            'classes': ('collapse',)
        }),
        ('Estatísticas', {
            'fields': ('messages_count',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def contact_display(self, obj):
        """Exibe informações do contato"""
        if obj.contact:
            return format_html(
                '<strong>{}</strong><br><small class="text-muted">{}</small>',
                obj.contact.name or 'Sem nome',
                obj.contact.phone_number
            )
        return format_html('<span class="text-muted">-</span>')
    contact_display.short_description = 'Contato'

    def status_badge(self, obj):
        """Retorna badge colorido para status"""
        colors = {
            'ai': 'info',
            'human': 'warning',
            'closed': 'secondary'
        }
        icons = {
            'ai': 'bi-robot',
            'human': 'bi-person',
            'closed': 'bi-x-circle'
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

    def messages_count(self, obj):
        """Retorna a contagem de mensagens"""
        if hasattr(obj, 'total_messages'):
            return obj.total_messages
        return obj.messages.count()
    messages_count.short_description = 'Mensagens'

    def change_to_ai(self, request, queryset):
        """Muda status para AI"""
        updated = queryset.update(status='ai')
        self.message_user(request, f'{updated} conversa(s) alterada(s) para AI.')
    change_to_ai.short_description = 'Mudar para atendimento por IA'

    def change_to_human(self, request, queryset):
        """Muda status para humano"""
        updated = queryset.update(status='human')
        self.message_user(request, f'{updated} conversa(s) alterada(s) para Humano.')
    change_to_human.short_description = 'Mudar para atendimento humano'

    def close_conversations(self, request, queryset):
        """Encerra conversas"""
        updated = queryset.update(status='closed')
        self.message_user(request, f'{updated} conversa(s) encerrada(s).')
    close_conversations.short_description = 'Encerrar conversas'

    def get_queryset(self, request):
        """Otimiza queryset com select_related e annotations"""
        qs = super().get_queryset(request)
        return qs.select_related('contact', 'evolution_instance').annotate(
            total_messages=Count('messages')
        )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """
    Admin para mensagens (cada mensagem tem content do usuário e response da IA)
    """
    list_display = ['id', 'conversation', 'message_type_badge', 'content_preview', 'response_preview', 'processing_status_badge', 'received_at']
    list_filter = ['message_type', 'processing_status', 'received_while_inactive', 'created_at', 'received_at', 'conversation__evolution_instance']
    search_fields = ['content', 'response', 'sender_name', 'message_id']
    readonly_fields = ['created_at', 'updated_at', 'received_at', 'message_id']
    raw_id_fields = ['conversation', 'owner']
    date_hierarchy = 'received_at'

    fieldsets = (
        ('Conversa e Proprietário', {
            'fields': ('conversation', 'owner')
        }),
        ('Identificação', {
            'fields': ('message_id', 'message_type', 'sender_name', 'source')
        }),
        ('Conteúdo', {
            'fields': ('content', 'response')
        }),
        ('Mídia', {
            'fields': ('media_url', 'media_file'),
            'classes': ('collapse',)
        }),
        ('Processamento', {
            'fields': ('processing_status', 'audio_transcription', 'received_while_inactive')
        }),
        ('Dados Brutos', {
            'fields': ('raw_data',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('received_at', 'created_at', 'updated_at')
        }),
    )

    def message_type_badge(self, obj):
        """Retorna badge colorido para tipo de mensagem"""
        colors = {
            'text': 'primary',
            'image': 'success',
            'audio': 'info',
            'video': 'warning',
            'document': 'secondary',
            'extended_text': 'dark'
        }
        icons = {
            'text': 'bi-chat-text',
            'image': 'bi-image',
            'audio': 'bi-mic',
            'video': 'bi-camera-video',
            'document': 'bi-file-earmark',
            'extended_text': 'bi-text-paragraph'
        }
        color = colors.get(obj.message_type, 'secondary')
        icon = icons.get(obj.message_type, 'bi-question')
        return format_html(
            '<span class="badge bg-{} d-inline-flex align-items-center"><i class="{} me-1"></i>{}</span>',
            color,
            icon,
            obj.get_message_type_display()
        )
    message_type_badge.short_description = 'Tipo'
    message_type_badge.admin_order_field = 'message_type'

    def processing_status_badge(self, obj):
        """Retorna badge colorido para status de processamento"""
        colors = {
            'pending': 'warning',
            'processing': 'info',
            'completed': 'success',
            'failed': 'danger'
        }
        color = colors.get(obj.processing_status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_processing_status_display()
        )
    processing_status_badge.short_description = 'Status'
    processing_status_badge.admin_order_field = 'processing_status'

    def content_preview(self, obj):
        """Retorna uma prévia do conteúdo do usuário"""
        if not obj.content:
            return format_html('<span class="text-muted">-</span>')
        if len(obj.content) > 80:
            return obj.content[:80] + '...'
        return obj.content
    content_preview.short_description = 'Usuário'

    def response_preview(self, obj):
        """Retorna uma prévia da resposta da IA"""
        if not obj.response:
            return format_html('<span class="text-muted">-</span>')
        if len(obj.response) > 80:
            return obj.response[:80] + '...'
        return obj.response
    response_preview.short_description = 'IA'

    def get_queryset(self, request):
        """Otimiza queryset com select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('conversation', 'owner', 'conversation__contact', 'conversation__evolution_instance')


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
    list_display = ['id', 'contact_display', 'conversation', 'content_preview', 'created_at']
    list_filter = ['created_at', 'conversation__evolution_instance']
    search_fields = ['content', 'contact__name', 'contact__phone_number']
    readonly_fields = ['created_at', 'embedding']
    raw_id_fields = ['contact', 'conversation']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Relacionamentos', {
            'fields': ('contact', 'conversation')
        }),
        ('Conteúdo', {
            'fields': ('content',),
            'classes': ('wide',)
        }),
        ('Embedding (Vetorização)', {
            'fields': ('embedding',),
            'classes': ('collapse',),
            'description': 'Representação vetorial do conteúdo para busca semântica'
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )

    def contact_display(self, obj):
        """Exibe informações do contato"""
        if obj.contact:
            return format_html(
                '<strong>{}</strong><br><small class="text-muted">{}</small>',
                obj.contact.name or 'Sem nome',
                obj.contact.phone_number
            )
        return format_html('<span class="text-muted">-</span>')
    contact_display.short_description = 'Contato'

    def content_preview(self, obj):
        """Retorna uma prévia do conteúdo"""
        if len(obj.content) > 100:
            return obj.content[:100] + '...'
        return obj.content
    content_preview.short_description = 'Conteúdo'

    def get_queryset(self, request):
        """Otimiza queryset com select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('contact', 'conversation', 'conversation__evolution_instance')

@admin.register(GlobalSettings)
class GlobalSettingsAdmin(admin.ModelAdmin):
    """
    Admin para as Configurações Globais do sistema (Singleton).
    """
    list_display = ['id', 'role', 'updated_at']
    search_fields = ['role', 'available_tools', 'input_context', 'steps', 'expectation', 'anti_hallucination_policies',
                     'applied_example', 'useful_default_messages', 'global_system_prompt']
    readonly_fields = ['updated_at']

    fieldsets = (
        ('Instruções Globais (RISE Framework)', {
            'fields': ('role', 'available_tools', 'input_context', 'steps', 'expectation', 'anti_hallucination_policies',
                       'applied_example', 'useful_default_messages'),
            'classes': ('wide',),
            'description': 'Estes campos definem o comportamento padrão para todos os agentes.'
        }),
        ('[LEGADO] Prompt Global', {
            'fields': ('global_system_prompt',),
            'classes': ('wide', 'collapse'),
            'description': 'Este campo é legado e será removido em versões futuras. Use os campos RISE acima.'
        }),
        ('Timestamps', {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        # Impede a criação de novas instâncias, garantindo o padrão Singleton
        return not GlobalSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Impede a exclusão da instância única
        return False

@admin.register(LLMUsage)
class LLMUsageAdmin(admin.ModelAdmin):
    """
    Admin para rastreamento de uso e custos de LLM
    """
    change_list_template = 'admin/agents/llmusage/change_list.html'

    list_display = [
        'id',
        'conversation_link',
        'provider_badge',
        'model_name',
        'tokens_display',
        'cost_display',
        'cache_display',
        'response_time_display',
        'created_at'
    ]
    list_filter = [
        'provider',
        'model_name',
        'agent',
        'created_at',
        'conversation__evolution_instance'
    ]
    search_fields = [
        'conversation__from_number',
        'conversation__contact__name',
        'conversation__contact__phone_number',
        'model_name',
        'tools_used'
    ]
    readonly_fields = [
        'conversation',
        'message',
        'agent',
        'provider',
        'model_name',
        'input_tokens',
        'output_tokens',
        'total_tokens',
        'cache_creation_tokens',
        'cache_read_tokens',
        'input_cost',
        'output_cost',
        'cache_creation_cost',
        'cache_read_cost',
        'total_cost',
        'response_time_ms',
        'context_size',
        'tools_used',
        'created_at',
        'cost_breakdown'
    ]
    raw_id_fields = ['conversation', 'message', 'agent']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Relacionamentos', {
            'fields': ('conversation', 'message', 'agent')
        }),
        ('Modelo', {
            'fields': ('provider', 'model_name')
        }),
        ('Tokens', {
            'fields': ('input_tokens', 'output_tokens', 'total_tokens')
        }),
        ('Cache (Anthropic)', {
            'fields': ('cache_creation_tokens', 'cache_read_tokens'),
            'classes': ('collapse',)
        }),
        ('Custos (USD)', {
            'fields': ('cost_breakdown', 'input_cost', 'output_cost', 'cache_creation_cost', 'cache_read_cost', 'total_cost')
        }),
        ('Metadados', {
            'fields': ('response_time_ms', 'context_size', 'tools_used'),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )

    def conversation_link(self, obj):
        """Link para a conversa"""
        if obj.conversation:
            from django.urls import reverse
            from django.utils.html import format_html
            url = reverse('admin:agents_conversation_change', args=[obj.conversation.id])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                f"Conv. #{obj.conversation.id}"
            )
        return '-'
    conversation_link.short_description = 'Conversa'

    def provider_badge(self, obj):
        """Badge colorido para o provider"""
        colors = {
            'openai': 'success',
            'anthropic': 'info',
            'google': 'warning',
            'mistral': 'primary'
        }
        color = colors.get(obj.provider, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.provider.upper()
        )
    provider_badge.short_description = 'Provider'
    provider_badge.admin_order_field = 'provider'

    def tokens_display(self, obj):
        """Exibe tokens formatados"""
        return format_html(
            '<strong>{}</strong> → <strong>{}</strong><br>'
            '<small class="text-muted">Total: {}</small>',
            f"{obj.input_tokens:,}",
            f"{obj.output_tokens:,}",
            f"{obj.total_tokens:,}"
        )
    tokens_display.short_description = 'Tokens (in → out)'

    def cost_display(self, obj):
        """Exibe custo total formatado"""
        cost_usd = float(obj.total_cost)
        cost_brl = cost_usd * 5.33  # Conversão USD -> BRL

        if cost_usd < 0.001:
            color = 'success'
        elif cost_usd < 0.01:
            color = 'info'
        elif cost_usd < 0.1:
            color = 'warning'
        else:
            color = 'danger'

        cost_usd_formatted = f"${cost_usd:.6f}"
        cost_brl_formatted = f"R${cost_brl:.6f}"

        return format_html(
            '<span class="badge bg-{}" style="font-size: 14px;">{}</span><br>'
            '<small class="text-muted">{}</small>',
            color,
            cost_usd_formatted,
            cost_brl_formatted
        )
    cost_display.short_description = 'Custo'
    cost_display.admin_order_field = 'total_cost'

    def cache_display(self, obj):
        """Exibe informações de cache se disponível"""
        if obj.cache_creation_tokens > 0 or obj.cache_read_tokens > 0:
            savings = float(obj.cache_creation_cost - obj.cache_read_cost)
            savings_formatted = f"${savings:.6f}" if savings > 0 else "$0.000000"

            return format_html(
                '💾 Criado: {}<br>'
                '⚡ Lido: {}<br>'
                '<span class="badge bg-success">Economia: {}</span>',
                f"{obj.cache_creation_tokens:,}",
                f"{obj.cache_read_tokens:,}",
                savings_formatted
            )
        return format_html('<span class="text-muted">-</span>')
    cache_display.short_description = 'Cache'

    def response_time_display(self, obj):
        """Exibe tempo de resposta formatado"""
        if obj.response_time_ms:
            seconds = obj.response_time_ms / 1000
            if seconds < 1:
                return format_html(
                    '<span class="badge bg-success">{} ms</span>',
                    obj.response_time_ms
                )
            elif seconds < 5:
                time_formatted = f"{seconds:.2f}s"
                return format_html(
                    '<span class="badge bg-info">{}</span>',
                    time_formatted
                )
            else:
                time_formatted = f"{seconds:.2f}s"
                return format_html(
                    '<span class="badge bg-warning">{}</span>',
                    time_formatted
                )
        return '-'
    response_time_display.short_description = 'Tempo'
    response_time_display.admin_order_field = 'response_time_ms'

    def cost_breakdown(self, obj):
        """Exibe breakdown detalhado dos custos"""
        from django.utils.safestring import mark_safe

        breakdown_html = '<div style="background: #f5f5f5; padding: 15px; border-radius: 4px;">'
        breakdown_html += '<h4 style="margin-top: 0;">Breakdown de Custos</h4>'
        breakdown_html += '<table style="width: 100%; border-collapse: collapse;">'

        # Input
        breakdown_html += f'''
        <tr style="border-bottom: 1px solid #ddd;">
            <td style="padding: 8px;"><strong>Input</strong></td>
            <td style="padding: 8px;">{obj.input_tokens:,} tokens</td>
            <td style="padding: 8px; text-align: right;">${float(obj.input_cost):.6f}</td>
        </tr>
        '''

        # Output
        breakdown_html += f'''
        <tr style="border-bottom: 1px solid #ddd;">
            <td style="padding: 8px;"><strong>Output</strong></td>
            <td style="padding: 8px;">{obj.output_tokens:,} tokens</td>
            <td style="padding: 8px; text-align: right;">${float(obj.output_cost):.6f}</td>
        </tr>
        '''

        # Cache (se houver)
        if obj.cache_creation_tokens > 0:
            breakdown_html += f'''
            <tr style="border-bottom: 1px solid #ddd;">
                <td style="padding: 8px;"><strong>Cache (criação)</strong></td>
                <td style="padding: 8px;">{obj.cache_creation_tokens:,} tokens</td>
                <td style="padding: 8px; text-align: right;">${float(obj.cache_creation_cost):.6f}</td>
            </tr>
            '''

        if obj.cache_read_tokens > 0:
            savings = float(obj.cache_creation_cost - obj.cache_read_cost)
            breakdown_html += f'''
            <tr style="border-bottom: 1px solid #ddd; background-color: #d4edda;">
                <td style="padding: 8px;"><strong>Cache (leitura)</strong></td>
                <td style="padding: 8px;">{obj.cache_read_tokens:,} tokens</td>
                <td style="padding: 8px; text-align: right;">
                    ${float(obj.cache_read_cost):.6f}
                    <br><small style="color: #155724;">Economia: ${savings:.6f}</small>
                </td>
            </tr>
            '''

        # Total
        breakdown_html += f'''
        <tr style="background-color: #e9ecef; font-weight: bold;">
            <td style="padding: 8px;">TOTAL</td>
            <td style="padding: 8px;">{obj.total_tokens:,} tokens</td>
            <td style="padding: 8px; text-align: right; font-size: 16px;">${float(obj.total_cost):.6f}</td>
        </tr>
        '''

        breakdown_html += '</table></div>'

        return mark_safe(breakdown_html)
    cost_breakdown.short_description = 'Breakdown'

    def get_queryset(self, request):
        """Otimiza queryset"""
        qs = super().get_queryset(request)
        return qs.select_related(
            'conversation',
            'conversation__contact',
            'conversation__evolution_instance',
            'agent',
            'message'
        )

    def has_add_permission(self, request):
        """Não permite adicionar manualmente"""
        return False

    def has_change_permission(self, request, obj=None):
        """Não permite editar"""
        return False

    def changelist_view(self, request, extra_context=None):
        """Adiciona sumário com totais ao topo da lista"""
        from django.db.models import Sum

        # Pegar o queryset filtrado (o que está sendo exibido)
        response = super().changelist_view(request, extra_context=extra_context)

        try:
            # Acessar o queryset filtrado da changelist
            qs = response.context_data['cl'].queryset

            # Calcular agregações
            totals = qs.aggregate(
                total_input_tokens=Sum('input_tokens'),
                total_output_tokens=Sum('output_tokens'),
                total_tokens_sum=Sum('total_tokens'),
                total_cost_sum=Sum('total_cost'),
                count=Count('id')
            )

            # Formatar valores
            total_input = totals['total_input_tokens'] or 0
            total_output = totals['total_output_tokens'] or 0
            total_tokens = totals['total_tokens_sum'] or 0
            total_cost_usd = float(totals['total_cost_sum'] or 0)
            total_cost_brl = total_cost_usd * 5.33
            count = totals['count']

            # Criar mensagem de sumário
            from django.utils.safestring import mark_safe
            summary = f'''
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 20px;
                        border-radius: 8px;
                        margin-bottom: 20px;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <h3 style="margin-top: 0; margin-bottom: 15px; font-size: 18px;">
                    📊 Resumo do Período Selecionado
                </h3>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
                    <div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 6px;">
                        <div style="font-size: 12px; opacity: 0.9; margin-bottom: 5px;">Total de Chamadas</div>
                        <div style="font-size: 24px; font-weight: bold;">{count:,}</div>
                    </div>
                    <div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 6px;">
                        <div style="font-size: 12px; opacity: 0.9; margin-bottom: 5px;">Tokens de Entrada</div>
                        <div style="font-size: 24px; font-weight: bold;">{total_input:,}</div>
                    </div>
                    <div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 6px;">
                        <div style="font-size: 12px; opacity: 0.9; margin-bottom: 5px;">Tokens de Saída</div>
                        <div style="font-size: 24px; font-weight: bold;">{total_output:,}</div>
                    </div>
                    <div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 6px;">
                        <div style="font-size: 12px; opacity: 0.9; margin-bottom: 5px;">Total de Tokens</div>
                        <div style="font-size: 24px; font-weight: bold;">{total_tokens:,}</div>
                    </div>
                    <div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 6px;">
                        <div style="font-size: 12px; opacity: 0.9; margin-bottom: 5px;">Custo Total (USD)</div>
                        <div style="font-size: 24px; font-weight: bold;">${total_cost_usd:.4f}</div>
                    </div>
                    <div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 6px;">
                        <div style="font-size: 12px; opacity: 0.9; margin-bottom: 5px;">Custo Total (BRL)</div>
                        <div style="font-size: 24px; font-weight: bold;">R$ {total_cost_brl:.4f}</div>
                    </div>
                </div>
            </div>
            '''

            # Adicionar ao contexto
            extra_context = extra_context or {}
            extra_context['summary_stats'] = mark_safe(summary)
            response.context_data.update(extra_context)

        except (AttributeError, KeyError):
            pass

        return response
