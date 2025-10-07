from django.apps import AppConfig


class WhatsappConnectorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'whatsapp_connector'

    def ready(self):
        import whatsapp_connector.signals
