import traceback
from datetime import timedelta
from django.conf import settings
from django.core.mail import mail_admins
from django.utils import timezone

from google_calendar.models import GoogleCalendarAuth
from google_calendar.services import GoogleCalendarService


def refresh_token_google_calendar_auth():
    """
    Faz refresh dos tokens do Google Calendar que estão próximos de expirar.

    Este job deve rodar periodicamente (ex: a cada hora) para garantir que os tokens
    estejam sempre válidos antes de expirarem.
    """
    try:
        print("🔄 [CRON] Iniciando refresh de tokens Google Calendar...")

        # Buscar todos os GoogleCalendarAuth que expiram nas próximas 24 horas
        now = timezone.now()
        expiring_soon = now + timedelta(hours=24)

        auth_list = GoogleCalendarAuth.objects.filter(
            expires_at__lte=expiring_soon,
            expires_at__gte=now
        )

        total = auth_list.count()
        print(f"📊 [CRON] Encontrados {total} tokens para renovar")

        if total == 0:
            print("✅ [CRON] Nenhum token precisa ser renovado no momento")
            return

        calendar_service = GoogleCalendarService()
        success_count = 0
        error_count = 0

        for auth in auth_list:
            user_info = f"{auth.user.username} ({auth.user.client.full_name if auth.user.client else 'Sem cliente'})"

            try:
                print(f"🔄 [CRON] Renovando token para: {user_info}")
                print(f"   Expira em: {auth.expires_at}")

                # Usa o método _refresh_token do GoogleCalendarService
                calendar_service._refresh_token(auth)  # noqa: SLF001

                success_count += 1
                print(f"✅ [CRON] Token renovado com sucesso para {user_info}")
                print(f"   Nova expiração: {auth.expires_at}")

            except Exception as e:
                error_count += 1
                print(f"❌ [CRON] Erro ao renovar token para {user_info}: {str(e)}")
                traceback.print_exc()

        print(f"📈 [CRON] Resumo:")
        print(f"   ✅ Sucessos: {success_count}")
        print(f"   ❌ Erros: {error_count}")
        print(f"   📊 Total: {total}")

        # Se houver erros em produção, notificar admins
        if error_count > 0 and not settings.DEBUG:
            subject = f"Google Calendar Token Refresh - {error_count} erro(s)"
            message = f"""
            Refresh de tokens do Google Calendar concluído com erros:

            - Sucessos: {success_count}
            - Erros: {error_count}
            - Total: {total}

            Verifique os logs para mais detalhes.
            """
            mail_admins(subject, message)

    except Exception as e:
        print(f"❌ [CRON] Erro crítico no job de refresh: {str(e)}")
        traceback.print_exc()

        if not settings.DEBUG:
            subject = "Google Calendar Token Refresh - Falha Crítica"
            message = f'{traceback.format_exc()}\n\nLocals: {locals()}'
            mail_admins(subject, message)

        raise e


def run():
    refresh_token_google_calendar_auth()
