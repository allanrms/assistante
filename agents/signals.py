"""
Signals para o app agents
"""
import logging
import random
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Conversation

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Conversation)
def notify_human_attendance(sender, instance, created, **kwargs):
    """
    Signal que dispara quando uma conversa muda de status para 'human'.
    Envia notificação WhatsApp para os contatos cadastrados na instância.
    """
    # Só processa se o status mudou para 'human'
    # Para detectar mudança, precisamos comparar com o estado anterior
    # Como post_save já salvou, vamos usar uma flag personalizada
    if not hasattr(instance, '_status_changed_to_human'):
        return

    if instance.status != 'human':
        return

    from whatsapp_connector.models import NotificationContact
    from evolution.services import EvolutionAPIService

    if not instance.evolution_instance:
        logger.warning(f"Conversation {instance.id} não tem evolution_instance associada")
        return

    evolution_instance = instance.evolution_instance

    # Buscar contatos ativos
    notification_contacts = NotificationContact.objects.filter(
        evolution_instance=evolution_instance,
        is_active=True
    )

    if not notification_contacts.exists():
        logger.info(f"Nenhum contato de notificação cadastrado para a instância {evolution_instance.name}")
        return

    # Preparar mensagem de notificação
    contact_name = instance.contact.name if instance.contact else instance.from_number
    message_text = (
        f"🔔 *Atendimento Humano Solicitado*\n\n"
        f"📱 *Contato:* {contact_name}\n"
        f"📞 *Número:* {instance.from_number}\n"
        f"💬 *Instância:* {evolution_instance.name}\n\n"
        f"Uma conversa necessita de atendimento humano."
    )

    # Determinar quais contatos receberão a notificação baseado na estratégia
    contacts_to_notify = []
    if evolution_instance.notification_strategy == 'all':
        # Enviar para todos
        contacts_to_notify = list(notification_contacts)
    elif evolution_instance.notification_strategy == 'random':
        # Enviar para um aleatório
        contacts_to_notify = [random.choice(notification_contacts)]

    # Inicializar serviço Evolution API
    evolution_service = EvolutionAPIService(
        base_url=evolution_instance.base_url,
        api_key=evolution_instance.api_key,
        instance_name=evolution_instance.instance_name
    )

    # Enviar notificação para os contatos selecionados
    for contact in contacts_to_notify:
        try:
            success, response = evolution_service.send_text_message(
                number=contact.phone,
                text=message_text
            )

            if success:
                logger.info(f"Notificação enviada com sucesso para {contact.name} ({contact.phone})")
            else:
                logger.error(f"Erro ao enviar notificação para {contact.name}: {response}")
        except Exception as e:
            logger.error(f"Exceção ao enviar notificação para {contact.name}: {str(e)}")
