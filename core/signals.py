from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from datetime import time

from agents.models import Conversation
from agents.tasks import create_conversation_summary

from core.models import Appointment, ScheduleConfig, WorkingDay


# @receiver(post_save, sender=Appointment, weak=False)
# def post_save_appointment(sender, instance: Appointment, *args, **kwargs):
#     create_conversation_summary(Conversation.objects.filter(contact_id=instance.contact.id).last())
#
# @receiver(post_delete, sender=Appointment, weak=False)
# def post_delete_appointment(sender, instance: Appointment, **kwargs):
#     create_conversation_summary(Conversation.objects.filter(contact_id=instance.contact.id).last())


@receiver(post_save, sender=ScheduleConfig)
def create_default_working_days(sender, instance, created, **kwargs):
    """
    Cria automaticamente os 7 dias da semana com horários padrão
    quando um ScheduleConfig é criado.

    Horários padrão:
    - Segunda a Sexta: 08:00-18:00, almoço 12:00-13:00 (Ativo)
    - Sábado: 08:00-12:00, sem almoço (Ativo)
    - Domingo: Inativo
    """
    if created:
        # Horários padrão para cada dia da semana
        default_working_hours = [
            # Segunda-feira (0)
            {
                'weekday': 0,
                'is_active': True,
                'start_time': time(8, 0),
                'end_time': time(18, 0),
                'lunch_start_time': time(12, 0),
                'lunch_end_time': time(13, 0),
            },
            # Terça-feira (1)
            {
                'weekday': 1,
                'is_active': True,
                'start_time': time(8, 0),
                'end_time': time(18, 0),
                'lunch_start_time': time(12, 0),
                'lunch_end_time': time(13, 0),
            },
            # Quarta-feira (2)
            {
                'weekday': 2,
                'is_active': True,
                'start_time': time(8, 0),
                'end_time': time(18, 0),
                'lunch_start_time': time(12, 0),
                'lunch_end_time': time(13, 0),
            },
            # Quinta-feira (3)
            {
                'weekday': 3,
                'is_active': True,
                'start_time': time(8, 0),
                'end_time': time(18, 0),
                'lunch_start_time': time(12, 0),
                'lunch_end_time': time(13, 0),
            },
            # Sexta-feira (4)
            {
                'weekday': 4,
                'is_active': True,
                'start_time': time(8, 0),
                'end_time': time(18, 0),
                'lunch_start_time': time(12, 0),
                'lunch_end_time': time(13, 0),
            },
            # Sábado (5)
            {
                'weekday': 5,
                'is_active': True,
                'start_time': time(8, 0),
                'end_time': time(12, 0),
                'lunch_start_time': None,
                'lunch_end_time': None,
            },
            # Domingo (6)
            {
                'weekday': 6,
                'is_active': False,
                'start_time': time(8, 0),
                'end_time': time(18, 0),
                'lunch_start_time': None,
                'lunch_end_time': None,
            },
        ]

        # Criar os dias de atendimento
        for day_config in default_working_hours:
            WorkingDay.objects.create(
                schedule_config=instance,
                **day_config
            )

        print(f"✅ Criados 7 dias de atendimento padrão para {instance.client.full_name}")


# =============================================================================
# Google Calendar Sync Signals
# =============================================================================

import logging
from datetime import datetime, timedelta
from django.db.models.signals import pre_delete
from django.utils import timezone
from google_calendar.services import GoogleCalendarService

logger = logging.getLogger(__name__)


def should_sync_to_calendar(appointment):
    """
    Verifica se o appointment deve ser sincronizado com o Google Calendar.

    Critérios:
    - Deve ter data e hora definidos
    - Status deve ser 'confirmed' ou 'pending'
    - Não deve estar cancelado ou em rascunho
    """
    if not appointment.date or not appointment.time:
        logger.info(f"[Appointment Signal] Não sincronizando - sem data/hora: {appointment.id}")
        return False

    if appointment.status in ['cancelled', 'draft']:
        logger.info(f"[Appointment Signal] Não sincronizando - status {appointment.status}: {appointment.id}")
        return False

    return True


def get_calendar_service_for_appointment(appointment):
    """
    Retorna o GoogleCalendarService e o contact_id para o appointment.
    """
    try:
        contact_id = str(appointment.contact.id)
        service = GoogleCalendarService()
        return service, contact_id
    except Exception as e:
        logger.error(f"[Appointment Signal] Erro ao obter GoogleCalendarService: {str(e)}")
        return None, None


def create_event_data(appointment):
    """
    Cria o dicionário de dados do evento para o Google Calendar.
    """
    # Combina data e hora para criar datetime
    start_datetime = datetime.combine(appointment.date, appointment.time)

    # Define duração padrão de 60 minutos se não houver configuração
    duration_minutes = 60
    if hasattr(appointment.contact, 'client') and appointment.contact.client:
        try:
            schedule_config = appointment.contact.client.schedule_config
            duration_minutes = schedule_config.appointment_duration
        except:
            pass

    end_datetime = start_datetime + timedelta(minutes=duration_minutes)

    # Converte para timezone aware
    start_datetime = timezone.make_aware(start_datetime) if timezone.is_naive(start_datetime) else start_datetime
    end_datetime = timezone.make_aware(end_datetime) if timezone.is_naive(end_datetime) else end_datetime

    # Nome do contato
    contact_name = appointment.contact.name or appointment.contact.phone_number

    # Monta o evento
    event_data = {
        'summary': f'Consulta - {contact_name}',
        'description': f'Consulta agendada via WhatsApp\nContato: {contact_name}\nTelefone: {appointment.contact.phone_number}',
        'start': {
            'dateTime': start_datetime.isoformat(),
            'timeZone': 'America/Sao_Paulo',
        },
        'end': {
            'dateTime': end_datetime.isoformat(),
            'timeZone': 'America/Sao_Paulo',
        },
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'email', 'minutes': 24 * 60},  # 1 dia antes
                {'method': 'popup', 'minutes': 60},  # 1 hora antes
            ],
        },
    }

    return event_data


@receiver(post_save, sender=Appointment)
def sync_appointment_to_google_calendar(sender, instance, created, **kwargs):
    """
    Signal que sincroniza Appointment com Google Calendar.

    - Quando criado: cria evento no Google Calendar
    - Quando atualizado: atualiza ou cria evento no Google Calendar
    """
    try:
        logger.info(f"[Appointment Signal] post_save - Appointment ID: {instance.id}, Created: {created}")

        # Verifica se deve sincronizar
        if not should_sync_to_calendar(instance):
            # Se tinha evento no calendar e agora não deve mais ter (ex: cancelado), deleta
            if instance.calendar_event_id:
                logger.info(f"[Appointment Signal] Appointment cancelado/rascunho, deletando evento: {instance.calendar_event_id}")
                service, contact_id = get_calendar_service_for_appointment(instance)
                if service and contact_id:
                    success, result = service.delete_event(contact_id, instance.calendar_event_id)
                    if success:
                        instance.calendar_event_id = None
                        instance.save(update_fields=['calendar_event_id'])
            return

        # Obtém o serviço
        service, contact_id = get_calendar_service_for_appointment(instance)
        if not service or not contact_id:
            logger.warning(f"[Appointment Signal] GoogleCalendarService não disponível para Appointment {instance.id}")
            return

        # Cria os dados do evento
        event_data = create_event_data(instance)

        # Se já tem calendar_event_id, tenta atualizar
        if instance.calendar_event_id:
            logger.info(f"[Appointment Signal] Tentando atualizar evento existente: {instance.calendar_event_id}")
            try:
                # Busca o serviço do calendar
                calendar_service = service.get_calendar_service(contact_id)
                if calendar_service:
                    # Atualiza o evento
                    updated_event = calendar_service.events().update(
                        calendarId='primary',
                        eventId=instance.calendar_event_id,
                        body=event_data
                    ).execute()
                    logger.info(f"✅ [Appointment Signal] Evento atualizado no Google Calendar: {updated_event.get('htmlLink')}")
                    return
            except Exception as e:
                logger.warning(f"[Appointment Signal] Erro ao atualizar evento, tentando criar novo: {str(e)}")
                # Se falhar ao atualizar, cria um novo
                instance.calendar_event_id = None

        # Cria novo evento
        logger.info(f"[Appointment Signal] Criando novo evento no Google Calendar")
        success, result = service.create_event(contact_id, event_data)

        if success:
            # Salva o event_id retornado
            event_id = result.get('id')
            logger.info(f"✅ [Appointment Signal] Evento criado com sucesso: {result.get('htmlLink')}")

            # Atualiza o appointment com o event_id (sem disparar signal novamente)
            Appointment.objects.filter(pk=instance.pk).update(calendar_event_id=event_id)
        else:
            logger.error(f"❌ [Appointment Signal] Erro ao criar evento: {result}")

    except Exception as e:
        logger.error(f"❌ [Appointment Signal] Erro inesperado ao sincronizar: {str(e)}", exc_info=True)


@receiver(pre_delete, sender=Appointment)
def delete_appointment_from_google_calendar(sender, instance, **kwargs):
    """
    Signal que deleta o evento do Google Calendar quando Appointment é deletado.
    """
    try:
        logger.info(f"[Appointment Signal] pre_delete - Appointment ID: {instance.id}")

        # Se não tem calendar_event_id, não há nada para deletar
        if not instance.calendar_event_id:
            logger.info(f"[Appointment Signal] Appointment sem calendar_event_id, nada para deletar")
            return

        # Obtém o serviço
        service, contact_id = get_calendar_service_for_appointment(instance)
        if not service or not contact_id:
            logger.warning(f"[Appointment Signal] GoogleCalendarService não disponível para deletar Appointment {instance.id}")
            return

        # Deleta o evento
        logger.info(f"[Appointment Signal] Deletando evento do Google Calendar: {instance.calendar_event_id}")
        success, result = service.delete_event(contact_id, instance.calendar_event_id)

        if success:
            logger.info(f"✅ [Appointment Signal] Evento deletado com sucesso do Google Calendar")
        else:
            logger.error(f"❌ [Appointment Signal] Erro ao deletar evento: {result}")

    except Exception as e:
        logger.error(f"❌ [Appointment Signal] Erro inesperado ao deletar: {str(e)}", exc_info=True)