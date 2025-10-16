from django import template
from core.models import Client, Employee

register = template.Library()

@register.inclusion_tag('core/tags/client_selector.html', takes_context=True)
def client_selector(context):
    user = context['request'].user
    clients = Client.objects.none()
    
    if user.is_authenticated:
        if user.is_superuser:
            clients = Client.objects.all()
        else:
            # Get clients from Employee relationship
            clients = Client.objects.filter(employees__user=user)
            # Also include the user's own client if it exists
            if user.client and user.client not in clients:
                clients = (clients | Client.objects.filter(pk=user.client.pk)).distinct()

    current_client = getattr(user, 'client', None)
    
    return {
        'clients': clients,
        'current_client': current_client,
    }