"""
Mixins e helpers para acesso ao Client através do User.
"""
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.translation import gettext_lazy as _


class ClientRequiredMixin:
    """
    Mixin que garante que o usuário tenha um perfil de Cliente.
    Redireciona para cadastro se não tiver.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('webapp:login')

        # Verifica se o usuário pertence a um cliente
        if not request.user.client:
            messages.warning(
                request,
                _('Você precisa completar seu cadastro de cliente para acessar esta página.')
            )
            return redirect('core:register')

        # Verifica se o email foi confirmado
        if not request.user.email_confirmed:
            messages.warning(
                request,
                _('Você precisa confirmar seu e-mail antes de acessar esta página.')
            )
            return redirect('webapp:login')

        return super().dispatch(request, *args, **kwargs)


def get_client_from_request(request):
    """
    Helper function para obter o Client do request.

    Args:
        request: Django request object

    Returns:
        Client object or None
    """
    if not request.user.is_authenticated:
        return None

    return request.user.client


def get_client_or_redirect(request):
    """
    Helper function que retorna o Client ou redireciona para cadastro.

    Args:
        request: Django request object

    Returns:
        Client object

    Raises:
        Redirect to registration if no client profile exists
    """
    client = get_client_from_request(request)

    if not client:
        messages.warning(
            request,
            _('Você precisa completar seu cadastro de cliente para continuar.')
        )
        raise redirect('core:register')

    if not client.email_confirmed:
        messages.warning(
            request,
            _('Você precisa confirmar seu e-mail antes de continuar.')
        )
        raise redirect('webapp:login')

    return client
