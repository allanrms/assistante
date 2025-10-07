from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Admin personalizado para o modelo User
    """
    fieldsets = UserAdmin.fieldsets + (
        ('Relação com Cliente', {
            'fields': ('client',)
        }),
        ('Confirmação de Email', {
            'fields': ('email_confirmed', 'email_confirmation_token', 'email_confirmation_sent_at')
        }),
        ('Preferências', {
            'fields': ('preferred_language',)
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Relação com Cliente', {
            'fields': ('client',)
        }),
        ('Confirmação de Email', {
            'fields': ('email_confirmed',)
        }),
        ('Preferências', {
            'fields': ('preferred_language',)
        }),
    )

    list_display = UserAdmin.list_display + ('client', 'email_confirmed', 'preferred_language')
    list_filter = UserAdmin.list_filter + ('client', 'email_confirmed', 'preferred_language')
    readonly_fields = ('email_confirmation_token', 'email_confirmation_sent_at')
    raw_id_fields = ('client',)

    def get_queryset(self, request):
        """Otimiza queryset com select_related para client."""
        qs = super().get_queryset(request)
        return qs.select_related('client')
