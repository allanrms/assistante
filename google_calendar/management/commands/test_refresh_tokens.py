from django.core.management.base import BaseCommand
from google_calendar.cron.process_google_calendar_updates import refresh_token_google_calendar_auth


class Command(BaseCommand):
    help = 'Testa a renovação de tokens do Google Calendar'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando teste de renovação de tokens...'))

        try:
            refresh_token_google_calendar_auth()
            self.stdout.write(self.style.SUCCESS('\n✅ Teste concluído com sucesso!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Teste falhou: {str(e)}'))
            raise
