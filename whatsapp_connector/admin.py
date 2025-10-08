from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from .models import EvolutionInstance, MessageHistory, ImageProcessingJob, ChatSession


@admin.register(EvolutionInstance)
class EvolutionInstanceAdmin(admin.ModelAdmin):
    """
    Admin para gerenciar instâncias Evolution API
    """
    list_display = ['name', 'instance_name', 'instance_evolution_id', 'owner', 'status_badge', 'connection_info',
                    'llm_config_display', 'authorized_numbers_count', 'is_active', 'created_at', 'last_connection']
    list_filter = ['status', 'is_active', 'owner', 'llm_config', 'created_at']
    search_fields = ['name', 'instance_name', 'instance_evolution_id', 'phone_number', 'profile_name', 'owner__full_name', 'owner__email']
    readonly_fields = ['created_at', 'updated_at', 'last_connection', ]
    raw_id_fields = ['owner', 'llm_config']
    actions = ['update_connection_info']
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('name', 'instance_name', 'instance_evolution_id', 'owner', 'is_active')
        }),
        ('Configuração Evolution API', {
            'fields': ('base_url', 'api_key', 'webhook_url')
        }),
        ('Configuração de IA', {
            'fields': ('llm_config',)
        }),
        ('🔐 Configurações de Segurança', {
            'fields': ('ignore_own_messages', 'authorized_numbers'),
            'description': 'Configure quais números podem interagir com esta instância. Deixe vazio para permitir todos os números.'
        }),
        ('Status da Conexão', {
            'fields': ('status', 'phone_number', 'profile_name', 'profile_pic_url')
        }),
        ('Datas', {
            'fields': ('created_at', 'updated_at', 'last_connection')
        }),
    )
    
    def status_badge(self, obj):
        """Exibe status com badge colorido"""
        colors = {
            'connected': 'success',
            'connecting': 'warning', 
            'disconnected': 'secondary',
            'error': 'danger'
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def connection_info(self, obj):
        """Exibe informações de conexão formatadas"""
        return obj.connection_info
    connection_info.short_description = 'Conexão'
    
    def llm_config_display(self, obj):
        """Exibe configuração LLM formatada"""
        if obj.llm_config:
            return format_html(
                '<span class="badge bg-info">{}</span>',
                str(obj.llm_config)
            )
        return format_html('<span class="text-muted">Não configurado</span>')
    llm_config_display.short_description = 'Configuração LLM'

    def authorized_numbers_count(self, obj):
        """Exibe contagem de números autorizados com preview"""
        numbers = obj.get_authorized_numbers_list()
        if not numbers:
            return format_html(
                '<span class="badge bg-success" title="Todos os números são autorizados">🌐 Todos</span>'
            )

        # Criar preview dos números
        preview = ', '.join(numbers[:3])
        if len(numbers) > 3:
            preview += f'... (+{len(numbers) - 3})'

        return format_html(
            '<span class="badge bg-warning" title="{}" style="cursor: help;">🔐 {} número(s)</span>',
            ', '.join(numbers),
            len(numbers)
        )
    authorized_numbers_count.short_description = 'Contatos Autorizados'
    
    def save_model(self, request, obj, form, change):
        """Define o client do usuário atual como owner se não foi especificado"""
        if not change:  # Criação de nova instância
            if not obj.owner and request.user.client:
                obj.owner = request.user.client
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        """Otimiza queryset com select_related para owner."""
        qs = super().get_queryset(request)
        return qs.select_related('owner', 'llm_config')

    def update_connection_info(self, request, queryset):
        """Ação para atualizar informações de conexão das instâncias selecionadas"""
        updated_count = 0
        failed_count = 0

        for instance in queryset:
            if instance.fetch_and_update_connection_info():
                updated_count += 1
            else:
                failed_count += 1

        if updated_count > 0:
            messages.success(request, f'{updated_count} instância(s) atualizada(s) com sucesso.')

        if failed_count > 0:
            messages.warning(request, f'{failed_count} instância(s) falharam na atualização.')

    update_connection_info.short_description = "Atualizar informações de conexão"


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    """
    Admin para gerenciar sessões de chat
    """
    list_display = ('id', 'from_number', 'contact_display', 'to_number', 'instance_display', 'status', 'has_summary', 'message_count', 'created_at', 'updated_at')
    list_filter = ('status', 'evolution_instance', 'contact', 'created_at', 'updated_at')
    search_fields = ('from_number', 'to_number', 'contact_summary', 'evolution_instance__name', 'contact__name', 'contact__phone_number')
    readonly_fields = ('created_at', 'updated_at', 'message_count')
    raw_id_fields = ('contact', 'evolution_instance')

    fieldsets = (
        ('Session Info', {
            'fields': ('from_number', 'to_number', 'status', 'evolution_instance', 'contact')
        }),
        ('👤 Resumo do Contato', {
            'fields': ('contact_summary',),
            'description': 'Informações importantes sobre este usuário salvas pela IA'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
        ('Statistics', {
            'fields': ('message_count',)
        }),
    )
    
    def status_badge(self, obj):
        """Exibe status com badge colorido"""
        colors = {
            'ai': 'primary',
            'human': 'success',
            'closed': 'secondary'
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def message_count(self, obj):
        """Retorna o número de mensagens na sessão"""
        return obj.messages.count()
    message_count.short_description = 'Mensagens'

    def has_summary(self, obj):
        """Indica se o contato tem resumo salvo"""
        if obj.contact_summary:
            return format_html(
                '<span title="{}" style="cursor: help;">📝 ✅</span>',
                obj.contact_summary[:100] + ('...' if len(obj.contact_summary) > 100 else '')
            )
        return format_html('<span class="text-muted">-</span>')
    has_summary.short_description = 'Resumo'

    def instance_display(self, obj):
        """Exibe a instância Evolution formatada"""
        if obj.evolution_instance:
            return format_html(
                '<span class="badge bg-info" title="{}">📱 {}</span>',
                obj.evolution_instance.instance_name,
                obj.evolution_instance.name
            )
        return format_html('<span class="text-muted">-</span>')
    instance_display.short_description = 'Instância'
    instance_display.admin_order_field = 'evolution_instance__name'

    def contact_display(self, obj):
        """Exibe o contato vinculado formatado"""
        if obj.contact:
            return format_html(
                '<span class="badge bg-success" title="Total mensagens: {}">👤 {}</span>',
                obj.contact.total_messages,
                obj.contact
            )
        return format_html('<span class="text-muted">-</span>')
    contact_display.short_description = 'Contato'
    contact_display.admin_order_field = 'contact__name'

    def get_queryset(self, request):
        """Otimiza queryset com select_related para evolution_instance e contact."""
        qs = super().get_queryset(request)
        return qs.select_related('evolution_instance', 'contact')



@admin.register(MessageHistory)
class MessageHistoryAdmin(admin.ModelAdmin):
    list_display = ('chat_session_id', 'owner', 'get_from_number', 'sender_name', 'message_type', 'content', 'processing_status', 'inactive_badge', 'created_at', 'received_at')
    list_filter = ('owner', 'message_type', 'processing_status', 'received_while_inactive', 'received_at', 'created_at')
    search_fields = ('message_id', 'chat_session__from_number', 'content', 'sender_name', 'owner__full_name', 'owner__email')
    readonly_fields = ('message_id', 'created_at', 'received_at', 'updated_at')
    raw_id_fields = ('owner', 'chat_session')
    
    fieldsets = (
        ('Message Info', {
            'fields': ('message_id', 'chat_session', 'message_type', 'created_at', 'received_at', 'updated_at')
        }),
        ('Content', {
            'fields': ('content', 'media_url', 'media_file')
        }),
        ('Sender Info', {
            'fields': ('sender_name', 'source')
        }),
        ('Processing', {
            'fields': ('processing_status', 'response', 'audio_transcription', 'received_while_inactive')
        }),
        ('Raw Data', {
            'fields': ('raw_data',),
            'classes': ('collapse',)
        }),
    )
    
    def get_from_number(self, obj):
        """Retorna o número de origem da sessão de chat"""
        return obj.chat_session.from_number if obj.chat_session else '-'
    get_from_number.short_description = 'From Number'
    get_from_number.admin_order_field = 'chat_session__from_number'
    
    def inactive_badge(self, obj):
        """Exibe badge se mensagem foi recebida com instância inativa"""
        if obj.received_while_inactive:
            return format_html('<span class="badge bg-warning" title="Recebida com instância inativa">🔴 Inativa</span>')
        return format_html('<span class="badge bg-success" title="Recebida com instância ativa">✅ Ativa</span>')
    inactive_badge.short_description = 'Status da Instância'
    inactive_badge.admin_order_field = 'received_while_inactive'

    def get_queryset(self, request):
        """Otimiza queryset com select_related para owner."""
        qs = super().get_queryset(request)
        return qs.select_related('owner', 'chat_session')


@admin.register(ImageProcessingJob)
class ImageProcessingJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'message', 'processor_type', 'status', 'created_at', 'completed_at')
    list_filter = ('processor_type', 'status', 'created_at')
    search_fields = ('message__message_id', 'message__chat_session__from_number')
    readonly_fields = ('created_at', 'updated_at', 'completed_at')
    
    fieldsets = (
        ('Job Info', {
            'fields': ('message', 'processor_type', 'status')
        }),
        ('Timing', {
            'fields': ('created_at', 'updated_at', 'completed_at')
        }),
        ('Results', {
            'fields': ('result', 'error_message'),
            'classes': ('collapse',)
        }),
    )