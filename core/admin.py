from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from .models import Client, Contact, Tag, Employee, Appointment, ScheduleConfig, WorkingDay, BlockedDay

User = get_user_model()


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['user', 'client', 'created_at']
    list_filter = ['client', 'user']
    search_fields = ['user__username', 'client__full_name']
    raw_id_fields = ['user', 'client']


class UserInline(admin.TabularInline):
    """
    Inline para exibir usuários associados ao cliente.
    """
    model = User
    fk_name = 'client'
    extra = 0
    fields = ('username', 'email', 'is_active', 'is_staff')
    readonly_fields = ('username', 'email', 'is_active', 'is_staff')
    can_delete = False
    verbose_name = 'Usuário'
    verbose_name_plural = 'Usuários do Cliente'

    def has_add_permission(self, request, obj=None):
        return False


class AppointmentInline(admin.TabularInline):
    """
    Inline para exibir agendamentos do contato.
    """
    model = Appointment
    extra = 0
    fields = ('date', 'time', 'scheduled_for', 'calendar_event_id', 'created_at')
    readonly_fields = ('created_at', 'calendar_event_id')
    can_delete = True
    verbose_name = 'Agendamento'
    verbose_name_plural = 'Agendamentos do Contato'


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """
    Configuração do admin para o modelo Client.
    """
    list_display = [
        'full_name',
        'email',
        'client_type',
        'status',
        'users_count',
        'created_at',
    ]
    inlines = [UserInline]
    list_filter = [
        'status',
        'client_type',
        'created_at',
    ]
    search_fields = [
        'full_name',
        'email',
        'cpf',
        'cnpj',
        'company_name',
    ]
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
    ]
    fieldsets = (
        ('Informações Básicas', {
            'fields': (
                'id',
                'full_name',
                'email',
                'phone',
            )
        }),
        ('Tipo de Cliente', {
            'fields': (
                'client_type',
                'cpf',
                'cnpj',
                'company_name',
            )
        }),
        ('Dados de Faturamento', {
            'fields': (
                'billing_address',
                'billing_city',
                'billing_state',
                'billing_zip_code',
                'billing_country',
            )
        }),
        ('Status', {
            'fields': (
                'status',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
    )

    def get_queryset(self, request):
        """
        Otimiza queryset com prefetch_related para users.
        """
        qs = super().get_queryset(request)
        return qs.prefetch_related('users')

    def users_count(self, obj):
        """Retorna o número de usuários associados ao cliente."""
        return obj.users.count()
    users_count.short_description = 'Usuários'

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    """
    Configuração do admin para o modelo Contact.
    """
    inlines = [AppointmentInline]
    list_display = [
        'phone_number',
        'name',
        'profile_name',
        'client',
        'tags_display',
        'appointments_count',
        'total_messages',
        'is_blocked',
        'is_active',
        'last_contact_at',
    ]
    list_filter = [
        'is_blocked',
        'is_active',
        'created_at',
        'last_contact_at',
        'client',
        'tags',
    ]
    filter_horizontal = ['tags']
    search_fields = [
        'phone_number',
        'name',
        'profile_name',
        'email',
        'notes',
    ]
    readonly_fields = [
        'id',
        'first_contact_at',
        'last_contact_at',
        'created_at',
        'updated_at',
        'total_messages',
        'chat_sessions_count',
        'messages_count',
    ]
    fieldsets = (
        ('Informações do Contato', {
            'fields': (
                'id',
                'phone_number',
                'name',
                'profile_name',
                'email',
                'profile_pic_url',
            )
        }),
        ('Relacionamento', {
            'fields': (
                'client',
            )
        }),
        ('Metadados', {
            'fields': (
                'notes',
                'tags',
            )
        }),
        ('Estatísticas', {
            'fields': (
                'total_messages',
                'chat_sessions_count',
                'messages_count',
                'first_contact_at',
                'last_contact_at',
            )
        }),
        ('Status', {
            'fields': (
                'is_blocked',
                'is_active',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
    )
    actions = ['block_contacts', 'unblock_contacts', 'mark_as_inactive', 'mark_as_active']

    def get_queryset(self, request):
        """
        Otimiza queryset com select_related para client e prefetch tags e appointments.
        """
        qs = super().get_queryset(request)
        return qs.select_related('client').prefetch_related('tags', 'appointments')

    def tags_display(self, obj):
        """Exibe as tags do contato com cores"""
        tags = obj.tags.all()
        if not tags:
            return format_html('<span class="text-muted">-</span>')

        badges = []
        for tag in tags[:5]:  # Limitar a 5 tags na lista
            badges.append(format_html(
                '<span style="display: inline-block; padding: 2px 8px; border-radius: 8px; '
                'background-color: {}; color: white; font-size: 11px; margin: 2px;">{}</span>',
                tag.color,
                tag.name
            ))

        if tags.count() > 5:
            badges.append(format_html('<span class="text-muted">+{}</span>', tags.count() - 5))

        return format_html(' '.join(str(badge) for badge in badges))
    tags_display.short_description = 'Tags'

    def chat_sessions_count(self, obj):
        """Retorna o número de sessões de chat do contato."""
        return obj.chat_sessions.count()
    chat_sessions_count.short_description = 'Sessões de Chat'

    def messages_count(self, obj):
        """Retorna o número total de mensagens do contato."""
        return obj.get_message_history().count()
    messages_count.short_description = 'Mensagens'

    def appointments_count(self, obj):
        """Retorna o número de agendamentos do contato."""
        return obj.appointments.count()
    appointments_count.short_description = 'Agendamentos'

    @admin.action(description='Bloquear contatos selecionados')
    def block_contacts(self, request, queryset):
        """Bloqueia os contatos selecionados."""
        count = 0
        for contact in queryset:
            if not contact.is_blocked:
                contact.block(reason='Bloqueado pelo admin')
                count += 1
        self.message_user(request, f'{count} contato(s) bloqueado(s) com sucesso.')

    @admin.action(description='Desbloquear contatos selecionados')
    def unblock_contacts(self, request, queryset):
        """Desbloqueia os contatos selecionados."""
        count = 0
        for contact in queryset:
            if contact.is_blocked:
                contact.unblock()
                count += 1
        self.message_user(request, f'{count} contato(s) desbloqueado(s) com sucesso.')

    @admin.action(description='Marcar como inativo')
    def mark_as_inactive(self, request, queryset):
        """Marca os contatos como inativos."""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} contato(s) marcado(s) como inativo(s).')

    @admin.action(description='Marcar como ativo')
    def mark_as_active(self, request, queryset):
        """Marca os contatos como ativos."""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} contato(s) marcado(s) como ativo(s).')


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """
    Configuração do admin para o modelo Tag.
    """
    list_display = [
        'name_badge',
        'client',
        'contacts_count',
        'created_at',
    ]
    list_filter = [
        'client',
        'created_at',
    ]
    search_fields = [
        'name',
        'client__full_name',
        'client__email',
    ]
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'contacts_count',
    ]
    raw_id_fields = ['client']
    fieldsets = (
        ('Informações da Tag', {
            'fields': (
                'id',
                'client',
                'name',
                'color',
            )
        }),
        ('Estatísticas', {
            'fields': (
                'contacts_count',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
    )

    def get_queryset(self, request):
        """
        Otimiza queryset com select_related para client.
        """
        qs = super().get_queryset(request)
        return qs.select_related('client')

    def name_badge(self, obj):
        """Exibe o nome da tag com sua cor"""
        return format_html(
            '<span style="display: inline-block; padding: 4px 12px; border-radius: 12px; '
            'background-color: {}; color: white; font-weight: 500;">{}</span>',
            obj.color,
            obj.name
        )
    name_badge.short_description = 'Tag'
    name_badge.admin_order_field = 'name'

    def contacts_count(self, obj):
        """Retorna o número de contatos com esta tag"""
        return obj.contacts.count()
    contacts_count.short_description = 'Contatos'


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    """
    Configuração do admin para o modelo Appointment.
    """
    list_display = [
        'contact_info',
        'date',
        'time',
        'scheduled_for',
        'has_calendar_event',
        'created_at',
    ]
    list_filter = [
        'date',
        'created_at',
    ]
    search_fields = [
        'contact__name',
        'contact__phone_number',
        'calendar_event_id',
    ]
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'calendar_event_link',
    ]
    raw_id_fields = ['contact']
    date_hierarchy = 'date'
    ordering = ['-date', '-time']

    fieldsets = (
        ('Informações do Agendamento', {
            'fields': (
                'id',
                'contact',
                'scheduled_for',
                'date',
                'time',
            )
        }),
        ('Integração Google Calendar', {
            'fields': (
                'calendar_event_id',
                'calendar_event_link',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
    )

    def get_queryset(self, request):
        """
        Otimiza queryset com select_related para contact.
        """
        qs = super().get_queryset(request)
        return qs.select_related('contact', 'contact__client')

    def contact_info(self, obj):
        """Exibe informações do contato"""
        if obj.contact.name:
            return format_html(
                '<strong>{}</strong><br><small>{}</small>',
                obj.contact.name,
                obj.contact.phone_number
            )
        return obj.contact.phone_number
    contact_info.short_description = 'Contato'
    contact_info.admin_order_field = 'contact__name'

    def has_calendar_event(self, obj):
        """Indica se o agendamento tem evento no Google Calendar"""
        if obj.calendar_event_id:
            return format_html(
                '<span style="color: green;">✓ Sim</span>'
            )
        return format_html(
            '<span style="color: gray;">✗ Não</span>'
        )
    has_calendar_event.short_description = 'Google Calendar'

    def calendar_event_link(self, obj):
        """Exibe link para o evento no Google Calendar"""
        if obj.calendar_event_id:
            # URL do Google Calendar para visualizar o evento
            calendar_url = f"https://calendar.google.com/calendar/u/0/r/eventedit/{obj.calendar_event_id}"
            return format_html(
                '<a href="{}" target="_blank" style="color: #1a73e8;">📅 Ver no Google Calendar</a>',
                calendar_url
            )
        return format_html('<span style="color: gray;">-</span>')
    calendar_event_link.short_description = 'Link do Evento'


class WorkingDayInline(admin.TabularInline):
    """
    Inline para configurar dias de atendimento da semana.
    """
    model = WorkingDay
    extra = 7  # Mostrar os 7 dias da semana por padrão
    fields = ('weekday', 'is_active', 'start_time', 'end_time', 'lunch_start_time', 'lunch_end_time')
    verbose_name = 'Dia de Atendimento'
    verbose_name_plural = 'Dias de Atendimento'


class BlockedDayInline(admin.TabularInline):
    """
    Inline para configurar dias bloqueados.
    """
    model = BlockedDay
    extra = 1
    fields = ('date', 'reason')
    verbose_name = 'Dia Bloqueado'
    verbose_name_plural = 'Dias Bloqueados'


@admin.register(ScheduleConfig)
class ScheduleConfigAdmin(admin.ModelAdmin):
    """
    Configuração do admin para o modelo ScheduleConfig.
    """
    list_display = [
        'client',
        'appointment_duration_display',
        'active_days_count',
        'blocked_days_count',
        'created_at',
    ]
    list_filter = [
        'appointment_duration',
        'created_at',
    ]
    search_fields = [
        'client__full_name',
        'client__email',
    ]
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'active_days_count',
        'blocked_days_count',
    ]
    raw_id_fields = ['client']
    inlines = [WorkingDayInline, BlockedDayInline]

    fieldsets = (
        ('Informações da Agenda', {
            'fields': (
                'id',
                'client',
                'appointment_duration',
            )
        }),
        ('Estatísticas', {
            'fields': (
                'active_days_count',
                'blocked_days_count',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
    )

    def get_queryset(self, request):
        """
        Otimiza queryset com select_related e prefetch.
        """
        qs = super().get_queryset(request)
        return qs.select_related('client').prefetch_related('working_days', 'blocked_days')

    def appointment_duration_display(self, obj):
        """Exibe o tempo de consulta formatado"""
        return f"{obj.appointment_duration} minutos"
    appointment_duration_display.short_description = 'Tempo de Consulta'

    def active_days_count(self, obj):
        """Retorna o número de dias ativos na semana"""
        return obj.working_days.filter(is_active=True).count()
    active_days_count.short_description = 'Dias Ativos'

    def blocked_days_count(self, obj):
        """Retorna o número de dias bloqueados cadastrados"""
        return obj.blocked_days.count()
    blocked_days_count.short_description = 'Dias Bloqueados'


@admin.register(WorkingDay)
class WorkingDayAdmin(admin.ModelAdmin):
    """
    Configuração do admin para o modelo WorkingDay.
    """
    list_display = [
        'schedule_config',
        'weekday_display',
        'is_active',
        'start_time',
        'end_time',
        'has_lunch_break',
        'created_at',
    ]
    list_filter = [
        'weekday',
        'is_active',
        'schedule_config__client',
    ]
    search_fields = [
        'schedule_config__client__full_name',
        'schedule_config__client__email',
    ]
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
    ]
    raw_id_fields = ['schedule_config']

    fieldsets = (
        ('Configuração do Dia', {
            'fields': (
                'id',
                'schedule_config',
                'weekday',
                'is_active',
            )
        }),
        ('Horários', {
            'fields': (
                'start_time',
                'end_time',
                'lunch_start_time',
                'lunch_end_time',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
    )

    def get_queryset(self, request):
        """
        Otimiza queryset com select_related.
        """
        qs = super().get_queryset(request)
        return qs.select_related('schedule_config', 'schedule_config__client')

    def weekday_display(self, obj):
        """Exibe o nome do dia da semana"""
        return dict(WorkingDay.WEEKDAY_CHOICES)[obj.weekday]
    weekday_display.short_description = 'Dia da Semana'
    weekday_display.admin_order_field = 'weekday'

    def has_lunch_break(self, obj):
        """Indica se o dia tem horário de almoço configurado"""
        if obj.lunch_start_time and obj.lunch_end_time:
            return format_html(
                '<span style="color: green;">✓ {}-{}</span>',
                obj.lunch_start_time.strftime('%H:%M'),
                obj.lunch_end_time.strftime('%H:%M')
            )
        return format_html('<span style="color: gray;">✗ Sem intervalo</span>')
    has_lunch_break.short_description = 'Horário de Almoço'


@admin.register(BlockedDay)
class BlockedDayAdmin(admin.ModelAdmin):
    """
    Configuração do admin para o modelo BlockedDay.
    """
    list_display = [
        'schedule_config',
        'date',
        'reason',
        'created_at',
    ]
    list_filter = [
        'date',
        'schedule_config__client',
        'created_at',
    ]
    search_fields = [
        'schedule_config__client__full_name',
        'schedule_config__client__email',
        'reason',
    ]
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
    ]
    raw_id_fields = ['schedule_config']
    date_hierarchy = 'date'
    ordering = ['-date']

    fieldsets = (
        ('Informações do Bloqueio', {
            'fields': (
                'id',
                'schedule_config',
                'date',
                'reason',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
    )
