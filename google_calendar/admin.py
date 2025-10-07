from django.contrib import admin
from .models import GoogleCalendarAuth, CalendarIntegrationRequest


@admin.register(GoogleCalendarAuth)
class GoogleCalendarAuthAdmin(admin.ModelAdmin):
    list_display = ('user', 'whatsapp_number', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user__username', 'whatsapp_number')
    readonly_fields = ('created_at', 'updated_at', 'expires_at')

    fieldsets = (
        ('Usuário', {
            'fields': ('user', 'whatsapp_number')
        }),
        ('Tokens (Sensível)', {
            'fields': ('access_token', 'refresh_token', 'expires_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CalendarIntegrationRequest)
class CalendarIntegrationRequestAdmin(admin.ModelAdmin):
    list_display = ('whatsapp_number', 'request_token', 'is_completed', 'created_at', 'completed_at')
    list_filter = ('is_completed', 'created_at', 'completed_at')
    search_fields = ('whatsapp_number', 'request_token')
    readonly_fields = ('request_token', 'created_at', 'completed_at')

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('whatsapp_number',)
        return self.readonly_fields
