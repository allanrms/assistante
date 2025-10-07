from django.contrib import admin
from django.contrib.auth import get_user_model
from .models import Client

User = get_user_model()


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
