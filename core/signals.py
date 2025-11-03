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