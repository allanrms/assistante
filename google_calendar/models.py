from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class GoogleCalendarAuth(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='google_calendar_auth')
    access_token = models.TextField()
    refresh_token = models.TextField()
    expires_at = models.DateTimeField()
    whatsapp_number = models.CharField(max_length=20, null=True, blank=True)
    evolution_instance = models.ForeignKey('whatsapp_connector.EvolutionInstance', on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Google Calendar Auth for {self.user.username}"

    class Meta:
        verbose_name = "Google Calendar Authentication"
        verbose_name_plural = "Google Calendar Authentications"


class CalendarIntegrationRequest(models.Model):
    whatsapp_number = models.CharField(max_length=20)
    request_token = models.CharField(max_length=100, unique=True)
    evolution_instance = models.ForeignKey('whatsapp_connector.EvolutionInstance', on_delete=models.CASCADE, null=True, blank=True)
    user_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"Calendar Integration Request for {self.whatsapp_number}"

    class Meta:
        verbose_name = "Calendar Integration Request"
        verbose_name_plural = "Calendar Integration Requests"
