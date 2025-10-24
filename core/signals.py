from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from agents.models import Conversation
from agents.tasks import create_conversation_summary

from core.models import Appointment


# @receiver(post_save, sender=Appointment, weak=False)
# def post_save_appointment(sender, instance: Appointment, *args, **kwargs):
#     create_conversation_summary(Conversation.objects.filter(contact_id=instance.contact.id).last())
#
# @receiver(post_delete, sender=Appointment, weak=False)
# def post_delete_appointment(sender, instance: Appointment, **kwargs):
#     create_conversation_summary(Conversation.objects.filter(contact_id=instance.contact.id).last())